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
    assert body["image_status"] == "pending"
    assert body["audio_status"] == "pending"

    # persisted: one poem, two jobs (image + audio)
    with client.session_local() as s:
        assert s.query(Poem).count() == 1
        jobs = s.query(Job).all()
        assert {j.type for j in jobs} == {"image", "audio"}

    # enqueued one image and one audio job
    assert len(client.queue.items.get("image", [])) == 1
    assert len(client.queue.items.get("audio", [])) == 1


def test_invalid_character_is_422(client):
    r = client.post("/api/generate", json={"character": "player", "theme": "x"})
    assert r.status_code == 422


def test_theme_too_long_is_422(client):
    r = client.post(
        "/api/generate", json={"character": "monika", "theme": "x" * 500}
    )
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
