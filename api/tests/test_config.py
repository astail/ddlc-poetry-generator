import pytest

from app.config import DEFAULT_MODEL, PoemConfig


def test_from_env_reads_values():
    cfg = PoemConfig.from_env(
        {
            "ANTHROPIC_API_KEY": "sk-test",
            "POEM_MODEL": "claude-haiku-4-5",
            "POEM_MAX_TOKENS": "800",
            "POEM_TEMPERATURE": "0.7",
        }
    )
    assert cfg.api_key == "sk-test"
    assert cfg.model == "claude-haiku-4-5"
    assert cfg.max_tokens == 800
    assert cfg.temperature == 0.7


def test_from_env_defaults_and_optional_temperature():
    cfg = PoemConfig.from_env({"ANTHROPIC_API_KEY": "sk-test"})
    assert cfg.model == DEFAULT_MODEL
    assert cfg.max_tokens == 1500
    # temperature is omitted unless explicitly set
    assert cfg.temperature is None


def test_from_env_missing_key_raises():
    with pytest.raises(RuntimeError):
        PoemConfig.from_env({})
