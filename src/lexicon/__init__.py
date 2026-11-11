"""Public package surface for the lexicon Python client."""

from .client import (
    DEFAULT_APP_NAME,
    DEFAULT_HOST,
    LEXICON_PORT,
    Lexicon,
    LexiconAuthError,
    LexiconConnectionError,
)
from .colors import Color, color_rgb
from .resources.control_types import CONTROL_ACTIONS, ControlAction
from .resources.player_types import PlayingResponse, RemoteTrackResponse
from .resources.playlists_types import PlaylistResponse
from .resources.tag_categories_types import TagCategoryResponse
from .resources.tags_types import TagResponse
from .resources.tracks_types import (
    CuePointResponse,
    CuePointUpdate,
    TEMPO_RANGES,
    TempoMarkerResponse,
    TempoMarkerUpdate,
    TempoRange,
    TrackResponse,
)

__all__ = [
    "Color",
    "color_rgb",
    "DEFAULT_APP_NAME",
    "DEFAULT_HOST",
    "LEXICON_PORT",
    "Lexicon",
    "LexiconAuthError",
    "LexiconConnectionError",
    "ControlAction",
    "CONTROL_ACTIONS",
    "TrackResponse",
    "PlayingResponse",
    "RemoteTrackResponse",
    "PlaylistResponse",
    "TagResponse",
    "TagCategoryResponse",
    "CuePointResponse",
    "CuePointUpdate",
    "TempoMarkerResponse",
    "TempoMarkerUpdate",
    "TempoRange",
    "TEMPO_RANGES",
]
