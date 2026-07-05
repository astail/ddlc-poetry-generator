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


def test_get_poems_avoids_n_plus_1():
    """get_poems eager-loads images/audios so the query count is constant.

    With selectinload it is 1 (poems) + 1 (images) + 1 (audios) = 3 regardless
    of how many rows are returned. Without it, _summary's images[0]/audios[0]
    access would lazy-load per row (1 + 2*N).
    """
    from sqlalchemy import event

    from app.repository import get_poems

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)

    with SessionLocal() as s:
        for i in range(5):
            poem = Poem(character="yuri", title=f"t{i}", poem_en="e", poem_ja="j", lang="en")
            poem.images.append(Image(prompt="p"))
            poem.audios.append(Audio(lang="en"))
            s.add(poem)
        s.commit()

    selects: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    with SessionLocal() as s:
        poems = get_poems(s, limit=100)
        # Touch the representative assets exactly as _summary does.
        touched = [(p.images[0].status, p.audios[0].status) for p in poems]

    assert len(touched) == 5
    assert len(selects) == 3, selects


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


def test_title_ja_exposed_in_list_and_detail(client):
    with client.session_local() as s:
        with_ja = Poem(
            character="yuri", title="Tidewater", title_ja="潮汐", poem_en="e", poem_ja="j"
        )
        without_ja = Poem(character="natsuki", title="Cupcakes", poem_en="e", poem_ja="j")
        s.add_all([with_ja, without_ja])
        s.commit()
        ja_id = with_ja.id

    by_id = {p["id"]: p for p in client.get("/api/poems").json()}
    assert by_id[ja_id]["title_ja"] == "潮汐"
    # A poem without a Japanese title returns null (frontend falls back to title).
    assert all(p["title_ja"] is None for p in by_id.values() if p["id"] != ja_id)

    detail = client.get(f"/api/poems/{ja_id}").json()
    assert detail["title"] == "Tidewater"
    assert detail["title_ja"] == "潮汐"


def test_asset_serving(client, tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "x.txt").write_text("hello")
    app.dependency_overrides[get_data_dir] = lambda: tmp_path
    try:
        r = client.get("/api/assets/images/x.txt")
        assert r.status_code == 200
        assert r.text == "hello"
        assert r.headers["x-content-type-options"] == "nosniff"  # served asset (#118)
        assert client.get("/api/assets/images/missing.txt").status_code == 404
    finally:
        app.dependency_overrides.pop(get_data_dir, None)


def test_security_headers_applied_to_all_responses(client):
    """The nosniff header is a blanket middleware, so JSON endpoints get it too."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"


def test_tts_capabilities_default_piper(client, monkeypatch):
    # Default Piper backend without VOICEVOX: ja is not voiceable (#89).
    monkeypatch.delenv("TTS_BACKEND", raising=False)
    monkeypatch.delenv("VOICEVOX_URL", raising=False)
    r = client.get("/api/tts/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "piper"
    assert body["voicevox"] is False
    assert body["langs"] == ["en"]


def test_tts_capabilities_voicevox_enables_ja(client, monkeypatch):
    # Wiring up VOICEVOX makes Japanese audio available on any base backend.
    monkeypatch.delenv("TTS_BACKEND", raising=False)
    monkeypatch.setenv("VOICEVOX_URL", "http://voicevox:50021")
    r = client.get("/api/tts/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["voicevox"] is True
    assert set(body["langs"]) == {"en", "ja"}


def test_tts_capabilities_xtts_enables_ja(client, monkeypatch):
    monkeypatch.setenv("TTS_BACKEND", "xtts")
    monkeypatch.delenv("VOICEVOX_URL", raising=False)
    r = client.get("/api/tts/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "xtts"
    assert set(body["langs"]) == {"en", "ja"}


def test_resolve_under_blocks_traversal(tmp_path):
    assert resolve_under(tmp_path, "a/b.txt") is not None
    assert resolve_under(tmp_path, "../etc/passwd") is None


def test_asset_url_helper():
    from app.main import _asset_url

    assert _asset_url("images", None) is None
    assert _asset_url("images", "/data/images/abc_x.png") == "/api/assets/images/abc_x.png"
    assert _asset_url("audio", "/data/audio/5.wav") == "/api/assets/audio/5.wav"


def test_list_exposes_asset_urls(client):
    with client.session_local() as s:
        poem = Poem(character="yuri", title="t", poem_en="e", poem_ja="j", lang="en")
        poem.images.append(Image(prompt="p", path="/data/images/g.png", status="done"))
        poem.audios.append(Audio(lang="en", path="/data/audio/g.wav", status="done"))
        s.add(poem)
        s.commit()
    item = client.get("/api/poems").json()[0]
    assert item["image_url"] == "/api/assets/images/g.png"
    assert item["audio_url"] == "/api/assets/audio/g.wav"


def test_detail_exposes_image_url(client):
    with client.session_local() as s:
        poem = Poem(character="yuri", title="t", poem_en="e", poem_ja="j", lang="en")
        poem.images.append(Image(prompt="p", path="/data/images/done.png", status="done"))
        poem.audios.append(Audio(lang="en"))
        s.add(poem)
        s.commit()
        pid = poem.id

    d = client.get(f"/api/poems/{pid}").json()
    assert d["images"][0]["url"] == "/api/assets/images/done.png"
    assert d["audios"][0]["url"] is None  # no path yet
