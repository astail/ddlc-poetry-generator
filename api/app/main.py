"""FastAPI application entrypoint (issue #6)."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .characters import Character
from .claude_client import PoemGenerator
from .deps import get_generator, get_queue, get_session
from .queue import JobQueue
from .service import GenerationService

app = FastAPI(title="DDLC Poetry Generator API")


class GenerateRequest(BaseModel):
    character: Character
    theme: Optional[str] = Field(default=None, max_length=200)
    lang: str = Field(default="en", pattern="^(en|ja)$")


class PoemResponse(BaseModel):
    id: int
    character: str
    title: str
    poem_en: str
    poem_ja: str
    mood: Optional[str]
    lang: str
    image_status: str
    audio_status: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/generate", response_model=PoemResponse)
def generate(
    req: GenerateRequest,
    session: Session = Depends(get_session),
    generator: PoemGenerator = Depends(get_generator),
    queue: JobQueue = Depends(get_queue),
) -> PoemResponse:
    service = GenerationService(generator, queue)
    poem = service.generate(session, req.character, req.theme, req.lang)
    return PoemResponse(
        id=poem.id,
        character=poem.character,
        title=poem.title,
        poem_en=poem.poem_en,
        poem_ja=poem.poem_ja,
        mood=poem.mood,
        lang=poem.lang,
        image_status=poem.images[0].status,
        audio_status=poem.audios[0].status,
    )
