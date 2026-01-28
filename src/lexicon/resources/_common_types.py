"""Shared types and validation helpers for resources.

This module contains:
- Validation mode type (shared across all resources)
- Color type definitions and normalization (used by tag_categories)
- Common validation normalizers (ID sequences, etc.)
"""

from __future__ import annotations

import logging
import re
from typing import Literal, Sequence, get_args

from ..utils import unique_in_order

_logger = logging.getLogger(__name__)

# --- Shared Validation Mode --- #
ValidationMode = Literal["off", "warn", "strict"]


# --- Color Types and Normalization --- #
Color = Literal[
    "red_dark", "red", "red_light", "red_orange", "orange", "beige", "yellow_dark", "yellow",
    "lime", "green_light", "green", "green_dark", "teal", "aqua", "aqua_dark", "blue_light",
    "blue", "blue_dark", "blue_violet", "violet", "violet_light", "magenta", "magenta_dark",
    "magenta_red", "grey_light", "grey_dark", "black", "white",
]
COLORS: tuple[Color, ...] = get_args(Color)
COLOR_RGBS: tuple[tuple[int, int, int], ...] = (
    (158,  15,   7), # red_dark
    (230,  15,  13), # red
    (242, 102,  92), # red_light
    (239,  89,  15), # red_orange
    (232, 137,  20), # orange
    (255, 225, 148), # beige
    (245, 208,   1), # yellow_dark
    (245, 245,  10), # yellow
    (186, 232,  22), # lime
    (174, 245,  95), # green_light
    (127, 231,  16), # green
    ( 75, 140,   8), # green_dark
    ( 20, 222, 120), # teal
    ( 20, 222, 202), # aqua
    (  7, 148, 134), # aqua_dark
    ( 47, 168, 237), # blue_light
    ( 14,  88, 222), # blue
    (  0,  40, 171), # blue_dark
    (132,   0, 255), # blue_violet
    (170,  59, 255), # violet
    (198, 140, 243), # violet_light
    (230,  15, 222), # magenta
    (170,   0, 188), # magenta_dark
    (222,  17,  92), # magenta_red
    (173, 173, 173), # grey_light
    ( 92,  92,  92), # grey_dark
    ( 48,  48,  48), # black
    (255, 255, 255), # white
)


def _normalize_color(value: object) -> Color | None:
    """Normalize color inputs to the nearest Lexicon color name.

    Parameters
    ----------
    value
        Color input. Supported forms:
        - ``None`` or the string ``"None"`` (case-insensitive)
        - Lexicon color names (see ``COLORS``)
        - Various RGB/RGBA forms (alpha is dropped)
          - Hex strings (``#RGB``, ``#RGBA``, ``#RRGGBB``, ``#RRGGBBAA``)
          - RGB/RGBA tuples or lists (ints 0-255 or floats 0-1)
          - Packed RGB integer (``0xRRGGBB``, ``0xAARRGGBB``)

    Returns
    -------
    Color or None
        The nearest Lexicon color name, or ``None`` when the input is ``None``.

    Raises
    ------
    ValueError
        If the input cannot be parsed as a color value.
    """
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip().lower() == "none":
            return None
        if value in COLORS:
            return value
        hex_match = re.match(r"^\s*#?([0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})\s*$", value, flags=re.IGNORECASE)
        if hex_match:
            hex_value = hex_match.group(1)
            if len(hex_value) in (3, 4):
                hex_value = "".join(ch * 2 for ch in hex_value)
            if len(hex_value) == 8:
                hex_value = hex_value[:6]
            rgb = (
                int(hex_value[0:2], 16),
                int(hex_value[2:4], 16),
                int(hex_value[4:6], 16),
            )
            return _nearest_color(rgb)
        raise ValueError(f"Unsupported string input {value!r}")

    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"Negative packed int {value!r}")
        if value > 0xFFFFFF:
            value = value & 0xFFFFFF
        rgb = ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
        return _nearest_color(rgb)

    if isinstance(value, (tuple, list)) and len(value) in (3, 4):
        rgb_values = value[:3]
        if all(isinstance(channel, (int, float)) for channel in rgb_values):
            rgb = []
            for channel in rgb_values:
                channel_value = float(channel)
                if channel_value <= 1:
                    channel_value *= 255
                rgb.append(int(max(0, min(255, round(channel_value)))))
            return _nearest_color((rgb[0], rgb[1], rgb[2]))
        raise ValueError(f"Invalid RGB tuple values {value!r}")

    raise ValueError(f"Unsupported input type {type(value)}")


def _nearest_color(rgb: tuple[int, int, int]) -> Color:
    """Find the nearest Lexicon color to the given RGB values."""
    best_index = 0
    best_distance = float("inf")
    for index, candidate in enumerate(COLOR_RGBS):
        dr = rgb[0] - candidate[0]
        dg = rgb[1] - candidate[1]
        db = rgb[2] - candidate[2]
        distance = dr * dr + dg * dg + db * db
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return COLORS[best_index]


# --- ID Sequence Normalization --- #
def _normalize_id_sequence(ids: int | Sequence[int] | object) -> list[int] | None:
    """Normalize single ID or sequence of IDs to a deduplicated list.
    
    Parameters
    ----------
    ids
        Single integer ID or sequence of integer IDs.
    
    Returns
    -------
    list[int] | None
        Deduplicated list of valid IDs (>= 1), or None if:
        - Input is not int or sequence (or is str/bytes)
        - No valid IDs found (all < 1)
    
    Notes
    -----
    Used for normalizing track IDs, tag IDs, and similar integer sequences.
    Filters out any non-integer elements and values < 1, then deduplicates.
    """
    if isinstance(ids, int):
        id_list = [ids]
    elif isinstance(ids, Sequence) and not isinstance(ids, (str, bytes)):
        id_list = list(ids)
    else:
        return None

    valid_ids = [id_val for id_val in id_list if isinstance(id_val, int) and id_val >= 1]
    if not valid_ids:
        return None

    return unique_in_order(valid_ids)
