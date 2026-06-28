import io
import wave

import httpx
import pytest

from app.models import Audio, Poem
from app.tts_voicevox import VoicevoxSynthesizer


def _wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


def test_voicevox_speaker_mapping():
    vs = VoicevoxSynthesizer(data_dir="/tmp")
    assert vs.speaker_for("yuri") == 16
    assert vs.speaker_for("natsuki") == 3
    assert vs.speaker_for("MONIKA") == 8  # case-insensitive
    assert vs.speaker_for("unknown") == vs._default_speaker  # falls back


def test_voicevox_synthesizes_via_http(tmp_path):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/audio_query":
            return httpx.Response(200, json={"accent_phrases": [], "speedScale": 1.0})
        if request.url.path == "/synthesis":
            return httpx.Response(200, content=_wav_bytes(), headers={"content-type": "audio/wav"})
        return httpx.Response(404)

    vs = VoicevoxSynthesizer(
        data_dir=tmp_path,
        base_url="http://voicevox:50021",
        transport=httpx.MockTransport(handler),
    )
    poem = Poem(character="natsuki", title="t", poem_en="hi", poem_ja="やあ")
    audio = Audio(lang="ja")
    poem.audios.append(audio)
    audio.id = 5

    path = vs(audio, "やあ、これはテストです。")

    assert path.endswith("5.wav")
    # Two-step API: audio_query then synthesis, both with the mapped speaker id.
    assert [c.url.path for c in calls] == ["/audio_query", "/synthesis"]
    assert calls[0].url.params["text"] == "やあ、これはテストです。"
    assert calls[0].url.params["speaker"] == "3"  # natsuki
    assert calls[1].url.params["speaker"] == "3"
    # Records the backend/voice actually used.
    assert audio.backend == "voicevox"
    assert audio.voice == "3"
    # Produced a real, readable WAV.
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 24000


def test_voicevox_raises_on_engine_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "bad request"})

    vs = VoicevoxSynthesizer(
        data_dir=tmp_path,
        base_url="http://voicevox:50021",
        transport=httpx.MockTransport(handler),
    )
    poem = Poem(character="yuri", title="t", poem_en="x", poem_ja="ゆり")
    audio = Audio(lang="ja")
    poem.audios.append(audio)
    audio.id = 1
    # An engine error surfaces (the worker then retries / dead-letters it).
    with pytest.raises(httpx.HTTPStatusError):
        vs(audio, "ゆり")
