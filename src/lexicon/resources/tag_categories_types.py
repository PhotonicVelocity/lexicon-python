"""Types and validation helpers for tag_categories resource."""

from __future__ import annotations

from typing import TypedDict
from typing_extensions import ReadOnly

class TagCategoryResponse(TypedDict, total=False):
    """Readonly tag category dict returned by tag endpoints."""
    id: ReadOnly[int]
    label: ReadOnly[str]
    position: ReadOnly[int]
    color: ReadOnly[str]  # Hex string (#RRGGBB), not a Color enum name
    tags: ReadOnly[list[int]]

__all__ = ["TagCategoryResponse"]