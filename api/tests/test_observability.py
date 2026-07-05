"""Request-id middleware + structured logging + opt-in error tracking (#128)."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from app.main import app
from app.observability import (
    JsonFormatter,
    RequestIdFilter,
    configure_logging,
    init_error_tracking,
    request_id_var,
)


def test_request_id_is_generated_and_returned():
    # /api/models needs no db/redis, so it exercises the middleware cleanly.
    r = TestClient(app).get("/api/models")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")


def test_request_id_is_echoed_when_supplied():
    r = TestClient(app).get("/api/models", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


def test_json_formatter_includes_request_id_and_message():
    token = request_id_var.set("rid-xyz")
    try:
        record = logging.LogRecord("n", logging.INFO, "p", 1, "hello %s", ("world",), None)
        RequestIdFilter().filter(record)
        out = json.loads(JsonFormatter().format(record))
        assert out["message"] == "hello world"
        assert out["request_id"] == "rid-xyz"
        assert out["level"] == "INFO"
    finally:
        request_id_var.reset(token)


def test_configure_logging_switches_format_without_stacking():
    configure_logging({"LOG_FORMAT": "json"})
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)

    configure_logging({"LOG_FORMAT": "plain"})
    assert len(root.handlers) == 1  # replaced, not stacked
    assert not isinstance(root.handlers[0].formatter, JsonFormatter)


def test_error_tracking_is_noop_without_dsn():
    assert init_error_tracking({}) is False
