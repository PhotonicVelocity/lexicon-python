"""Public package surface for the lexicon Python client."""

from .client import DEFAULT_HOST, LEXICON_PORT, Lexicon
from .colors import Color, color_rgb
from .resources.playlists_types import PlaylistResponse
from .resources.tag_categories_types import TagCategoryResponse
from .resources.tags_types import TagResponse
from .resources.tracks_types import (
    CuePointResponse,
    CuePointUpdate,
    TempoMarkerResponse,
    TempoMarkerUpdate,
    TrackResponse,
)

__all__ = [
    "Color",
    "color_rgb",
    "DEFAULT_HOST",
    "LEXICON_PORT",
    "Lexicon",
    "TrackResponse",
    "PlaylistResponse",
    "TagResponse",
    "TagCategoryResponse",
    "CuePointResponse",
    "CuePointUpdate",
    "TempoMarkerResponse",
    "TempoMarkerUpdate",
]
