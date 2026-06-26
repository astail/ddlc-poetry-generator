"""Live smoke test for the Claude poem client (hits the real API).

Requires ANTHROPIC_API_KEY in the environment. Not part of the unit suite.

Usage:
    docker compose run --rm --no-deps api python scripts/smoke.py [character] [theme]
"""

from __future__ import annotations

import logging
import sys

from app.characters import Character
from app.claude_client import PoemGenerator


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    character = Character(sys.argv[1]) if len(sys.argv) > 1 else Character.YURI
    theme = sys.argv[2] if len(sys.argv) > 2 else "the quiet after rain"

    gen = PoemGenerator()  # reads config from env
    result = gen.generate(character, theme)

    print(f"\n=== {result.character} :: {result.title} ===")
    print("\n[EN]\n" + result.poem_en)
    print("\n[JA]\n" + result.poem_ja)
    print(f"\nmood={result.mood}  voice={result.voice_hints}")
    print(f"\nimage_prompt: {result.image_prompt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
