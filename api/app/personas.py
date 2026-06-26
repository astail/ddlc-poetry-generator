"""Per-character personas for poem generation (docs/SPEC.md §3).

Each Persona captures the character's writing style, diction, length, tone,
typical themes, an art direction for the image prompt, and a voice-hint target
for TTS. These drive the system prompt in ``prompts.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .characters import Character


@dataclass(frozen=True)
class Persona:
    name: str
    style: str
    vocabulary: str
    length: str
    tone: str
    themes: str
    image_direction: str
    voice: str  # human-readable target for voice_hints (rate / pitch)


PERSONAS: dict[Character, Persona] = {
    Character.SAYORI: Persona(
        name="Sayori",
        style=(
            "plain, conversational free verse that sounds spoken aloud; bright "
            "and sincere on the surface with an ache of loneliness underneath"
        ),
        vocabulary="simple, everyday words; little ornamentation",
        length="short, 8-14 lines",
        tone="warm, earnest, a little fragile",
        themes="friendship, sunshine, clouds, mornings, the gap between smiling and feeling okay",
        image_direction=(
            "warm soft lighting, pastel sky, coral/peach palette, gentle morning "
            "atmosphere, a hint of wistfulness"
        ),
        voice="rate 1.05, pitch +1 (light, warm, gently upbeat)",
    ),
    Character.NATSUKI: Persona(
        name="Natsuki",
        style=(
            "short, punchy, rhythmic lines with a cute, defiant edge; tsundere "
            "energy — sweet underneath a sharp front"
        ),
        vocabulary="casual, blunt, playful; exclamations and the occasional pout",
        length="very short, 6-10 punchy lines",
        tone="feisty, cute, secretly tender",
        themes="cupcakes and sweets, small everyday wins, manga, being underestimated",
        image_direction=(
            "pop pastel palette, pink tones, cute props (cupcakes, ribbons), "
            "bold clean lines, cheerful but with attitude"
        ),
        voice="rate 1.1, pitch +2 (quick, high, energetic)",
    ),
    Character.YURI: Persona(
        name="Yuri",
        style=(
            "ornate, dark, intricate verse with elaborate extended metaphor and "
            "rich imagery; introspective and intense"
        ),
        vocabulary="sophisticated, literary, sometimes archaic; sensory and precise",
        length="longer, 14-20 lines with flowing phrasing",
        tone="brooding, passionate, melancholic",
        themes="depths and oceans, candlelight, tea, books, knives, longing and obsession",
        image_direction=(
            "deep purples and dark tones, dramatic chiaroscuro lighting, candle "
            "or moonlight, gothic and atmospheric, fine detail"
        ),
        voice="rate 0.8, pitch -2 (slow, low, breathy)",
    ),
    Character.MONIKA: Persona(
        name="Monika",
        style=(
            "composed, articulate, philosophical free verse; self-aware and "
            "quietly meta, addressing the reader directly at times"
        ),
        vocabulary="clear, polished, thoughtful; balanced and deliberate",
        length="medium, 10-16 even lines",
        tone="confident, reflective, serene",
        themes="reality and perception, the self, the boundary between fiction and the reader, growth",
        image_direction=(
            "fresh greens, balanced and orderly composition, soft natural light, "
            "serene classroom or garden, a sense of calm clarity"
        ),
        voice="rate 1.0, pitch 0 (measured, clear, even)",
    ),
}
