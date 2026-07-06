"""Shared test fakes for the Claude client (no network / no API key needed)."""

from __future__ import annotations

import json
from types import SimpleNamespace


def text_message(
    payload,
    *,
    stop_reason: str = "end_turn",
    input_tokens: int = 12,
    output_tokens: int = 34,
):
    """Build a fake Messages API response with a single text block.

    ``payload`` may be a dict (serialized to JSON) or a raw string.
    """
    text = json.dumps(payload) if isinstance(payload, dict) else payload
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
        _request_id="req_test_123",
    )


class FakeMessages:
    def __init__(self, responses: list[object]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeMessages.create called more times than expected")
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


class FakeClient:
    def __init__(self, responses: list[object]):
        self.messages = FakeMessages(responses)


SAMPLE_POEM = {
    "title": "Tidewater",
    "title_ja": "潮汐",
    "character": "ignored-by-client",
    "poem_en": "The sea forgets my name each night.",
    "poem_ja": "海は毎晩わたしの名前を忘れる。",
    "image_prompt": "1girl, purple hair, moonlit shore, waves, melancholic",
    "image_negative": "lowres, bad anatomy",
    "mood": "melancholic",
    "voice_hints": {"rate": 0.95, "pitch": -1},
}
