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


class UnsupportedLanguageError(ValueError):
    """Raised when the Piper (CPU) backend has no voice for the requested language."""


# Languages the Piper (CPU) backend can synthesize. Piper ships only English
# voices here; Japanese is served by the XTTS backend instead (#50).
PIPER_LANGS = {"en"}

# Languages the XTTS (GPU) backend can synthesize that this app actually offers.
# XTTS v2 is multilingual (16 langs), but poems exist only in en/ja, so we expose
# just those — enough for the frontend to know ja audio is available (#50, #89).
XTTS_LANGS = {"en", "ja"}


def supported_audio_langs(backend: str, *, voicevox_enabled: bool = False) -> set[str]:
    """Languages that can currently produce audio, given the active config.

    Lets the API tell the frontend up front which languages can produce audio,
    so it can disable the option for unsupported langs instead of enqueuing a
    job that is bound to fail (#89). English comes from the base backend
    (Piper/XTTS); Japanese is available when VOICEVOX is configured (it voices
    ja regardless of the base backend) or when the multilingual XTTS backend is
    selected.
    """
    langs = set(XTTS_LANGS) if (backend or "").lower() == "xtts" else set(PIPER_LANGS)
    if voicevox_enabled:
        langs.add("ja")
    return langs


@dataclass(frozen=True)
class VoiceProfile:
    voice: str
    length_scale: float  # >1 slower, <1 faster
    noise_scale: float  # expressiveness


# character -> profile. length_scale/noise_scale tuned to each persona's pacing.
_PROFILES: dict[str, VoiceProfile] = {
    "sayori": VoiceProfile(_EN_VOICE, length_scale=1.0, noise_scale=0.667),
    "natsuki": VoiceProfile(_EN_VOICE, length_scale=0.85, noise_scale=0.75),
    "yuri": VoiceProfile(_EN_VOICE, length_scale=1.2, noise_scale=0.6),
    "monika": VoiceProfile(_EN_VOICE, length_scale=1.0, noise_scale=0.6),
}

_FALLBACK = VoiceProfile(_EN_VOICE, length_scale=1.0, noise_scale=0.667)


def get_voice_profile(character: str | None, lang: str = "en") -> VoiceProfile:
    """Return the Piper voice profile for a character + language.

    Piper (CPU) has only English voices, so a non-English ``lang`` raises
    ``UnsupportedLanguageError`` instead of silently synthesizing the text with
    an English voice (which produced garbled output for Japanese, #47/#50).
    Japanese is supported via the XTTS backend (TTS_BACKEND=xtts).
    """
    if lang and lang.lower() not in PIPER_LANGS:
        raise UnsupportedLanguageError(
            f"Piper (CPU) TTS has no '{lang}' voice; set TTS_BACKEND=xtts for Japanese (#50)"
        )
    return _PROFILES.get((character or "").lower(), _FALLBACK)
