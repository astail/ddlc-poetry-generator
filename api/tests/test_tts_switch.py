import wave

from app.models import Audio, Poem
from app.tts import PiperSynthesizer
from app.tts_xtts import XttsSynthesizer
from app.worker_tts import _default_synthesizer


def test_default_backend_is_piper(monkeypatch):
    monkeypatch.delenv("TTS_BACKEND", raising=False)
    assert isinstance(_default_synthesizer(), PiperSynthesizer)


def test_xtts_backend_selected(monkeypatch):
    monkeypatch.setenv("TTS_BACKEND", "xtts")
    assert isinstance(_default_synthesizer(), XttsSynthesizer)


def test_xtts_speaker_mapping():
    xs = XttsSynthesizer(data_dir="/tmp")
    assert xs.speaker_for("yuri") == "Alison Dietlinde"
    assert xs.speaker_for("natsuki") == "Daisy Studious"
    assert xs.speaker_for("unknown")  # falls back to a default speaker


def test_xtts_call_uses_speaker_and_lang(tmp_path):
    xs = XttsSynthesizer(data_dir=tmp_path)
    captured = {}

    class FakeTTS:
        def tts_to_file(self, text, file_path, speaker, language):
            captured.update(text=text, speaker=speaker, language=language)
            with wave.open(file_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                w.writeframes(b"\x00\x00" * 50)

    xs._tts = FakeTTS()  # bypass real model load
    poem = Poem(character="natsuki", title="t", poem_en="hi", poem_ja="やあ")
    audio = Audio(lang="en")
    poem.audios.append(audio)
    audio.id = 3

    path = xs(audio, "hello there")
    assert path.endswith("3.wav")
    assert captured == {
        "text": "hello there",
        "speaker": "Daisy Studious",
        "language": "en",
    }


def test_xtts_supports_japanese(tmp_path):
    # XTTS is multilingual: ja text is synthesized with language="ja" (#50).
    xs = XttsSynthesizer(data_dir=tmp_path)
    captured = {}

    class FakeTTS:
        def tts_to_file(self, text, file_path, speaker, language):
            captured.update(text=text, language=language)
            with wave.open(file_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                w.writeframes(b"\x00\x00" * 50)

    xs._tts = FakeTTS()
    poem = Poem(character="yuri", title="t", poem_en="hi", poem_ja="やあ")
    audio = Audio(lang="ja")
    poem.audios.append(audio)
    audio.id = 9
    xs(audio, "やあ")
    assert captured["language"] == "ja"
    assert captured["text"] == "やあ"
