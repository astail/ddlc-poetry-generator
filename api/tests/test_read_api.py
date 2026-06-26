import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.assets import resolve_under
from app.deps import get_data_dir, get_session
from app.main import app
from app.models import Audio, Base, Image, Poem


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)

    def _override_session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override_session
    c = TestClient(app)
    c.session_local = SessionLocal
    yield c
    app.dependency_overrides.clear()


def _seed(SessionLocal):
    with SessionLocal() as s:
        for ch in ["yuri", "natsuki", "yuri"]:
            poem = Poem(
                character=ch, title=f"t-{ch}", poem_en="en", poem_ja="ja", lang="en", mood="m"
            )
            poem.images.append(Image(prompt="p"))
            poem.audios.append(Audio(lang="en"))
            s.add(poem)
        s.commit()


def test_list_poems_newest_first(client):
    _seed(client.session_local)
    r = client.get("/api/poems")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3
    assert body[0]["id"] > body[-1]["id"]
    assert body[0]["image_status"] == "pending"
    assert body[0]["audio_status"] == "pending"


def test_list_filter_and_paging(client):
    _seed(client.session_local)
    r = client.get("/api/poems", params={"character": "yuri"})
    assert [p["character"] for p in r.json()] == ["yuri", "yuri"]
    r2 = client.get("/api/poems", params={"limit": 1, "offset": 1})
    assert len(r2.json()) == 1


def test_get_poem_detail(client):
    _seed(client.session_local)
    pid = client.get("/api/poems").json()[0]["id"]
    r = client.get(f"/api/poems/{pid}")
    assert r.status_code == 200
    d = r.json()
    assert d["poem_en"] == "en" and d["poem_ja"] == "ja"
    assert len(d["images"]) == 1 and len(d["audios"]) == 1
    assert d["images"][0]["width"] == 512


def test_get_poem_404(client):
    assert client.get("/api/poems/9999").status_code == 404


def test_asset_serving(client, tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "x.txt").write_text("hello")
    app.dependency_overrides[get_data_dir] = lambda: tmp_path
    try:
        r = client.get("/api/assets/images/x.txt")
        assert r.status_code == 200
        assert r.text == "hello"
        assert client.get("/api/assets/images/missing.txt").status_code == 404
    finally:
        app.dependency_overrides.pop(get_data_dir, None)


def test_resolve_under_blocks_traversal(tmp_path):
    assert resolve_under(tmp_path, "a/b.txt") is not None
    assert resolve_under(tmp_path, "../etc/passwd") is None
