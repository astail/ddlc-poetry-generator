"""Unit tests for repository helpers."""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Audio, Base, Image, Job, JobType, Poem
from app.repository import combine_image_prompt, delete_poem


def test_combine_appends_extra():
    assert combine_image_prompt("a, b", "c, d") == "a, b, c, d"


def test_combine_ignores_blank_or_none_extra():
    assert combine_image_prompt("a, b", "   ") == "a, b"
    assert combine_image_prompt("a, b", None) == "a, b"


def test_combine_trims_trailing_comma_and_whitespace():
    assert combine_image_prompt("a, b", "  c,  ") == "a, b, c"


def test_combine_uses_extra_only_when_base_empty():
    assert combine_image_prompt("", "c") == "c"


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(engine, expire_on_commit=False)
    s = session_local()
    try:
        yield s
    finally:
        s.close()


def _poem_with_assets(session, data_dir):
    """A persisted poem with an image + audio (real files on disk) and jobs."""
    (data_dir / "images").mkdir(parents=True, exist_ok=True)
    (data_dir / "audio").mkdir(parents=True, exist_ok=True)
    img_file = data_dir / "images" / "pic.png"
    img_file.write_bytes(b"img")
    aud_file = data_dir / "audio" / "voice.wav"
    aud_file.write_bytes(b"aud")

    poem = Poem(character="yuri", title="t", poem_en="e", poem_ja="j")
    poem.images.append(Image(prompt="p", path=str(img_file)))
    poem.audios.append(Audio(lang="en", path=str(aud_file)))
    session.add(poem)
    session.flush()
    session.add_all(
        [
            Job(type=JobType.IMAGE.value, ref_id=poem.images[0].id),
            Job(type=JobType.AUDIO.value, ref_id=poem.audios[0].id),
        ]
    )
    session.commit()
    return poem, img_file, aud_file


def test_delete_poem_removes_rows_files_and_jobs(session, tmp_path):
    poem, img_file, aud_file = _poem_with_assets(session, tmp_path)
    poem_id = poem.id

    assert delete_poem(session, poem_id, tmp_path) is True

    assert session.get(Poem, poem_id) is None
    assert session.query(Image).count() == 0  # cascaded off the poem
    assert session.query(Audio).count() == 0
    assert session.query(Job).count() == 0  # FK-less jobs removed explicitly
    assert not img_file.exists()  # files cleaned up
    assert not aud_file.exists()


def test_delete_missing_poem_returns_false(session, tmp_path):
    assert delete_poem(session, 999, tmp_path) is False


def test_delete_poem_tolerates_missing_files(session, tmp_path):
    poem, img_file, aud_file = _poem_with_assets(session, tmp_path)
    img_file.unlink()  # file already gone; delete must not raise
    assert delete_poem(session, poem.id, tmp_path) is True
    assert session.get(Poem, poem.id) is None


def test_delete_poem_leaves_other_poems_jobs_intact(session, tmp_path):
    """Deleting one poem removes only its jobs — no orphaned or collateral jobs
    for other poems (the FK-less jobs are cleaned up by (type, ref_id))."""
    poem_a, *_ = _poem_with_assets(session, tmp_path)
    poem_b, *_ = _poem_with_assets(session, tmp_path)
    b_image_ids = {i.id for i in poem_b.images}
    b_audio_ids = {a.id for a in poem_b.audios}
    assert session.query(Job).count() == 4

    assert delete_poem(session, poem_a.id, tmp_path) is True

    remaining = session.query(Job).all()
    assert len(remaining) == 2  # only poem_b's jobs survive
    for j in remaining:
        expected = b_image_ids if j.type == JobType.IMAGE.value else b_audio_ids
        assert j.ref_id in expected


def test_jobs_have_composite_type_status_index():
    """The (type, status) composite index backing queue/reconcile scans exists."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    names = {idx["name"] for idx in inspect(engine).get_indexes("jobs")}
    assert "ix_jobs_type_status" in names
