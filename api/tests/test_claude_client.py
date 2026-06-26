import pytest

from app.characters import Character
from app.claude_client import (
    PoemGenerationError,
    PoemGenerator,
    _extract_json,
)
from app.config import PoemConfig
from app.schemas import PoemResult, VoiceHints

from .conftest import SAMPLE_POEM, FakeClient, text_message


def _config(**overrides):
    base = dict(api_key="sk-test", model="claude-sonnet-4-6", parse_retries=2)
    base.update(overrides)
    return PoemConfig(**base)


def test_generate_returns_spec_schema():
    """完了条件: character + theme -> SPEC §5 schema."""
    client = FakeClient([text_message(SAMPLE_POEM)])
    gen = PoemGenerator(config=_config(), client=client)

    result = gen.generate(Character.YURI, theme="the sea")

    assert isinstance(result, PoemResult)
    # all SPEC §5 fields present and typed
    assert result.title == "Tidewater"
    assert result.poem_en
    assert result.poem_ja
    assert result.image_prompt
    assert result.mood == "melancholic"
    assert isinstance(result.voice_hints, VoiceHints)
    assert result.voice_hints.rate == 0.95
    # character is taken from the input, not the model output
    assert result.character == "yuri"


def test_generate_builds_prompt_and_passes_model():
    client = FakeClient([text_message(SAMPLE_POEM)])
    gen = PoemGenerator(config=_config(temperature=0.8), client=client)

    gen.generate(Character.NATSUKI, theme="cupcakes")

    call = client.messages.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["max_tokens"] == 1500
    assert call["temperature"] == 0.8
    assert "Natsuki" in call["system"]
    assert call["messages"][0]["role"] == "user"
    assert "cupcakes" in call["messages"][0]["content"]


def test_temperature_omitted_when_unset():
    client = FakeClient([text_message(SAMPLE_POEM)])
    gen = PoemGenerator(config=_config(temperature=None), client=client)

    gen.generate(Character.MONIKA)

    assert "temperature" not in client.messages.calls[0]


def test_accepts_code_fenced_json():
    fenced = "```json\n" + text_message(SAMPLE_POEM).content[0].text + "\n```"
    client = FakeClient([text_message(fenced)])
    gen = PoemGenerator(config=_config(), client=client)

    result = gen.generate(Character.SAYORI)
    assert result.title == "Tidewater"


def test_retries_on_invalid_then_succeeds():
    sleeps = []
    client = FakeClient(
        [text_message("not json at all"), text_message(SAMPLE_POEM)]
    )
    gen = PoemGenerator(
        config=_config(parse_retries=2), client=client, sleep=sleeps.append
    )

    result = gen.generate(Character.YURI)

    assert result.title == "Tidewater"
    assert len(client.messages.calls) == 2  # retried once
    assert len(sleeps) == 1  # backed off once


def test_raises_after_exhausting_retries():
    client = FakeClient([text_message("nope"), text_message("still nope")])
    gen = PoemGenerator(
        config=_config(parse_retries=1), client=client, sleep=lambda _s: None
    )

    with pytest.raises(PoemGenerationError):
        gen.generate(Character.YURI)
    assert len(client.messages.calls) == 2


def test_refusal_raises():
    client = FakeClient([text_message("", stop_reason="refusal")])
    gen = PoemGenerator(config=_config(), client=client)

    with pytest.raises(PoemGenerationError):
        gen.generate(Character.MONIKA)


def test_extract_json_finds_object_in_prose():
    raw = 'Here is your poem:\n{"title": "x", "poem_en": "a", "poem_ja": "b"} thanks!'
    assert _extract_json(raw) == '{"title": "x", "poem_en": "a", "poem_ja": "b"}'
