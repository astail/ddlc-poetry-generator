"""DATABASE_URL resolution + engine liveness check (#125)."""

from __future__ import annotations

import pytest

from app.db import DEFAULT_URL, create_db_engine, get_database_url


def test_explicit_database_url_wins():
    url = "postgresql+psycopg://u:p@host:5432/db"
    assert get_database_url({"DATABASE_URL": url}) == url
    # even under production, an explicit URL is honoured
    assert get_database_url({"APP_ENV": "production", "DATABASE_URL": url}) == url


def test_dev_falls_back_to_in_memory_sqlite():
    assert get_database_url({}) == DEFAULT_URL
    assert get_database_url({"APP_ENV": "development"}) == DEFAULT_URL


def test_production_without_database_url_fails_fast():
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        get_database_url({"APP_ENV": "production"})
    # empty string counts as unset
    with pytest.raises(RuntimeError):
        get_database_url({"APP_ENV": "Production", "DATABASE_URL": ""})


def test_create_db_engine_enables_pool_pre_ping_by_default():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    try:
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


def test_create_db_engine_pre_ping_is_overridable():
    engine = create_db_engine("sqlite+pysqlite:///:memory:", pool_pre_ping=False)
    try:
        assert engine.pool._pre_ping is False
    finally:
        engine.dispose()
