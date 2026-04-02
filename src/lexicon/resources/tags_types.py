"""Types and validation helpers for tags resource.

All tag inputs are simple primitives (tag_id, category_id, label, position).
No complex normalization functions needed; validation stays inline in tags.py.
"""

from __future__ import annotations

from typing import Required, TypedDict
from typing_extensions import ReadOnly

__all__ = ["TagResponse"]


class TagResponse(TypedDict, total=False):
    """Readonly tag dict returned by tag endpoints."""
    id: Required[ReadOnly[int]]
    label: Required[ReadOnly[str]]
    categoryId: Required[ReadOnly[int]]
    position: ReadOnly[int]
