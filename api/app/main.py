"""FastAPI application entrypoint (issues #6, #7)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .assets import resolve_under
from .characters import Character
from .claude_client import PoemGenerationError, PoemGenerator
from .deps import (
    get_api_auth_token,
    get_data_dir,
    get_generator,
    get_queue,
    get_rate_limiter,
    get_session,
)
from .models import Poem
from .queue import JobQueue
from .ratelimit import RateLimiter
from .repository import get_poem, get_poems, get_stats
from .service import GenerationService

app = FastAPI(title="DDLC Poetry Generator API")


def enforce_rate_limit(
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
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
    if token and x_api_key != token:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


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


# ---------------------------------------------------------------- response models
class ImageOut(BaseModel):
    id: int
    status: str
    path: Optional[str]
    url: Optional[str] = None
    width: int
    height: int
    seed: Optional[int]


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


@app.get("/api/stats")
def stats(session: Session = Depends(get_session)) -> dict:
    return get_stats(session)


@app.post(
    "/api/generate",
    response_model=PoemDetail,
    dependencies=[Depends(enforce_rate_limit), Depends(require_api_key)],
)
def generate(
    req: GenerateRequest,
    session: Session = Depends(get_session),
    generator: PoemGenerator = Depends(get_generator),
    queue: JobQueue = Depends(get_queue),
) -> PoemDetail:
    service = GenerationService(generator, queue)
    poem = service.generate(session, req.character, req.theme, req.lang)
    return _detail(poem)


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
