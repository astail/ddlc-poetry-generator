"""Persistence helpers for generated poems."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Audio, Image, Job, JobType, Poem
from .schemas import PoemResult


def persist_poem(
    session: Session,
    result: PoemResult,
    *,
    theme: Optional[str] = None,
    lang: str = "en",
    model: Optional[str] = None,
) -> tuple[Poem, list[Job]]:
    """Create the Poem plus its pending Image/Audio assets and their Jobs.

    Returns the persisted Poem and the two queued Jobs (image, audio).
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
    image = Image(prompt=result.image_prompt, negative=result.image_negative)
    audio = Audio(lang=lang)
    poem.images.append(image)
    poem.audios.append(audio)

    session.add(poem)
    session.flush()  # assign ids

    image_job = Job(type=JobType.IMAGE, ref_id=image.id)
    audio_job = Job(type=JobType.AUDIO, ref_id=audio.id)
    session.add_all([image_job, audio_job])
    session.commit()
    session.refresh(poem)
    return poem, [image_job, audio_job]


def get_poems(
    session: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    character: Optional[str] = None,
) -> list[Poem]:
    stmt = select(Poem)
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
