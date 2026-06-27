"""Database models (docs/SPEC.md §6).

Status / type values are kept as plain string columns (portable across
SQLite and PostgreSQL); the StrEnums below are the source of allowed values
for the application and workers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class JobType(StrEnum):
    IMAGE = "image"
    AUDIO = "audio"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AssetStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TtsBackend(StrEnum):
    PIPER = "piper"
    XTTS = "xtts"


class Poem(Base):
    __tablename__ = "poems"

    id: Mapped[int] = mapped_column(primary_key=True)
    character: Mapped[str] = mapped_column(String(32), index=True)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    lang: Mapped[str] = mapped_column(String(8), default="en")
    title: Mapped[str] = mapped_column(Text)
    poem_en: Mapped[str] = mapped_column(Text)
    poem_ja: Mapped[str] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    images: Mapped[list["Image"]] = relationship(
        back_populates="poem", cascade="all, delete-orphan"
    )
    audios: Mapped[list["Audio"]] = relationship(
        back_populates="poem", cascade="all, delete-orphan"
    )


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    poem_id: Mapped[int] = mapped_column(ForeignKey("poems.id", ondelete="CASCADE"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    negative: Mapped[str] = mapped_column(Text, default="")
    checkpoint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int] = mapped_column(Integer, default=512)
    height: Mapped[int] = mapped_column(Integer, default=512)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=AssetStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    poem: Mapped[Poem] = relationship(back_populates="images")


class Audio(Base):
    __tablename__ = "audios"

    id: Mapped[int] = mapped_column(primary_key=True)
    poem_id: Mapped[int] = mapped_column(ForeignKey("poems.id", ondelete="CASCADE"), index=True)
    backend: Mapped[str] = mapped_column(String(16), default=TtsBackend.PIPER)
    voice: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lang: Mapped[str] = mapped_column(String(8), default="en")
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=AssetStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    poem: Mapped[Poem] = relationship(back_populates="audios")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16), index=True)
    ref_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
