"""Request-id propagation, structured logging, and optional error tracking (#128).

Gives the async pipeline (api -> redis -> worker -> comfyui/tts) a correlation id
and an optional JSON log format, so a single request/job can be followed across
services. Everything is opt-in and dependency-free when disabled.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from contextvars import ContextVar

# Correlation id for the current request (API) or job (workers); "-" when unset.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attach the current request/job id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter (no external dependency)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(env: Mapping[str, str] | None = None) -> None:
    """Configure root logging once (idempotent).

    ``LOG_FORMAT=json`` switches to JSON output; anything else keeps a plain-text
    format that still includes the request id. ``LOG_LEVEL`` sets the level.
    """
    env = env if env is not None else os.environ
    level = getattr(logging, env.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    if env.get("LOG_FORMAT", "plain").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]  # replace so repeated calls don't stack handlers
    root.setLevel(level)


def init_error_tracking(env: Mapping[str, str] | None = None) -> bool:
    """Opt-in Sentry init — only when ``SENTRY_DSN`` is set. Returns True if
    enabled. Zero overhead and no dependency when unset; if the DSN is set but
    ``sentry_sdk`` is not installed, warn rather than crash startup.
    """
    env = env if env is not None else os.environ
    dsn = env.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(env.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        )
        return True
    except Exception:  # noqa: BLE001 - telemetry must never break startup
        logging.getLogger(__name__).warning(
            "SENTRY_DSN is set but sentry_sdk is unavailable; skipping error tracking"
        )
        return False
