"""DDLC characters and their poem styles.

Minimal persona definitions for the Claude client. The full persona / style
guide is fleshed out in issue #5.
"""

from __future__ import annotations

from enum import Enum


class Character(str, Enum):
    SAYORI = "sayori"
    NATSUKI = "natsuki"
    YURI = "yuri"
    MONIKA = "monika"


# Short style hints injected into the system prompt. Expanded in #5.
CHARACTER_STYLES: dict[Character, str] = {
    Character.SAYORI: (
        "plain and conversational, bright on the surface with a hidden "
        "melancholy underneath; relatively short and earnest"
    ),
    Character.NATSUKI: (
        "short, cute and punchy with a tsundere edge; rhythmic, a little blunt"
    ),
    Character.YURI: (
        "ornate and dark, intricate vocabulary and elaborate metaphor; "
        "introspective and longer"
    ),
    Character.MONIKA: (
        "meta, philosophical and self-aware; composed and articulate"
    ),
}
