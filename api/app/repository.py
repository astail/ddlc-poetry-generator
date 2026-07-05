"""Persistence helpers for generated poems."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .assets import resolve_under
from .models import Audio, Image, Job, JobType, Poem
from .schemas import PoemResult

logger = logging.getLogger(__name__)


def combine_image_prompt(base: str, extra: Optional[str]) -> str:
    """Append the user's optional extra tags to the model-generated image prompt.

    The mandatory quality prefix is added later in the worker, so this only joins
    the model's tags with the user's (comma-separated). Blank/whitespace extras
    are ignored so an empty field never dirties the prompt.
    """
    extra = (extra or "").strip().rstrip(",").strip()
    base = (base or "").strip()
    if not extra:
        return base
    return f"{base}, {extra}" if base else extra


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
    image_prompt_extra: Optional[str] = None,
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
        title_ja=result.title_ja or None,
        poem_en=result.poem_en,
        poem_ja=result.poem_ja,
        mood=result.mood,
        model=model,
    )
    image = None
    audio = None
    if generate_image:
        image = Image(
            prompt=combine_image_prompt(result.image_prompt, image_prompt_extra),
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


def _remove_asset_file(data_dir: Path, kind: str, path: Optional[str]) -> None:
    """Best-effort delete of a generated asset file under ``data_dir/kind``.

    Mirrors how assets are served (``data_dir/<kind>/<basename>``) and reuses
    ``resolve_under`` to stay inside the data dir. A missing/removed file is not
    an error — the DB row is going away regardless.
    """
    if not path:
        return
    target = resolve_under(data_dir, f"{kind}/{os.path.basename(path)}")
    if target is not None and target.is_file():
        try:
            target.unlink()
        except OSError:
            logger.warning("failed to remove asset file %s", target)


def delete_poem(session: Session, poem_id: int, data_dir: Path) -> bool:
    """Delete a poem, its asset rows/files, and its (FK-less) jobs.

    Returns False if the poem does not exist. Image/Audio rows cascade off the
    poem, but Job rows reference assets only by ``(type, ref_id)`` with no FK, so
    they are deleted explicitly here to avoid orphans.
    """
    poem = session.get(Poem, poem_id)
    if poem is None:
        return False

    for img in poem.images:
        _remove_asset_file(data_dir, "images", img.path)
    for aud in poem.audios:
        _remove_asset_file(data_dir, "audio", aud.path)

    image_ids = [i.id for i in poem.images]
    audio_ids = [a.id for a in poem.audios]
    if image_ids:
        session.query(Job).filter(
            Job.type == JobType.IMAGE.value, Job.ref_id.in_(image_ids)
        ).delete(synchronize_session=False)
    if audio_ids:
        session.query(Job).filter(
            Job.type == JobType.AUDIO.value, Job.ref_id.in_(audio_ids)
        ).delete(synchronize_session=False)

    session.delete(poem)  # cascades to Image/Audio rows
    session.commit()
    return True


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
