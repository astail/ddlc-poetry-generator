import pytest

from app.characters import ALL_CHARACTERS, Character
from app.personas import PERSONAS, Persona
from app.prompts import build_system_prompt, build_user_prompt


def test_all_characters_have_persona():
    assert set(PERSONAS) == set(Character)
    for persona in PERSONAS.values():
        assert isinstance(persona, Persona)
        assert persona.name and persona.style and persona.voice


@pytest.mark.parametrize("character", ALL_CHARACTERS)
def test_system_prompt_anchors(character):
    s = build_system_prompt(character)
    # character pinned + persona name present
    assert PERSONAS[character].name in s
    assert f'"{character.value}"' in s
    # required generation instructions
    assert "ONLY a single JSON object" in s
    assert "ORIGINAL" in s
    assert "non-commercial" in s
    # bilingual output + image + voice instructions present
    assert "poem_en" in s
    assert "poem_ja" in s
    assert "image_prompt" in s
    assert "image_negative" in s
    assert "voice_hints" in s


def test_prompts_are_distinct_per_character():
    prompts = {c: build_system_prompt(c) for c in Character}
    assert len(set(prompts.values())) == len(Character)


def test_distinctive_style_keywords():
    assert "conversational" in build_system_prompt(Character.SAYORI)
    assert "tsundere" in build_system_prompt(Character.NATSUKI)
    assert "ornate" in build_system_prompt(Character.YURI)
    assert "philosophical" in build_system_prompt(Character.MONIKA)


def test_user_prompt_with_and_without_theme():
    assert "cupcakes" in build_user_prompt(Character.NATSUKI, "cupcakes")
    generic = build_user_prompt(Character.YURI, None)
    assert "Yuri" in generic
