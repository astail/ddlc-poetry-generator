"""Persistence helpers for generated poems."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import Audio, Image, Job, JobType, Poem
from .schemas import PoemResult


def persist_poem(
    session: Session,
    result: PoemResult,
    *,
    theme: Optional[str] = None,
    lang: str = "en",
    model: Optional[str] = None,
    image_checkpoint: Optional[str] = None,
    generate_image: bool = True,
    generate_audio: bool = True,
) -> tuple[Poem, list[Job]]:
    """Create the Poem plus the selected pending Image/Audio assets and Jobs.

    ``generate_image`` / ``generate_audio`` opt each asset in or out: an asset
    (and its Job) is only created when its flag is set, so "image only",
    "audio only", and "both" all work. ``image_checkpoint`` pins which image
    model the worker should use (#49). Defaults keep both assets on for backward
    compatibility. Returns the persisted Poem and the queued Jobs.
    """
    poem = Poem(
        character=result.character,
        theme=theme,
        lang=lang,
        title=result.title,
        poem_en=result.poem_en,
        poem_ja=result.poem_ja,
        mood=result.mood,
        model=model,
    )
    image = None
    audio = None
    if generate_image:
        image = Image(
            prompt=result.image_prompt,
            negative=result.image_negative,
            checkpoint=image_checkpoint,
        )
        poem.images.append(image)
    if generate_audio:
        audio = Audio(lang=lang)
        poem.audios.append(audio)

    session.add(poem)
    session.flush()  # assign ids

    jobs: list[Job] = []
    if image is not None:
        jobs.append(Job(type=JobType.IMAGE, ref_id=image.id))
    if audio is not None:
        jobs.append(Job(type=JobType.AUDIO, ref_id=audio.id))
    session.add_all(jobs)
    session.commit()
    session.refresh(poem)
    return poem, jobs


def get_poems(
    session: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    character: Optional[str] = None,
) -> list[Poem]:
    # Eager-load the image/audio relations so _summary's images[0] / audios[0]
    # access doesn't fire a lazy query per row (was 1 + 2*N; now a constant 3).
    stmt = select(Poem).options(
        selectinload(Poem.images),
        selectinload(Poem.audios),
    )
    if character:
        stmt = stmt.where(Poem.character == character)
    stmt = stmt.order_by(Poem.id.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt))


def get_poem(session: Session, poem_id: int) -> Optional[Poem]:
    return session.get(Poem, poem_id)


def get_stats(session: Session) -> dict:
    total = session.scalar(select(func.count()).select_from(Poem)) or 0
    by_character = dict(
        session.execute(select(Poem.character, func.count()).group_by(Poem.character)).all()
    )
    images = dict(session.execute(select(Image.status, func.count()).group_by(Image.status)).all())
    audios = dict(session.execute(select(Audio.status, func.count()).group_by(Audio.status)).all())
    return {
        "total_poems": total,
        "by_character": by_character,
        "images": images,
        "audios": audios,
    }
