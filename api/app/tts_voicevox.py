"""VOICEVOX synthesizer — Japanese TTS via the VOICEVOX engine HTTP API (#89).

VOICEVOX (https://voicevox.hiroshiba.jp/) is a free Japanese TTS engine with
anime-style character voices — a good fit for the four DDLC personas. It runs as
a separate service (Docker image ``voicevox/voicevox_engine``) exposing an HTTP
API; point the worker at it with ``VOICEVOX_URL`` (e.g. ``http://voicevox:50021``).

Synthesis is two calls: build an ``audio_query`` from the text + speaker, then
``synthesis`` to render a WAV. ``httpx`` is already a dependency, so no extra
package is needed (unlike the GPU XTTS backend).
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from .models import Audio, TtsBackend

logger = logging.getLogger(__name__)

# character -> VOICEVOX *style* (speaker) id. These are stable built-in styles
# of the default engine; picked to keep the four girls audibly distinct. See
# ``GET {VOICEVOX_URL}/speakers`` for the full catalogue to retune.
CHARACTER_SPEAKERS: dict[str, int] = {
    "sayori": 2,  # 四国めたん（ノーマル） — bright / cheerful
    "natsuki": 3,  # ずんだもん（ノーマル） — small / energetic
    "yuri": 16,  # 九州そら（ノーマル） — calm / mature
    "monika": 8,  # 春日部つむぎ（ノーマル） — composed
}
DEFAULT_SPEAKER = 3  # ずんだもん（ノーマル）
DEFAULT_URL = "http://voicevox:50021"


class VoicevoxSynthesizer:
    def __init__(
        self,
        data_dir: Path | str = "/data",
        base_url: str = DEFAULT_URL,
        speakers: dict[str, int] | None = None,
        default_speaker: int = DEFAULT_SPEAKER,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._data_dir = Path(data_dir)
        self._base_url = base_url.rstrip("/")
        self._speakers = speakers or CHARACTER_SPEAKERS
        self._default_speaker = default_speaker
        self._timeout = timeout
        # Injectable for tests (httpx.MockTransport); None = real network.
        self._transport = transport

    def speaker_for(self, character: str | None) -> int:
        return self._speakers.get((character or "").lower(), self._default_speaker)

    def __call__(self, audio: Audio, text: str) -> str:
        character = audio.poem.character if audio.poem is not None else None
        speaker = self.speaker_for(character)
        wav = self._synthesize(text, speaker)
        out_dir = self._data_dir / "audio"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{audio.id}.wav"
        out_path.write_bytes(wav)
        # Record the backend/voice actually used so the API/gallery reflect it.
        audio.backend = TtsBackend.VOICEVOX
        audio.voice = str(speaker)
        logger.info(
            "VOICEVOX synthesized %s (char=%s speaker=%s lang=%s)",
            out_path,
            character,
            speaker,
            audio.lang,
        )
        return str(out_path)

    def _synthesize(self, text: str, speaker: int) -> bytes:
        # VOICEVOX is a two-step API: /audio_query produces the synthesis params,
        # which are then POSTed back to /synthesis to render the WAV.
        with httpx.Client(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        ) as client:
            query = client.post("/audio_query", params={"text": text, "speaker": speaker})
            query.raise_for_status()
            audio = client.post("/synthesis", params={"speaker": speaker}, json=query.json())
            audio.raise_for_status()
            return audio.content
