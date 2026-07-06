"""Database engine / session helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# Dev/test convenience ONLY. In production DATABASE_URL must be set (see
# get_database_url): a silent in-memory SQLite would lose all data on restart and
# leave the api and each worker on their own throwaway DB that never share state.
DEFAULT_URL = "sqlite+pysqlite:///:memory:"


def get_database_url(env: Mapping[str, str] | None = None) -> str:
    """Resolve the database URL.

    Returns ``DATABASE_URL`` when set. When it is *not* set we fall back to an
    in-memory SQLite for local dev / tests — but that fallback is a data-loss
    footgun in production (every process gets its own throwaway DB), so when
    ``APP_ENV=production`` a missing ``DATABASE_URL`` fails fast instead, mirroring
    the compose password fail-fast rather than silently "working".
    """
    env = env if env is not None else os.environ
    url = env.get("DATABASE_URL")
    if url:
        return url
    if env.get("APP_ENV", "").strip().lower() == "production":
        raise RuntimeError(
            "DATABASE_URL is not set but APP_ENV=production. Set DATABASE_URL "
            "(docker compose provides it from POSTGRES_*); refusing to fall back "
            "to a throwaway in-memory SQLite in production."
        )
    return DEFAULT_URL


def create_db_engine(url: str | None = None, **kwargs) -> Engine:
    """Create an Engine with a liveness check on pooled connections.

    ``pool_pre_ping`` issues a cheap ``SELECT 1`` on checkout so a connection the
    database or a proxy dropped after an idle period is transparently replaced,
    instead of surfacing as a stale-connection error on the next query. Harmless
    for SQLite; important for Postgres / managed DBs. Callers can override it.
    """
    kwargs.setdefault("pool_pre_ping", True)
    return create_engine(url or get_database_url(), **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
