"""Claude API client wrapper for poem generation.

Responsibilities (issue #4):
- read config (ANTHROPIC_API_KEY / POEM_MODEL / temperature / max_tokens) from env
- timeout + exponential-backoff retries
  (transport errors via the SDK's max_retries; parse/validation failures here)
- structured JSON output, parsed and validated against PoemResult
- log errors and token usage
"""

from __future__ import annotations

import json
import logging
import re
import time

from pydantic import ValidationError

from .characters import Character
from .config import PoemConfig
from .prompts import build_system_prompt, build_user_prompt
from .schemas import PoemResult

logger = logging.getLogger(__name__)

_FENCE_OPEN = re.compile(r"^```[a-zA-Z0-9]*\s*")
_FENCE_CLOSE = re.compile(r"\s*```$")


class PoemGenerationError(RuntimeError):
    """Raised when a valid poem could not be produced."""


def _extract_text(message) -> str:
    """Concatenate the text blocks of a Messages API response."""
    parts = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _extract_json(text: str) -> str:
    """Pull a JSON object out of model text, tolerating code fences/prose."""
    t = text.strip()
    if t.startswith("```"):
        t = _FENCE_OPEN.sub("", t)
        t = _FENCE_CLOSE.sub("", t).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("no JSON object found in response", t or "", 0)
    return t[start : end + 1]


class PoemGenerator:
    """Generate a structured poem for a DDLC character via the Claude API."""

    def __init__(
        self,
        config: PoemConfig | None = None,
        client=None,
        sleep=time.sleep,
    ):
        self.config = config or PoemConfig.from_env()
        self._sleep = sleep
        if client is not None:
            self.client = client
        else:
            import anthropic

            self.client = anthropic.Anthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )

    def generate(self, character: Character | str, theme: str | None = None) -> PoemResult:
        character = Character(character)
        system = build_system_prompt(character)
        user = build_user_prompt(character, theme)

        last_error: Exception | None = None
        for attempt in range(self.config.parse_retries + 1):
            message = self._call(system, user)

            if getattr(message, "stop_reason", None) == "refusal":
                req_id = getattr(message, "_request_id", None)
                raise PoemGenerationError(f"model refused the request (request_id={req_id})")

            text = _extract_text(message)
            try:
                data = json.loads(_extract_json(text))
                result = PoemResult.model_validate(data)
                result.character = character.value  # trust input, not the model
                logger.info("poem generated: character=%s title=%r", character.value, result.title)
                return result
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                logger.warning(
                    "poem parse/validation failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.config.parse_retries + 1,
                    exc,
                )
                if attempt < self.config.parse_retries:
                    self._sleep(min(0.5 * (2**attempt), 8.0))

        raise PoemGenerationError(
            f"failed to produce a valid poem after {self.config.parse_retries + 1} attempt(s)"
        ) from last_error

    def _call(self, system: str, user: str):
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature

        message = self.client.messages.create(**kwargs)

        usage = getattr(message, "usage", None)
        if usage is not None:
            logger.info(
                "claude call model=%s input_tokens=%s output_tokens=%s",
                self.config.model,
                getattr(usage, "input_tokens", None),
                getattr(usage, "output_tokens", None),
            )
        return message
