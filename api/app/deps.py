"""FastAPI dependency providers (overridable in tests)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from .claude_client import PoemGenerator
from .db import create_db_engine, make_session_factory
from .queue import JobQueue, RedisJobQueue


@lru_cache
def _session_factory():
    return make_session_factory(create_db_engine())


def get_session() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def get_generator() -> PoemGenerator:
    return PoemGenerator()


@lru_cache
def get_queue() -> JobQueue:
    return RedisJobQueue.from_env()


def get_data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))
