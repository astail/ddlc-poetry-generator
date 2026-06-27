"""XTTS (Coqui) synthesizer — optional GPU TTS backend (issue #16).

Enable with TTS_BACKEND=xtts on a GPU-attached worker, and install the extra:
    pip install ".[xtts]"
XTTS shares the GPU with image generation; on a 6GB card do NOT run it
concurrently with heavy SD generation (run one GPU worker at a time / low
concurrency). Voice quality and pitch are richer than Piper.

The coqui ``TTS`` import is lazy so the default (Piper) image needs no torch.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .models import Audio

logger = logging.getLogger(__name__)

# character -> XTTS v2 built-in studio speaker (configurable).
CHARACTER_SPEAKERS: dict[str, str] = {
    "sayori": "Tammie Ema",
    "natsuki": "Daisy Studious",
    "yuri": "Alison Dietlinde",
    "monika": "Gracie Wise",
}
DEFAULT_SPEAKER = "Gracie Wise"
DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"


class XttsSynthesizer:
    def __init__(
        self,
        data_dir: Path | str = "/data",
        model_name: str = DEFAULT_MODEL,
        use_gpu: bool = True,
    ):
        self._data_dir = Path(data_dir)
        self._model_name = model_name
        self._use_gpu = use_gpu
        self._tts = None

    def speaker_for(self, character: str | None) -> str:
        return CHARACTER_SPEAKERS.get((character or "").lower(), DEFAULT_SPEAKER)

    def _load(self):
        if self._tts is None:
            from TTS.api import TTS  # lazy: only when XTTS is actually used

            self._tts = TTS(self._model_name, gpu=self._use_gpu)
        return self._tts

    def __call__(self, audio: Audio, text: str) -> str:
        tts = self._load()
        character = audio.poem.character if audio.poem is not None else None
        speaker = self.speaker_for(character)
        out_dir = self._data_dir / "audio"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{audio.id}.wav"
        tts.tts_to_file(
            text=text,
            file_path=str(out_path),
            speaker=speaker,
            language=audio.lang or "en",
        )
        logger.info(
            "XTTS synthesized %s (char=%s speaker=%s lang=%s)",
            out_path,
            character,
            speaker,
            audio.lang,
        )
        return str(out_path)
