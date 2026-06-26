"""Safe resolution of generated-asset paths under the data directory."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def resolve_under(base: Path, rel: str) -> Optional[Path]:
    """Resolve ``rel`` under ``base``; return None if it escapes ``base``.

    Guards against path traversal (``..``, absolute paths, symlinks).
    """
    base = base.resolve()
    try:
        target = (base / rel).resolve()
    except (OSError, ValueError):
        return None
    if target == base or base in target.parents:
        return target
    return None
