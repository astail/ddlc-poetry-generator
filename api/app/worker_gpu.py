"""Image-generation worker (issue #9).

Consumes image jobs from Redis and drives them through the Job/Image status
state machine. The actual Stable Diffusion / ComfyUI call is injected as a
``processor`` (implemented in issue #12); the default raises NotImplementedError.

Shares the ``app`` package (models, db, queue) and runs from the api image:
    docker compose run --rm worker-gpu   # command: python -m app.worker_gpu
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable, Optional

from .db import create_db_engine, make_session_factory
from .models import AssetStatus, Image, Job, JobStatus
from .queue import queue_key
from .worker_common import handle_job_failure

logger = logging.getLogger(__name__)

ImageProcessor = Callable[[Image], str]


class ImageWorker:
    def __init__(
        self,
        session_factory,
        redis_client,
        processor: ImageProcessor,
        block_timeout: int = 5,
        max_retries: int = 1,
    ):
        self._session_factory = session_factory
        self._redis = redis_client
        self._processor = processor
        self._block_timeout = block_timeout
        self._max_retries = max_retries

    def run_once(self) -> bool:
        """Block for one job; return True if one was consumed, False on timeout."""
        popped = self._redis.blpop([queue_key("image")], timeout=self._block_timeout)
        if not popped:
            return False
        _key, raw = popped
        try:
            job_id = int(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
        except (ValueError, AttributeError):
            logger.error("invalid job id on queue: %r", raw)
            return True
        self.process(job_id)
        return True

    def process(self, job_id: int) -> None:
        with self._session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                logger.warning("job %s not found", job_id)
                return
            if job.status == JobStatus.DONE:
                logger.info("job %s already done, skipping", job_id)
                return

            image = session.get(Image, job.ref_id)
            if image is None:
                job.status = JobStatus.FAILED
                job.error = "image not found"
                session.commit()
                return

            job.status = JobStatus.RUNNING
            image.status = AssetStatus.RUNNING
            session.commit()

            try:
                path = self._processor(image)
                image.path = path
                image.status = AssetStatus.DONE
                job.status = JobStatus.DONE
                job.error = None
            except Exception as exc:  # noqa: BLE001 - record failure, keep looping
                handle_job_failure(
                    self._redis, job, image, exc,
                    job_type="image", max_retries=self._max_retries,
                )
                logger.exception("image job %s failed", job_id)
            session.commit()

    def run(self) -> None:
        logger.info("image worker started (queue=%s)", queue_key("image"))
        while True:
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - never let the loop die
                logger.exception("worker loop error")
                time.sleep(1)


def _default_processor() -> ImageProcessor:
    from pathlib import Path

    from .comfyui_client import ComfyUIClient, make_comfyui_processor

    client = ComfyUIClient(
        os.environ.get("COMFYUI_URL", "http://comfyui:8188"),
        data_dir=Path(os.environ.get("DATA_DIR", "/data")),
    )
    return make_comfyui_processor(
        client,
        checkpoint=os.environ.get("SD_CHECKPOINT", "anything-v5.safetensors"),
        steps=int(os.environ.get("SD_STEPS", "25")),
        cfg=float(os.environ.get("SD_CFG", "7")),
        width=int(os.environ.get("SD_WIDTH", "512")),
        height=int(os.environ.get("SD_HEIGHT", "512")),
    )


def build_worker(processor: Optional[ImageProcessor] = None) -> ImageWorker:
    import redis

    engine = create_db_engine()
    session_factory = make_session_factory(engine)
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
    return ImageWorker(
        session_factory,
        client,
        processor or _default_processor(),
        max_retries=int(os.environ.get("JOB_MAX_RETRIES", "1")),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    build_worker().run()


if __name__ == "__main__":
    main()
