"""DB-level CHECK constraints reject invalid enum values (#123).

The StrEnums (plus Character / LANGS) are mirrored as CHECK constraints on the
tables, so an invalid status/type/lang/character/backend is rejected by the
database itself — not only the application layer. Verified here on SQLite, which
enforces CHECK constraints the same way PostgreSQL does.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.characters import Character
from app.models import AssetStatus, Audio, Base, Image, Job, JobStatus, JobType, Poem, TtsBackend


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _valid_poem(**overrides) -> Poem:
    base = dict(character="yuri", title="t", poem_en="e", poem_ja="j")
    base.update(overrides)
    return Poem(**base)


def test_rejects_invalid_character():
    Session = _session()
    with Session() as s:
        s.add(_valid_poem(character="villain"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_rejects_invalid_lang():
    Session = _session()
    with Session() as s:
        s.add(_valid_poem(lang="fr"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_rejects_invalid_image_status():
    Session = _session()
    with Session() as s:
        poem = _valid_poem()
        poem.images.append(Image(prompt="p", status="bogus"))
        s.add(poem)
        with pytest.raises(IntegrityError):
            s.commit()


def test_rejects_invalid_audio_backend():
    Session = _session()
    with Session() as s:
        poem = _valid_poem()
        poem.audios.append(Audio(backend="espeak"))
        s.add(poem)
        with pytest.raises(IntegrityError):
            s.commit()


def test_rejects_invalid_job_type():
    Session = _session()
    with Session() as s:
        s.add(Job(type="text", ref_id=1))
        with pytest.raises(IntegrityError):
            s.commit()


def test_rejects_invalid_job_status():
    Session = _session()
    with Session() as s:
        s.add(Job(type="image", ref_id=1, status="paused"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_accepts_every_declared_enum_value():
    """Sanity: each value the app actually uses passes the new constraints."""
    Session = _session()
    with Session() as s:
        for c in Character:
            s.add(_valid_poem(character=c.value))
        s.commit()
    with Session() as s:
        poem = _valid_poem()
        for st in AssetStatus:
            poem.images.append(Image(prompt="p", status=st.value))
        for b in TtsBackend:
            poem.audios.append(Audio(backend=b.value, lang="ja"))
        s.add(poem)
        s.commit()
    with Session() as s:
        for jt in JobType:
            for js in JobStatus:
                s.add(Job(type=jt.value, ref_id=1, status=js.value))
        s.commit()
