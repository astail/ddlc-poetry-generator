"""Text-to-speech worker (issue #14).

Consumes audio jobs from Redis and drives Audio/Job through the status state
machine. Synthesis is injected as a `synthesizer` (Audio, text) -> path; the
default uses Piper (CPU). Runs from the api image:
    docker compose run --rm worker-tts   # command: python -m app.worker_tts
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, Optional

from .db import create_db_engine, make_session_factory
from .models import AssetStatus, Audio, Job, JobStatus
from .queue import queue_key
from .worker_common import ack, handle_job_failure, reap_stuck, reliable_pop

logger = logging.getLogger(__name__)

Synthesizer = Callable[[Audio, str], str]


def _text_for(audio: Audio) -> str:
    poem = audio.poem
    return poem.poem_ja if audio.lang == "ja" else poem.poem_en


class AudioWorker:
    def __init__(
        self,
        session_factory,
        redis_client,
        synthesizer: Synthesizer,
        block_timeout: int = 5,
        max_retries: int = 1,
    ):
        self._session_factory = session_factory
        self._redis = redis_client
        self._synthesizer = synthesizer
        self._block_timeout = block_timeout
        self._max_retries = max_retries

    def run_once(self) -> bool:
        """Block for one job; reliable pop -> process -> (requeue) -> ack.

        See ImageWorker.run_once: in-flight ids live on the processing list and
        are only acked once handled; a retry re-enqueues after the commit, so a
        crash can't drop the job (at-least-once delivery).
        """
        raw = reliable_pop(self._redis, "audio", self._block_timeout)
        if raw is None:
            return False
        try:
            job_id = int(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
        except (ValueError, AttributeError):
            logger.error("invalid job id on queue: %r", raw)
            ack(self._redis, "audio", raw)
            return True
        requeue = self.process(job_id)
        if requeue:
            self._redis.rpush(queue_key("audio"), job_id)
        ack(self._redis, "audio", raw)
        return True

    def process(self, job_id: int) -> bool:
        """Run one job to completion. Returns True if it should be re-enqueued."""
        with self._session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                logger.warning("job %s not found", job_id)
                return False
            if job.status == JobStatus.DONE:
                logger.info("job %s already done, skipping", job_id)
                return False

            audio = session.get(Audio, job.ref_id)
            if audio is None:
                job.status = JobStatus.FAILED
                job.error = "audio not found"
                session.commit()
                return False

            job.status = JobStatus.RUNNING
            audio.status = AssetStatus.RUNNING
            session.commit()

            requeue = False
            try:
                path = self._synthesizer(audio, _text_for(audio))
                audio.path = path
                audio.status = AssetStatus.DONE
                job.status = JobStatus.DONE
                job.error = None
            except Exception as exc:  # noqa: BLE001
                requeue = handle_job_failure(
                    self._redis,
                    job,
                    audio,
                    exc,
                    job_type="audio",
                    max_retries=self._max_retries,
                )
                logger.exception("audio job %s failed", job_id)
            session.commit()
            return requeue

    def run(self) -> None:
        logger.info("audio worker started (queue=%s)", queue_key("audio"))
        reap_stuck(self._redis, "audio")
        while True:
            try:
                self.run_once()
            except Exception:  # noqa: BLE001
                logger.exception("worker loop error")
                time.sleep(1)


def _default_synthesizer() -> Synthesizer:
    from pathlib import Path

    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    backend = os.environ.get("TTS_BACKEND", "piper").lower()
    if backend == "xtts":
        from .tts_xtts import XttsSynthesizer

        return XttsSynthesizer(data_dir=data_dir)

    from .tts import PiperSynthesizer

    return PiperSynthesizer(data_dir=data_dir)


def build_worker(synthesizer: Optional[Synthesizer] = None) -> AudioWorker:
    import redis

    engine = create_db_engine()
    session_factory = make_session_factory(engine)
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
    return AudioWorker(
        session_factory,
        client,
        synthesizer or _default_synthesizer(),
        max_retries=int(os.environ.get("JOB_MAX_RETRIES", "1")),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    build_worker().run()


if __name__ == "__main__":
    main()
