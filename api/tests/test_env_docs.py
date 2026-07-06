"""Guard against env-var documentation drift (#132).

Every environment variable the app reads must appear in .env.example (even as a
commented example), so the docs and code can't silently diverge again.
"""

from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
_ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"

# `environ.get("X"`, `environ["X"`, or `env.get("X"` (config/observability take an
# env Mapping). COQUI_TOS_AGREED is set via environ.setdefault, not read as config.
_PATTERN = re.compile(
    r"""(?:environ\.get\(|environ\[|\benv\.get\()\s*["']([A-Z][A-Z0-9_]{2,})["']"""
)


def _referenced_env_vars() -> set[str]:
    found: set[str] = set()
    for path in _APP.rglob("*.py"):
        found.update(_PATTERN.findall(path.read_text(encoding="utf-8")))
    return found


def test_referenced_env_vars_are_documented_in_env_example():
    env_example = _ENV_EXAMPLE.read_text(encoding="utf-8")
    missing = sorted(v for v in _referenced_env_vars() if v not in env_example)
    assert not missing, f"env vars read by app/ but missing from .env.example: {missing}"
