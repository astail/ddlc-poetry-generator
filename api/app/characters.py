"""DDLC characters."""

from __future__ import annotations

from enum import Enum


class Character(str, Enum):
    SAYORI = "sayori"
    NATSUKI = "natsuki"
    YURI = "yuri"
    MONIKA = "monika"


ALL_CHARACTERS = tuple(Character)
