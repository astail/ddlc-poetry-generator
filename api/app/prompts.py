"""Prompt builders for poem generation.

Minimal here; the rich per-character persona lives in issue #5.
"""

from __future__ import annotations

from typing import Optional

from .characters import CHARACTER_STYLES, Character

_SYSTEM_TEMPLATE = """\
You are a poetry generator for an unofficial, non-commercial Doki Doki \
Literature Club fan project.

Write an ORIGINAL poem in the style of {name}.
Style: {style}

Rules:
- Produce a brand-new, original poem. Do NOT copy or quote existing DDLC text.
- Respond with ONLY a single JSON object. No prose, no markdown, no code fences.
- Use exactly these keys:
  - "title": short title for the poem
  - "character": must be "{value}"
  - "poem_en": the poem in English
  - "poem_ja": a natural Japanese translation of the poem
  - "image_prompt": concrete English Danbooru-style tags / scene description for
    an anime-style Stable Diffusion model that fits the poem's imagery
  - "image_negative": negative-prompt tags (e.g. "lowres, bad anatomy")
  - "mood": one lowercase English word describing the mood
  - "voice_hints": an object with numeric "rate" (0.5-1.5) and "pitch" (-5..5)
"""


def build_system_prompt(character: Character) -> str:
    return _SYSTEM_TEMPLATE.format(
        name=character.value.title(),
        value=character.value,
        style=CHARACTER_STYLES[character],
    )


def build_user_prompt(character: Character, theme: Optional[str]) -> str:
    if theme:
        return f"Write a {character.value} poem about: {theme.strip()}"
    return f"Write a {character.value} poem on a theme that suits the character."
