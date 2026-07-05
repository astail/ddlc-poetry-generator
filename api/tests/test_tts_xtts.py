"""XTTS synthesizer tests (#122). Coqui TTS / torch are never imported: the
model is injected so the synthesis path is exercised without the GPU stack."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.tts_xtts import DEFAULT_SPEAKER, XttsSynthesizer


def test_speaker_mapping_is_case_insensitive_with_default():
    s = XttsSynthesizer(data_dir="/tmp")
    assert s.speaker_for("yuri") == "Alison Dietlinde"
    assert s.speaker_for("SAYORI") == "Tammie Ema"
    assert s.speaker_for("natsuki") == "Daisy Studious"
    assert s.speaker_for("unknown") == DEFAULT_SPEAKER
    assert s.speaker_for(None) == DEFAULT_SPEAKER


def test_synthesize_writes_wav_with_character_speaker(tmp_path):
    calls: dict = {}

    class FakeTTS:
        def tts_to_file(self, **kwargs):
            calls.update(kwargs)
            Path(kwargs["file_path"]).write_bytes(b"wav")  # emulate coqui writing

    synth = XttsSynthesizer(data_dir=tmp_path)
    synth._tts = FakeTTS()  # bypass _load(): no TTS/torch import

    audio = SimpleNamespace(id=7, lang="en", poem=SimpleNamespace(character="natsuki"))
    out = synth(audio, "hello world")

    assert out == str(tmp_path / "audio" / "7.wav")
    assert Path(out).exists()
    assert calls["speaker"] == "Daisy Studious"  # natsuki
    assert calls["language"] == "en"
    assert calls["text"] == "hello world"


def test_synthesize_defaults_language_when_missing(tmp_path):
    calls: dict = {}

    class FakeTTS:
        def tts_to_file(self, **kwargs):
            calls.update(kwargs)
            Path(kwargs["file_path"]).write_bytes(b"wav")

    synth = XttsSynthesizer(data_dir=tmp_path)
    synth._tts = FakeTTS()

    audio = SimpleNamespace(id=1, lang=None, poem=None)  # no poem -> default speaker
    synth(audio, "text")

    assert calls["language"] == "en"  # falls back to en
    assert calls["speaker"] == DEFAULT_SPEAKER
