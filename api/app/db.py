"""Database engine / session helpers."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

DEFAULT_URL = "sqlite+pysqlite:///:memory:"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def create_db_engine(url: str | None = None, **kwargs) -> Engine:
    return create_engine(url or get_database_url(), **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
