"""Configuration for the Claude poem client, loaded from environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class PoemConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    max_tokens: int = 1500
    # temperature is only sent when set. Some newer models (Opus 4.8/4.7, Fable 5)
    # reject sampling params, so leave POEM_TEMPERATURE unset for those.
    temperature: float | None = None
    # SDK transport-level retries (429 / 5xx / connection errors, exp. backoff).
    max_retries: int = 3
    # request timeout in seconds.
    timeout: float = 60.0
    # extra retries when the model returns text that fails JSON parse/validation.
    parse_retries: int = 2

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PoemConfig:
        env = env if env is not None else os.environ
        api_key = env.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (copy .env.example to .env)")
        temp = env.get("POEM_TEMPERATURE")
        return cls(
            api_key=api_key,
            model=env.get("POEM_MODEL", DEFAULT_MODEL),
            max_tokens=int(env.get("POEM_MAX_TOKENS", "1500")),
            temperature=float(temp) if temp else None,
            max_retries=int(env.get("POEM_MAX_RETRIES", "3")),
            timeout=float(env.get("POEM_TIMEOUT", "60")),
            parse_retries=int(env.get("POEM_PARSE_RETRIES", "2")),
        )
