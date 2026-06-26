"""Structured output schema for a generated poem (see docs/SPEC.md §5)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VoiceHints(BaseModel):
    """Hints for the TTS worker (issue #15)."""

    rate: float = 1.0
    pitch: float = 0.0


class PoemResult(BaseModel):
    """One generated poem plus image / voice metadata.

    The core poem fields (title, poem_en, poem_ja) are required; the rest carry
    defaults so a slightly-incomplete model response still validates.
    """

    title: str
    character: str = ""
    poem_en: str
    poem_ja: str
    image_prompt: str = ""
    image_negative: str = ""
    mood: str = "neutral"
    voice_hints: VoiceHints = Field(default_factory=VoiceHints)
