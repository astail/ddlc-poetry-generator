"""FastAPI application entrypoint (issues #6, #7)."""

from __future__ import annotations

import hmac
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .assets import resolve_under
from .characters import Character
from .claude_client import PoemGenerationError, PoemGenerator
from .deps import (
    get_api_auth_token,
    get_data_dir,
    get_generation_semaphore,
    get_generator,
    get_queue,
    get_rate_limiter,
    get_session,
)
from .image_models import catalog as image_model_catalog
from .image_models import default_name as default_image_model
from .image_models import resolve as resolve_image_model
from .models import Poem
from .queue import JobQueue
from .ratelimit import RateLimiter
from .repository import get_poem, get_poems, get_stats
from .service import GenerationService
from .voices import supported_audio_langs

app = FastAPI(title="DDLC Poetry Generator API")

# Browser calls come from the frontend on a different origin (port 3000 vs the
# API's 8000, and often a LAN IP rather than localhost), so the app must answer
# CORS preflights or fetch() is blocked. Operators can pin exact origins via
# CORS_ALLOW_ORIGINS (comma-separated; "*" opts into wildcard). When unset, we
# allow loopback plus private-LAN (RFC1918) origins via regex — enough for
# self-hosting on a LAN, but not the public internet, so a malicious external
# site can't read the API from a victim's browser. Credentials stay off (the
# optional auth is the X-API-Key header, not cookies).
_cors_origins = [
    o.strip() for o in os.environ.get("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()
]
_PRIVATE_ORIGIN_RE = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|\[::1\]|"
    r"10(\.\d{1,3}){3}|"
    r"192\.168(\.\d{1,3}){2}|"
    r"172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2}"
    r")(:\d+)?$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=None if _cors_origins else _PRIVATE_ORIGIN_RE,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


def enforce_rate_limit(
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    # Identify the client by source IP. Behind a reverse proxy / Docker bridge
    # this is the gateway IP unless uvicorn runs with --proxy-headers (+ a
    # trusted --forwarded-allow-ips); we intentionally do NOT trust a raw
    # X-Forwarded-For header here, since that is client-spoofable. The limiter
    # itself bounds memory so unknown/abusive IPs can't grow state unbounded.
    key = request.client.host if request.client else "anon"
    allowed, retry_after = limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded, please slow down",
            headers={"Retry-After": str(retry_after)},
        )


def require_api_key(
    x_api_key: Optional[str] = Header(default=None),
    token: Optional[str] = Depends(get_api_auth_token),
) -> None:
    # Constant-time compare so the response time doesn't leak how many leading
    # characters of the shared secret matched (timing side-channel). Compare as
    # bytes: compare_digest on str rejects non-ASCII, so a non-ASCII X-API-Key
    # header would otherwise raise (500) instead of cleanly failing auth.
    if token and not hmac.compare_digest((x_api_key or "").encode(), token.encode()):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def enforce_generation_limit(
    semaphore: threading.BoundedSemaphore = Depends(get_generation_semaphore),
) -> Iterator[None]:
    # Bound concurrent generations so slow synchronous Claude calls can't
    # exhaust the threadpool (#59). Over the cap -> fast 503 instead of piling up
    # and starving reads. The slot is released after the response is sent.
    if not semaphore.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="server is busy generating; please retry shortly",
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        semaphore.release()


@app.exception_handler(PoemGenerationError)
async def _poem_generation_error(request: Request, exc: PoemGenerationError):
    return JSONResponse(
        status_code=502,
        content={"detail": "poem generation failed; please try again"},
    )


# ---------------------------------------------------------------- request models
class GenerateRequest(BaseModel):
    character: Character
    theme: Optional[str] = Field(default=None, max_length=200)
    lang: str = Field(default="en", pattern="^(en|ja)$")
    # Opt each asset in or out. Both default to True so existing callers that
    # omit the flags keep getting image + audio (backward compatible).
    generate_image: bool = True
    generate_audio: bool = True
    # Image checkpoint to use. None = the configured default. Validated against
    # the allow-list (#49); unknown names are rejected (422).
    model: Optional[str] = Field(default=None, max_length=200)
    # Optional extra positive-prompt tags supplied by the user, appended to the
    # model-generated image prompt (still gets the mandatory quality prefix and
    # base negative in the worker). Ignored when generate_image is false.
    image_prompt_extra: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------- response models
class ImageOut(BaseModel):
    id: int
    status: str
    path: Optional[str]
    url: Optional[str] = None
    width: int
    height: int
    seed: Optional[int]
    checkpoint: Optional[str] = None  # image model used / selected (#49)


class AudioOut(BaseModel):
    id: int
    backend: str
    lang: str
    status: str
    path: Optional[str]
    url: Optional[str] = None
    voice: Optional[str]


def _asset_url(kind: str, path: Optional[str]) -> Optional[str]:
    """Public URL for a stored asset (served by GET /api/assets/{kind}/{name})."""
    if not path:
        return None
    return f"/api/assets/{kind}/{os.path.basename(path)}"


class PoemSummary(BaseModel):
    id: int
    character: str
    title: str
    title_ja: Optional[str] = None
    mood: Optional[str]
    lang: str
    created_at: datetime
    image_status: Optional[str]
    audio_status: Optional[str]
    image_url: Optional[str] = None
    audio_url: Optional[str] = None


class PoemDetail(PoemSummary):
    theme: Optional[str]
    model: Optional[str]
    poem_en: str
    poem_ja: str
    images: list[ImageOut]
    audios: list[AudioOut]


def _summary(poem: Poem) -> PoemSummary:
    return PoemSummary(
        id=poem.id,
        character=poem.character,
        title=poem.title,
        title_ja=poem.title_ja,
        mood=poem.mood,
        lang=poem.lang,
        created_at=poem.created_at,
        image_status=poem.images[0].status if poem.images else None,
        audio_status=poem.audios[0].status if poem.audios else None,
        image_url=_asset_url("images", poem.images[0].path) if poem.images else None,
        audio_url=_asset_url("audio", poem.audios[0].path) if poem.audios else None,
    )


def _detail(poem: Poem) -> PoemDetail:
    return PoemDetail(
        **_summary(poem).model_dump(),
        theme=poem.theme,
        model=poem.model,
        poem_en=poem.poem_en,
        poem_ja=poem.poem_ja,
        images=[
            ImageOut(
                id=i.id,
                status=i.status,
                path=i.path,
                url=_asset_url("images", i.path),
                width=i.width,
                height=i.height,
                seed=i.seed,
                checkpoint=i.checkpoint,
            )
            for i in poem.images
        ],
        audios=[
            AudioOut(
                id=a.id,
                backend=a.backend,
                lang=a.lang,
                status=a.status,
                path=a.path,
                url=_asset_url("audio", a.path),
                voice=a.voice,
            )
            for a in poem.audios
        ],
    )


# ---------------------------------------------------------------- endpoints
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# /api/stats exposes aggregate usage (total poems, per-character counts, asset
# states). When an API key is configured it should not be world-readable, so it
# is guarded by the same key as /api/generate. With no key configured
# require_api_key is a no-op, keeping the endpoint open for local/self-hosting.
@app.get("/api/stats", dependencies=[Depends(require_api_key)])
def stats(session: Session = Depends(get_session)) -> dict:
    return get_stats(session)


@app.post(
    "/api/generate",
    response_model=PoemDetail,
    dependencies=[
        Depends(enforce_rate_limit),
        Depends(require_api_key),
        Depends(enforce_generation_limit),
    ],
)
def generate(
    req: GenerateRequest,
    session: Session = Depends(get_session),
    generator: PoemGenerator = Depends(get_generator),
    queue: JobQueue = Depends(get_queue),
) -> PoemDetail:
    # Validate the requested image model against the allow-list (rejects unknown
    # names / path injection). None resolves to the configured default.
    try:
        image_model = resolve_image_model(req.model).name
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown image model: {req.model}")
    service = GenerationService(generator, queue)
    poem = service.generate(
        session,
        req.character,
        req.theme,
        req.lang,
        generate_image=req.generate_image,
        generate_audio=req.generate_audio,
        image_checkpoint=image_model,
        image_prompt_extra=req.image_prompt_extra,
    )
    return _detail(poem)


@app.get("/api/models")
def list_models() -> dict:
    """Selectable image-generation models (for the frontend dropdown, #49)."""
    return {
        "default": default_image_model(),
        "models": [
            {"name": m.name, "label": m.label, "type": m.type} for m in image_model_catalog()
        ],
    }


@app.get("/api/tts/capabilities")
def tts_capabilities() -> dict:
    """TTS backend and the languages it can synthesize (#89).

    The frontend uses this to disable "音声を生成" for a language the active
    config can't voice (e.g. ja when VOICEVOX is not configured), so the user is
    told up front instead of getting a failed/garbled audio job. Japanese is
    available when VOICEVOX is wired up (``VOICEVOX_URL``).
    """
    backend = os.environ.get("TTS_BACKEND", "piper").lower()
    voicevox = bool(os.environ.get("VOICEVOX_URL"))
    langs = supported_audio_langs(backend, voicevox_enabled=voicevox)
    return {"backend": backend, "voicevox": voicevox, "langs": sorted(langs)}


@app.get("/api/poems", response_model=list[PoemSummary])
def list_poems(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    character: Optional[Character] = None,
    session: Session = Depends(get_session),
) -> list[PoemSummary]:
    poems = get_poems(
        session,
        limit=limit,
        offset=offset,
        character=character.value if character else None,
    )
    return [_summary(p) for p in poems]


@app.get("/api/poems/{poem_id}", response_model=PoemDetail)
def read_poem(
    poem_id: int,
    session: Session = Depends(get_session),
) -> PoemDetail:
    poem = get_poem(session, poem_id)
    if poem is None:
        raise HTTPException(status_code=404, detail="poem not found")
    return _detail(poem)


@app.get("/api/assets/{path:path}")
def get_asset(
    path: str,
    data_dir: Path = Depends(get_data_dir),
) -> FileResponse:
    target = resolve_under(data_dir, path)
    if target is None or not target.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(target)
