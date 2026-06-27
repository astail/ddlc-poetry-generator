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
from .worker_common import ack, handle_job_failure, reap_stuck, reliable_pop

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
        """Block for one job; return True if one was consumed, False on timeout.

        The id is moved onto the processing list while in flight (reliable_pop)
        and only acked once handled. A retryable failure re-enqueues *after* the
        status is committed by ``process`` (and before the ack), so a crash can
        never drop the job — at worst it is reprocessed (at-least-once).
        """
        raw = reliable_pop(self._redis, "image", self._block_timeout)
        if raw is None:
            return False
        try:
            job_id = int(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
        except (ValueError, AttributeError):
            logger.error("invalid job id on queue: %r", raw)
            ack(self._redis, "image", raw)
            return True
        requeue = self.process(job_id)
        if requeue:
            self._redis.rpush(queue_key("image"), job_id)
        ack(self._redis, "image", raw)
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

            image = session.get(Image, job.ref_id)
            if image is None:
                job.status = JobStatus.FAILED
                job.error = "image not found"
                session.commit()
                return False

            job.status = JobStatus.RUNNING
            image.status = AssetStatus.RUNNING
            session.commit()

            requeue = False
            try:
                path = self._processor(image)
                image.path = path
                image.status = AssetStatus.DONE
                job.status = JobStatus.DONE
                job.error = None
            except Exception as exc:  # noqa: BLE001 - record failure, keep looping
                requeue = handle_job_failure(
                    self._redis,
                    job,
                    image,
                    exc,
                    job_type="image",
                    max_retries=self._max_retries,
                )
                logger.exception("image job %s failed", job_id)
            session.commit()
            return requeue

    def run(self) -> None:
        logger.info("image worker started (queue=%s)", queue_key("image"))
        reap_stuck(self._redis, "image")
        while True:
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - never let the loop die
                logger.exception("worker loop error")
                time.sleep(1)


def _default_processor() -> ImageProcessor:
    from pathlib import Path

    from .comfyui_client import ComfyUIClient, make_comfyui_processor, workflow_for

    model_type = os.environ.get("SD_MODEL_TYPE", "sd15").lower()
    is_sdxl = model_type == "sdxl"
    default_size = "1024" if is_sdxl else "512"
    default_steps = "30" if is_sdxl else "25"
    default_ckpt = "sdxl.safetensors" if is_sdxl else "anything-v5.safetensors"

    client = ComfyUIClient(
        os.environ.get("COMFYUI_URL", "http://comfyui:8188"),
        data_dir=Path(os.environ.get("DATA_DIR", "/data")),
        workflow=workflow_for(model_type),
    )
    return make_comfyui_processor(
        client,
        checkpoint=os.environ.get("SD_CHECKPOINT", default_ckpt),
        steps=int(os.environ.get("SD_STEPS", default_steps)),
        cfg=float(os.environ.get("SD_CFG", "7")),
        width=int(os.environ.get("SD_WIDTH", default_size)),
        height=int(os.environ.get("SD_HEIGHT", default_size)),
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
