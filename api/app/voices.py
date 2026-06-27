"""Per-character voice profiles for TTS (issue #15).

Maps a character + language to a Piper voice plus synthesis parameters so the
four characters are audibly distinct. Piper has no direct pitch control, so we
differentiate pacing (length_scale) and expressiveness (noise_scale); the
voice model can also be swapped per character. Stronger pitch/timbre control
comes with XTTS (#16).
"""

from __future__ import annotations

from dataclasses import dataclass

# Default Piper voice (downloaded on first use). Override per-character below.
_EN_VOICE = "en_US-amy-low"


@dataclass(frozen=True)
class VoiceProfile:
    voice: str
    length_scale: float  # >1 slower, <1 faster
    noise_scale: float   # expressiveness


# character -> profile. length_scale/noise_scale tuned to each persona's pacing.
_PROFILES: dict[str, VoiceProfile] = {
    "sayori": VoiceProfile(_EN_VOICE, length_scale=1.0, noise_scale=0.667),
    "natsuki": VoiceProfile(_EN_VOICE, length_scale=0.85, noise_scale=0.75),
    "yuri": VoiceProfile(_EN_VOICE, length_scale=1.2, noise_scale=0.6),
    "monika": VoiceProfile(_EN_VOICE, length_scale=1.0, noise_scale=0.6),
}

_FALLBACK = VoiceProfile(_EN_VOICE, length_scale=1.0, noise_scale=0.667)


def get_voice_profile(character: str | None, lang: str = "en") -> VoiceProfile:
    """Return the voice profile for a character (lang reserved for ja voices)."""
    return _PROFILES.get((character or "").lower(), _FALLBACK)
