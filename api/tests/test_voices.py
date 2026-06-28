import wave

import pytest

from app.models import Audio, Poem
from app.tts import PiperSynthesizer
from app.voices import UnsupportedLanguageError, get_voice_profile


def test_japanese_raises_on_piper_backend():
    # Piper (CPU) has no Japanese voice; it must error (with guidance) rather
    # than synthesize ja text with an English voice and garble it (#47/#50).
    with pytest.raises(UnsupportedLanguageError, match="xtts"):
        get_voice_profile("yuri", "ja")


def test_english_still_resolves():
    assert get_voice_profile("yuri", "en").voice
    assert get_voice_profile("yuri").voice  # default lang=en


def test_piper_synthesizer_rejects_japanese(tmp_path):
    synth = PiperSynthesizer(data_dir=tmp_path)
    poem = Poem(character="yuri", title="t", poem_en="hi", poem_ja="やあ")
    audio = Audio(lang="ja")
    poem.audios.append(audio)
    audio.id = 3
    with pytest.raises(UnsupportedLanguageError):
        synth(audio, "やあ")


def test_profiles_are_distinct_per_character():
    chars = ["sayori", "natsuki", "yuri", "monika"]
    scales = {c: get_voice_profile(c).length_scale for c in chars}
    # at least 3 distinct paces so characters are audibly differentiated
    assert len(set(scales.values())) >= 3
    # natsuki faster than yuri
    assert scales["natsuki"] < scales["yuri"]


def test_unknown_character_falls_back():
    p = get_voice_profile("not-a-character")
    assert p.voice
    assert p.length_scale > 0


class _FakeVoice:
    def __init__(self):
        self.last = None

    def synthesize_wav(self, text, wav, syn_config=None, **kwargs):
        self.last = (text, syn_config)
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 100)


def test_synthesizer_applies_character_profile(tmp_path):
    fake = _FakeVoice()
    synth = PiperSynthesizer(data_dir=tmp_path)
    synth._cache["en_US-amy-low"] = fake  # skip download/load

    poem = Poem(character="natsuki", title="t", poem_en="hi", poem_ja="やあ")
    audio = Audio(lang="en")
    poem.audios.append(audio)
    audio.id = 7

    path = synth(audio, "hi there")

    assert path.endswith("7.wav")
    text, cfg = fake.last
    assert text == "hi there"
    assert cfg is not None
    assert cfg.length_scale == get_voice_profile("natsuki").length_scale
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000


def test_synthesizer_falls_back_when_synconfig_unsupported(tmp_path):
    class OldVoice:
        def __init__(self):
            self.plain = 0

        def synthesize_wav(self, text, wav):  # accepts no config kwargs
            self.plain += 1
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * 10)

    old = OldVoice()
    synth = PiperSynthesizer(data_dir=tmp_path)
    synth._cache["en_US-amy-low"] = old
    poem = Poem(character="yuri", title="t", poem_en="x", poem_ja="x")
    audio = Audio(lang="en")
    poem.audios.append(audio)
    audio.id = 1
    synth(audio, "text")
    assert old.plain == 1  # fell back to the plain call
