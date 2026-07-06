"""Piper TTS synthesizer (issue #14).

Synthesizes a poem's text to a WAV under DATA_DIR/audio using Piper (CPU).
Voice models are downloaded on first use into DATA_DIR/voices (not committed).
Per-character voice mapping is layered on in issue #15.
"""

from __future__ import annotations

import hashlib
import logging
import os
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

# Expected SHA256 / byte size of each voice's .onnx model (from the upstream
# git-LFS pointers). Used to (a) verify a fresh download end-to-end and (b)
# cheaply detect a truncated/corrupt cached file (size check) so it is
# re-downloaded instead of failing forever. Add an entry when registering a new
# voice in VOICE_URLS.
VOICE_SHA256: dict[str, str] = {
    "en_US-amy-low": "a5a91abb7de0f104358a25aded480ddacf1ff0762886325886ec406a2e86aab3",
    "en_US-amy-medium": "b3a6e47b57b8c7fbe6a0ce2518161a50f59a9cdd8a50835c02cb02bdd6206c18",
}
VOICE_SIZE: dict[str, int] = {
    "en_US-amy-low": 63104526,
    "en_US-amy-medium": 63201294,
}

# lang -> default voice name
DEFAULT_VOICES: dict[str, str] = {"en": "en_US-amy-low"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_atomic(
    url: str,
    dest: Path,
    *,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
) -> None:
    """Download ``url`` to a temp file, verify it, then atomically rename.

    Writing straight to ``dest`` means an interrupted download leaves a partial
    file that later looks valid via ``exists()``. Instead we fetch to a sibling
    ``.part`` file, optionally check its size / SHA256, and only ``os.replace``
    (atomic on the same filesystem) it into place once verified. Any partial
    file is removed on failure so the next attempt starts clean.
    """
    tmp = dest.with_name(dest.name + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)  # noqa: S310 (hardcoded HTTPS HF URLs only)
        actual_size = tmp.stat().st_size
        if expected_size is not None and actual_size != expected_size:
            raise OSError(f"size mismatch for {dest.name}: got {actual_size}, want {expected_size}")
        if expected_sha256 is not None:
            actual_sha = _sha256(tmp)
            if actual_sha != expected_sha256:
                raise OSError(
                    f"sha256 mismatch for {dest.name}: got {actual_sha}, want {expected_sha256}"
                )
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


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
        # A previously-cached pair is reused only if the model passes a cheap
        # integrity check (expected size). A truncated file from an interrupted
        # download would otherwise be treated as valid forever (no self-heal).
        if onnx.exists() and cfg.exists() and self._cached_onnx_ok(name, onnx):
            return onnx
        url = VOICE_URLS.get(name)
        if not url:
            raise ValueError(f"unknown Piper voice: {name}")
        logger.info("downloading Piper voice %s", name)
        _download_atomic(
            url,
            onnx,
            expected_size=VOICE_SIZE.get(name),
            expected_sha256=VOICE_SHA256.get(name),
        )
        _download_atomic(url + ".json", cfg)
        return onnx

    @staticmethod
    def _cached_onnx_ok(name: str, onnx: Path) -> bool:
        expected = VOICE_SIZE.get(name)
        if expected is not None and onnx.stat().st_size != expected:
            logger.warning(
                "cached voice %s is %s bytes, expected %s; re-downloading",
                name,
                onnx.stat().st_size,
                expected,
            )
            return False
        return True

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
            out_path,
            character,
            audio.lang,
            profile.voice,
            profile.length_scale,
        )
        return str(out_path)

    @staticmethod
    def _synthesize(voice, text, wav_file, profile) -> None:
        # Piper >= 1.3 takes a SynthesisConfig; older versions take kwargs.
        try:
            from piper import SynthesisConfig
        except ImportError:
            SynthesisConfig = None  # type: ignore[assignment,misc]

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
