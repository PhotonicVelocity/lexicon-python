"""Shared helpers for the Lexicon client."""

from __future__ import annotations

from typing import Iterable

def unique_in_order(values: Iterable[int]) -> list[int]:
    """Return unique values preserving the original order."""
    seen: set[int] = set()
    output: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
