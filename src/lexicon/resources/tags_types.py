"""Types and validation helpers for tags resource.

All tag inputs are simple primitives (tag_id, category_id, label, position).
No complex normalization functions needed; validation stays inline in tags.py.
"""

from __future__ import annotations

from typing import TypedDict
from typing_extensions import ReadOnly


class TagResponse(TypedDict, total=False):
    """Readonly tag dict returned by tag endpoints."""
    id: ReadOnly[int]
    label: ReadOnly[str]
    categoryId: ReadOnly[int]
    position: ReadOnly[int]

__all__ = ["TagResponse"]
