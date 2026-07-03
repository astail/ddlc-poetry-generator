from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.characters import Character
from app.deps import get_generator, get_queue, get_session
from app.main import app
from app.models import Base, Job, Poem
from app.queue import InMemoryJobQueue
from app.schemas import PoemResult

from .conftest import SAMPLE_POEM


class _FakeGenerator:
    """Mirrors PoemGenerator: returns a PoemResult with character forced."""

    config = SimpleNamespace(model="test-model")

    def generate(self, character, theme=None):
        result = PoemResult.model_validate(dict(SAMPLE_POEM))
        result.character = Character(character).value
        return result


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    queue = InMemoryJobQueue()

    def _override_session():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_generator] = _FakeGenerator
    app.dependency_overrides[get_queue] = lambda: queue

    c = TestClient(app)
    c.session_local = SessionLocal
    c.queue = queue
    yield c
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_generate_returns_bilingual_poem_and_enqueues(client):
    r = client.post(
        "/api/generate",
        json={"character": "yuri", "theme": "the sea", "lang": "en"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["character"] == "yuri"
    assert body["poem_en"] and body["poem_ja"]  # bilingual
    assert body["title_ja"] == "潮汐"  # Japanese title round-trips (from SAMPLE_POEM)
    assert body["image_status"] == "pending"
    assert body["audio_status"] == "pending"

    # persisted: one poem (with its Japanese title), two jobs (image + audio)
    with client.session_local() as s:
        assert s.query(Poem).count() == 1
        assert s.query(Poem).one().title_ja == "潮汐"
        jobs = s.query(Job).all()
        assert {j.type for j in jobs} == {"image", "audio"}

    # enqueued one image and one audio job
    assert len(client.queue.items.get("image", [])) == 1
    assert len(client.queue.items.get("audio", [])) == 1


def test_generate_with_selected_model_sets_checkpoint(client):
    r = client.post(
        "/api/generate",
        json={"character": "yuri", "model": "AnythingXL_v50.safetensors"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["images"][0]["checkpoint"] == "AnythingXL_v50.safetensors"


def test_generate_default_model_when_omitted(client):
    r = client.post("/api/generate", json={"character": "yuri"})
    assert r.status_code == 200, r.text
    # Falls back to the configured default checkpoint (allow-listed).
    assert r.json()["images"][0]["checkpoint"] == "anything-v5.safetensors"


def test_generate_rejects_unknown_model(client):
    r = client.post(
        "/api/generate",
        json={"character": "yuri", "model": "../../etc/passwd"},
    )
    assert r.status_code == 422
    assert "unknown image model" in r.json()["detail"]


def test_generate_returns_503_when_at_concurrency_cap(client):
    import threading

    from app.deps import get_generation_semaphore
    from app.main import app

    sem = threading.BoundedSemaphore(1)
    app.dependency_overrides[get_generation_semaphore] = lambda: sem

    # Saturate the single slot (simulating a generation already in flight).
    assert sem.acquire(blocking=False) is True
    r = client.post("/api/generate", json={"character": "yuri"})
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "5"

    # Freeing the slot lets the next request through again.
    sem.release()
    assert client.post("/api/generate", json={"character": "yuri"}).status_code == 200


def test_list_models_endpoint(client):
    body = client.get("/api/models").json()
    assert body["default"] == "anything-v5.safetensors"
    names = {m["name"] for m in body["models"]}
    assert "AnythingXL_v50.safetensors" in names
    anyxl = next(m for m in body["models"] if m["name"] == "AnythingXL_v50.safetensors")
    assert anyxl["type"] == "sdxl"


def test_generate_image_only_skips_audio(client):
    r = client.post(
        "/api/generate",
        json={"character": "yuri", "generate_image": True, "generate_audio": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["image_status"] == "pending"
    assert body["audio_status"] is None
    assert len(body["images"]) == 1
    assert body["audios"] == []

    with client.session_local() as s:
        assert {j.type for j in s.query(Job).all()} == {"image"}
    assert len(client.queue.items.get("image", [])) == 1
    assert len(client.queue.items.get("audio", [])) == 0


def test_generate_audio_only_skips_image(client):
    r = client.post(
        "/api/generate",
        json={"character": "yuri", "generate_image": False, "generate_audio": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audio_status"] == "pending"
    assert body["image_status"] is None
    assert len(body["audios"]) == 1
    assert body["images"] == []

    with client.session_local() as s:
        assert {j.type for j in s.query(Job).all()} == {"audio"}
    assert len(client.queue.items.get("audio", [])) == 1
    assert len(client.queue.items.get("image", [])) == 0


def test_generate_both_explicit_flags(client):
    r = client.post(
        "/api/generate",
        json={"character": "yuri", "generate_image": True, "generate_audio": True},
    )
    assert r.status_code == 200, r.text
    with client.session_local() as s:
        assert {j.type for j in s.query(Job).all()} == {"image", "audio"}


def test_generate_omitting_flags_is_backward_compatible(client):
    # No flags supplied -> both assets generated, as before.
    r = client.post("/api/generate", json={"character": "monika"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["image_status"] == "pending"
    assert body["audio_status"] == "pending"
    with client.session_local() as s:
        assert {j.type for j in s.query(Job).all()} == {"image", "audio"}


def test_invalid_character_is_422(client):
    r = client.post("/api/generate", json={"character": "player", "theme": "x"})
    assert r.status_code == 422


def test_theme_too_long_is_422(client):
    r = client.post("/api/generate", json={"character": "monika", "theme": "x" * 500})
    assert r.status_code == 422


def test_rate_limit_returns_429(client):
    from app.deps import get_rate_limiter
    from app.main import app
    from app.ratelimit import RateLimiter

    limiter = RateLimiter(2, 60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    body = {"character": "yuri", "theme": "x"}
    assert client.post("/api/generate", json=body).status_code == 200
    assert client.post("/api/generate", json=body).status_code == 200
    r = client.post("/api/generate", json=body)
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}


def test_generation_error_returns_502(client):
    from app.claude_client import PoemGenerationError
    from app.deps import get_generator
    from app.main import app

    class _Boom:
        config = SimpleNamespace(model="m")

        def generate(self, character, theme=None):
            raise PoemGenerationError("claude down")

    app.dependency_overrides[get_generator] = _Boom
    r = client.post("/api/generate", json={"character": "monika"})
    assert r.status_code == 502
    assert "failed" in r.json()["detail"]


def test_stats_counts(client):
    client.post("/api/generate", json={"character": "yuri"})
    client.post("/api/generate", json={"character": "yuri"})
    client.post("/api/generate", json={"character": "monika"})
    s = client.get("/api/stats").json()
    assert s["total_poems"] == 3
    assert s["by_character"]["yuri"] == 2
    assert s["by_character"]["monika"] == 1


def test_api_key_required_when_configured(client):
    from app.deps import get_api_auth_token
    from app.main import app

    app.dependency_overrides[get_api_auth_token] = lambda: "secret"
    body = {"character": "sayori"}
    assert client.post("/api/generate", json=body).status_code == 401
    assert (
        client.post("/api/generate", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    )
    assert (
        client.post("/api/generate", json=body, headers={"X-API-Key": "secret"}).status_code == 200
    )


def test_open_when_no_token_configured(client):
    assert client.post("/api/generate", json={"character": "natsuki"}).status_code == 200


def test_stats_requires_api_key_when_configured(client):
    from app.deps import get_api_auth_token
    from app.main import app

    app.dependency_overrides[get_api_auth_token] = lambda: "secret"
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/stats", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/stats", headers={"X-API-Key": "secret"}).status_code == 200


def test_stats_open_when_no_token_configured(client):
    # No API_AUTH_TOKEN -> require_api_key is a no-op and /api/stats stays public.
    assert client.get("/api/stats").status_code == 200
