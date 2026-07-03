"""Prompt builders for poem generation (uses the personas from personas.py)."""

from __future__ import annotations

from typing import Optional

from .characters import Character
from .personas import PERSONAS

_SYSTEM_TEMPLATE = """\
You are a poetry generator for an unofficial, non-commercial Doki Doki \
Literature Club fan project.

Write an ORIGINAL poem in the voice of {name}, one of the club members.

Voice & craft:
- Style: {style}
- Diction: {vocabulary}
- Length: {length}
- Tone: {tone}
- Typical themes: {themes}

Hard rules:
- Produce a brand-new, ORIGINAL poem. Never copy, paraphrase, or quote existing
  DDLC poems, dialogue, or lyrics. This is non-commercial fan work.
- Respond with ONLY a single JSON object. No prose, no markdown, no code fences.
- Use exactly these keys:
  - "title": a short English title fitting {name}'s voice
  - "title_ja": a natural Japanese rendering of the title (kanji/kana, not
    romaji), matching "poem_ja" in register
  - "character": must be exactly "{value}"
  - "poem_en": the poem in natural English
  - "poem_ja": a faithful, natural Japanese translation (kanji/kana, not romaji)
  - "image_prompt": concrete English Danbooru-style tags plus a scene
    description for an anime-style Stable Diffusion model. Reflect the poem's
    imagery and this art direction: {image_direction}
  - "image_negative": negative-prompt tags (e.g. "lowres, bad anatomy, extra
    fingers, watermark, text")
  - "mood": one lowercase English word describing the overall mood
  - "voice_hints": an object with numeric "rate" (0.5-1.5) and "pitch" (-5..5).
    For {name}, aim around {voice}.
"""


def build_system_prompt(character: Character) -> str:
    persona = PERSONAS[character]
    return _SYSTEM_TEMPLATE.format(
        name=persona.name,
        value=character.value,
        style=persona.style,
        vocabulary=persona.vocabulary,
        length=persona.length,
        tone=persona.tone,
        themes=persona.themes,
        image_direction=persona.image_direction,
        voice=persona.voice,
    )


def build_user_prompt(character: Character, theme: Optional[str]) -> str:
    persona = PERSONAS[character]
    if theme:
        return f"Write a poem in {persona.name}'s voice about: {theme.strip()}"
    return f"Write a poem in {persona.name}'s voice on a theme that suits the character."
