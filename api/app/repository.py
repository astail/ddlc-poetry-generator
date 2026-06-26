"""Persistence helpers for generated poems."""

from __future__ import annotations

from typing import Optional

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
