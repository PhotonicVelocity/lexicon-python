"""Public color helpers — Lexicon color name ⇄ RGB.

Lexicon stores colors (on cuepoints, tags, etc.) as Lexicon-specific name
strings declared by the :data:`Color` literal type. This module exposes the
small surface needed to do anything with those values besides comparing them
to other Lexicon names — primarily, converting them to RGB for rendering or
for mapping into another color system.
"""

from __future__ import annotations

from .resources._common_types import COLORS, COLOR_RGBS, Color

__all__ = ["Color", "color_rgb"]


def color_rgb(name: Color) -> tuple[int, int, int]:
    """Return the RGB tuple ``(r, g, b)`` (0–255) for a Lexicon color name.

    Raises:
        ValueError: If ``name`` is not a recognized Lexicon color.
    """
    try:
        index = COLORS.index(name)
    except ValueError:
        raise ValueError(
            f"Unknown Lexicon color: {name!r} (valid: {', '.join(COLORS)})"
        ) from None
    return COLOR_RGBS[index]
