"""Types and validation helpers for tag_categories resource."""

from __future__ import annotations

import sys
from typing import TypedDict

if sys.version_info >= (3, 13):
    from typing import ReadOnly, Required
else:
    from typing_extensions import ReadOnly, Required

__all__ = ["TagCategoryResponse"]


class TagCategoryResponse(TypedDict, total=False):
    """Readonly tag category dict returned by tag endpoints."""

    id: Required[ReadOnly[int]]
    label: Required[ReadOnly[str]]
    position: ReadOnly[int]
    color: ReadOnly[str]  # Hex string (#RRGGBB), not a Color enum name
    tags: ReadOnly[list[int]]
