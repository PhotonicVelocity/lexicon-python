"""Types and validation helpers for tag_categories resource."""

from __future__ import annotations

from typing import TypedDict
from typing_extensions import ReadOnly

from ._common_types import Color

class TagCategoryResponse(TypedDict, total=False):
    """Readonly tag category dict returned by tag endpoints."""
    id: ReadOnly[int]
    label: ReadOnly[str]
    position: ReadOnly[int]
    color: ReadOnly[Color]
    tags: ReadOnly[list[int]]

__all__ = ["TagCategoryResponse"]