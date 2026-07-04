"""Unit tests for repository helpers."""

from app.repository import combine_image_prompt


def test_combine_appends_extra():
    assert combine_image_prompt("a, b", "c, d") == "a, b, c, d"


def test_combine_ignores_blank_or_none_extra():
    assert combine_image_prompt("a, b", "   ") == "a, b"
    assert combine_image_prompt("a, b", None) == "a, b"


def test_combine_trims_trailing_comma_and_whitespace():
    assert combine_image_prompt("a, b", "  c,  ") == "a, b, c"


def test_combine_uses_extra_only_when_base_empty():
    assert combine_image_prompt("", "c") == "c"
