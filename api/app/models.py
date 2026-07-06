"""Database models (docs/SPEC.md §6).

Status / type values are kept as plain string columns (portable across SQLite
and PostgreSQL). The StrEnums below (plus Character / LANGS) are the source of
allowed values, and are mirrored as DB-level CHECK constraints (#123) so an
invalid status/type/lang/character/backend is rejected by the database itself,
not only the application layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from .characters import Character


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
    VOICEVOX = "voicevox"


# Allowed content languages (matches GenerateRequest's ^(en|ja)$ and audios.lang).
LANGS = ("en", "ja")


def _sql_in(column: str, values) -> str:
    """Build a portable ``col IN ('a','b',...)`` CHECK condition.

    The StrEnums above (plus Character / LANGS) are the single source of allowed
    values; the DB-level CHECK constraints below are generated from them so an
    invalid status/type/lang/character/backend is rejected by the database, not
    only by the application layer.
    """
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


_CHARACTERS = tuple(c.value for c in Character)
_ASSET_STATUSES = tuple(s.value for s in AssetStatus)
_JOB_STATUSES = tuple(s.value for s in JobStatus)
_JOB_TYPES = tuple(t.value for t in JobType)
_BACKENDS = tuple(b.value for b in TtsBackend)


class Poem(Base):
    __tablename__ = "poems"
    __table_args__ = (
        CheckConstraint(_sql_in("character", _CHARACTERS), name="ck_poems_character"),
        CheckConstraint(_sql_in("lang", LANGS), name="ck_poems_lang"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character: Mapped[str] = mapped_column(String(32), index=True)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    lang: Mapped[str] = mapped_column(String(8), default="en")
    title: Mapped[str] = mapped_column(Text)
    title_ja: Mapped[str | None] = mapped_column(Text, nullable=True)
    poem_en: Mapped[str] = mapped_column(Text)
    poem_ja: Mapped[str] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # order_by makes images[0] / audios[0] (used as the "representative" asset
    # in API responses) deterministic instead of relying on undefined relation
    # ordering.
    images: Mapped[list[Image]] = relationship(
        back_populates="poem", cascade="all, delete-orphan", order_by="Image.id"
    )
    audios: Mapped[list[Audio]] = relationship(
        back_populates="poem", cascade="all, delete-orphan", order_by="Audio.id"
    )


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (CheckConstraint(_sql_in("status", _ASSET_STATUSES), name="ck_images_status"),)

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
    __table_args__ = (
        CheckConstraint(_sql_in("backend", _BACKENDS), name="ck_audios_backend"),
        CheckConstraint(_sql_in("lang", LANGS), name="ck_audios_lang"),
        CheckConstraint(_sql_in("status", _ASSET_STATUSES), name="ck_audios_status"),
    )

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
    """Async work item for one asset (image/audio).

    ``jobs`` deliberately has **no** FK to images/audios: a job references its
    asset polymorphically by ``(type, ref_id)`` — ``ref_id`` points to *either* an
    image or an audio depending on ``type`` — which a single native FK cannot
    express. Referential cleanup is therefore explicit: ``repository.delete_poem``
    deletes a poem's jobs by ``(type, ref_id)`` alongside the cascaded asset rows,
    so no orphan job is left behind (covered by tests/test_repository.py). The
    composite ``(type, status)`` index backs the queue-scan / reconcile queries
    that filter on both columns.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(_sql_in("type", _JOB_TYPES), name="ck_jobs_type"),
        CheckConstraint(_sql_in("status", _JOB_STATUSES), name="ck_jobs_status"),
        Index("ix_jobs_type_status", "type", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16), index=True)
    ref_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
