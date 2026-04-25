"""Startup font probe and fallback chain."""

from __future__ import annotations

import logging
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass

from toolkit import tokens

logger = logging.getLogger(__name__)

# Serif fallback: Georgia is universally available on Windows and most Linux CI.
_FONT_SERIF_FALLBACK = "Georgia"


@dataclass(frozen=True)
class FontMap:
    """Resolved font families after probing what is available on this system."""

    sans_family: str  # "Aptos" or "Segoe UI"
    serif_family: str  # "Source Serif 4" or "Georgia"
    mono_family: str  # "Cascadia Mono" or "Consolas"


def detect_fonts(root: tk.Tk) -> FontMap:
    """Probe tkinter.font.families() and resolve font families with fallbacks.

    Emits a single INFO log line listing the resolved families.
    """
    available: frozenset[str] = frozenset(tkfont.families(root))

    # Case-insensitive lookup helper (font family names can vary by OS)
    available_lower = {f.lower(): f for f in available}

    def pick(primary: str, fallback: str) -> str:
        if primary.lower() in available_lower:
            return primary
        return fallback

    sans = pick(tokens.FONT_SANS_PRIMARY, tokens.FONT_SANS_FALLBACK)
    serif = pick(tokens.FONT_SERIF_PRIMARY, _FONT_SERIF_FALLBACK)
    mono = pick(tokens.FONT_MONO_PRIMARY, tokens.FONT_MONO_FALLBACK)

    font_map = FontMap(sans_family=sans, serif_family=serif, mono_family=mono)

    logger.info(
        "Fonts resolved — sans: %r, serif: %r, mono: %r",
        font_map.sans_family,
        font_map.serif_family,
        font_map.mono_family,
    )

    return font_map
