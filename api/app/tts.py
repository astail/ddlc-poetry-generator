"""Piper TTS synthesizer (issue #14).

Synthesizes a poem's text to a WAV under DATA_DIR/audio using Piper (CPU).
Voice models are downloaded on first use into DATA_DIR/voices (not committed).
Per-character voice mapping is layered on in issue #15.
"""

from __future__ import annotations

import logging
import urllib.request
import wave
from pathlib import Path

from .models import Audio
from .voices import get_voice_profile

logger = logging.getLogger(__name__)

# Known Piper voices (rhasspy/piper-voices). Extended in #15.
_VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICE_URLS: dict[str, str] = {
    "en_US-amy-low": f"{_VOICE_BASE}/en/en_US/amy/low/en_US-amy-low.onnx",
    "en_US-amy-medium": f"{_VOICE_BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx",
}

# lang -> default voice name
DEFAULT_VOICES: dict[str, str] = {"en": "en_US-amy-low"}


class PiperSynthesizer:
    def __init__(
        self,
        data_dir: Path | str = "/data",
        voices: dict[str, str] | None = None,
        default_voice: str = "en_US-amy-low",
    ):
        self._data_dir = Path(data_dir)
        self._voices_dir = self._data_dir / "voices"
        self._lang_voices = voices or DEFAULT_VOICES
        self._default_voice = default_voice
        self._cache: dict[str, object] = {}

    def voice_for(self, lang: str) -> str:
        return self._lang_voices.get(lang, self._default_voice)

    def _ensure_voice(self, name: str) -> Path:
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        onnx = self._voices_dir / f"{name}.onnx"
        cfg = self._voices_dir / f"{name}.onnx.json"
        if onnx.exists() and cfg.exists():
            return onnx
        url = VOICE_URLS.get(name)
        if not url:
            raise ValueError(f"unknown Piper voice: {name}")
        logger.info("downloading Piper voice %s", name)
        urllib.request.urlretrieve(url, onnx)
        urllib.request.urlretrieve(url + ".json", cfg)
        return onnx

    def _load(self, name: str):
        if name not in self._cache:
            from piper import PiperVoice

            onnx = self._ensure_voice(name)
            self._cache[name] = PiperVoice.load(str(onnx), config_path=f"{onnx}.json")
        return self._cache[name]

    def __call__(self, audio: Audio, text: str) -> str:
        character = audio.poem.character if audio.poem is not None else None
        profile = get_voice_profile(character, audio.lang)
        voice = self._load(profile.voice)
        out_dir = self._data_dir / "audio"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{audio.id}.wav"
        with wave.open(str(out_path), "wb") as wav_file:
            self._synthesize(voice, text, wav_file, profile)
        logger.info(
            "synthesized %s (char=%s lang=%s voice=%s len=%s)",
            out_path, character, audio.lang, profile.voice, profile.length_scale,
        )
        return str(out_path)

    @staticmethod
    def _synthesize(voice, text, wav_file, profile) -> None:
        # Piper >= 1.3 takes a SynthesisConfig; older versions take kwargs.
        try:
            from piper import SynthesisConfig
        except ImportError:
            SynthesisConfig = None

        if SynthesisConfig is not None:
            try:
                cfg = SynthesisConfig(
                    length_scale=profile.length_scale,
                    noise_scale=profile.noise_scale,
                )
                voice.synthesize_wav(text, wav_file, syn_config=cfg)
                return
            except TypeError:
                pass
        try:
            voice.synthesize_wav(
                text,
                wav_file,
                length_scale=profile.length_scale,
                noise_scale=profile.noise_scale,
            )
        except TypeError:
            voice.synthesize_wav(text, wav_file)
