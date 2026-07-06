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
from collections.abc import Callable

from .db import create_db_engine, make_session_factory
from .models import AssetStatus, Audio, Job, JobStatus
from .observability import configure_logging, init_error_tracking
from .queue import queue_key, redis_from_url
from .voices import UnsupportedLanguageError
from .worker_common import (
    MAINTENANCE_INTERVAL_SECONDS,
    ack,
    handle_job_failure,
    reap_stuck,
    reconcile_orphans,
    reliable_pop,
    write_heartbeat,
)

logger = logging.getLogger(__name__)

Synthesizer = Callable[[Audio, str], str]


def _text_for(audio: Audio) -> str:
    poem = audio.poem
    return poem.poem_ja if audio.lang == "ja" else poem.poem_en


class RoutingSynthesizer:
    """Dispatch synthesis to a per-language backend (#89).

    English uses the configured Piper/XTTS backend; Japanese uses VOICEVOX when
    ``VOICEVOX_URL`` is set. A language with no registered backend falls through
    to ``default`` (Piper), which raises ``UnsupportedLanguageError`` with
    guidance instead of garbling the text with the wrong-language voice.
    """

    def __init__(self, default: Synthesizer, by_lang: dict[str, Synthesizer] | None = None):
        self._default = default
        self._by_lang = by_lang or {}

    def __call__(self, audio: Audio, text: str) -> str:
        synth = self._by_lang.get((audio.lang or "en").lower(), self._default)
        return synth(audio, text)


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
            except UnsupportedLanguageError as exc:
                # Deterministic config error (e.g. ja on the Piper backend): no
                # point retrying — fail immediately with actionable guidance
                # instead of garbling the audio with the wrong-language voice.
                job.status = JobStatus.FAILED
                audio.status = AssetStatus.FAILED
                job.error = str(exc)[:500]
                logger.warning("audio job %s unsupported language: %s", job_id, exc)
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
        reconcile_orphans(self._redis, self._session_factory, "audio")
        last_maintenance = time.monotonic()
        while True:
            try:
                write_heartbeat("audio")
                self.run_once()
                if time.monotonic() - last_maintenance > MAINTENANCE_INTERVAL_SECONDS:
                    reap_stuck(self._redis, "audio")
                    # Also recover jobs committed as QUEUED but missing from Redis
                    # (e.g. the API crashed / the enqueue failed right after the DB
                    # commit) without waiting for a worker restart. QUEUED-only so
                    # an in-flight (RUNNING) job is never double-processed (#126).
                    reconcile_orphans(
                        self._redis, self._session_factory, "audio", statuses=(JobStatus.QUEUED,)
                    )
                    last_maintenance = time.monotonic()
            except Exception:  # noqa: BLE001
                logger.exception("worker loop error")
                time.sleep(1)


def _english_synthesizer(data_dir) -> Synthesizer:
    backend = os.environ.get("TTS_BACKEND", "piper").lower()
    if backend == "xtts":
        from .tts_xtts import XttsSynthesizer

        return XttsSynthesizer(data_dir=data_dir)

    from .tts import PiperSynthesizer

    return PiperSynthesizer(data_dir=data_dir)


def _default_synthesizer() -> Synthesizer:
    from pathlib import Path

    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    base = _english_synthesizer(data_dir)

    # Japanese is voiced by VOICEVOX when configured; route ja jobs to it and
    # leave everything else on the base (Piper/XTTS) backend (#89). With no
    # VOICEVOX_URL there is nothing to route, so keep the base synthesizer as-is
    # (a bare PiperSynthesizer/XttsSynthesizer, preserving prior behavior).
    by_lang: dict[str, Synthesizer] = {}
    voicevox_url = os.environ.get("VOICEVOX_URL")
    if voicevox_url:
        from .tts_voicevox import VoicevoxSynthesizer

        by_lang["ja"] = VoicevoxSynthesizer(data_dir=data_dir, base_url=voicevox_url)

    if not by_lang:
        return base
    return RoutingSynthesizer(base, by_lang)


def build_worker(synthesizer: Synthesizer | None = None) -> AudioWorker:
    engine = create_db_engine()
    session_factory = make_session_factory(engine)
    client = redis_from_url()
    return AudioWorker(
        session_factory,
        client,
        synthesizer or _default_synthesizer(),
        max_retries=int(os.environ.get("JOB_MAX_RETRIES", "1")),
    )


def main() -> None:
    configure_logging()
    init_error_tracking()
    build_worker().run()


if __name__ == "__main__":
    main()
