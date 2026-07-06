"""DDLC characters."""

from __future__ import annotations

from enum import Enum


class Character(str, Enum):  # noqa: UP042 (keep str+Enum; StrEnum would change str())
    SAYORI = "sayori"
    NATSUKI = "natsuki"
    YURI = "yuri"
    MONIKA = "monika"


ALL_CHARACTERS = tuple(Character)
