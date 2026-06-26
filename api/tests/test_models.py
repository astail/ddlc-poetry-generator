from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.models import Audio, Base, Image, Job, JobStatus, JobType, Poem


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def test_all_tables_created():
    engine, _ = _session_factory()
    tables = set(inspect(engine).get_table_names())
    assert {"poems", "images", "audios", "jobs"} <= tables


def test_poem_with_relations_and_defaults():
    _, Session = _session_factory()
    with Session() as s:
        poem = Poem(
            character="yuri",
            theme="the sea",
            title="Tidewater",
            poem_en="en",
            poem_ja="ja",
            mood="melancholic",
            model="claude-sonnet-4-6",
        )
        poem.images.append(Image(prompt="1girl, purple hair", seed=42))
        poem.audios.append(Audio(backend="piper", lang="ja"))
        s.add(poem)
        s.commit()
        poem_id = poem.id
        image_id = poem.images[0].id

        s.add(Job(type=JobType.IMAGE, ref_id=image_id))
        s.commit()

    with Session() as s:
        p = s.get(Poem, poem_id)
        assert p is not None
        assert p.lang == "en"  # column default
        assert p.created_at is not None
        assert len(p.images) == 1 and len(p.audios) == 1
        assert p.images[0].status == "pending"
        assert p.images[0].width == 512
        assert p.audios[0].lang == "ja"

        job = s.query(Job).one()
        assert job.type == JobType.IMAGE
        assert job.status == JobStatus.QUEUED
        assert job.ref_id == image_id


def test_cascade_delete_removes_children():
    _, Session = _session_factory()
    with Session() as s:
        poem = Poem(character="sayori", title="t", poem_en="e", poem_ja="j")
        poem.images.append(Image(prompt="p"))
        poem.audios.append(Audio())
        s.add(poem)
        s.commit()

        s.delete(poem)
        s.commit()
        assert s.query(Image).count() == 0
        assert s.query(Audio).count() == 0
