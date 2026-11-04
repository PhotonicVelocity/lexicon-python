"""Types for the music player."""

from __future__ import annotations

import sys
from typing import TypedDict

if sys.version_info >= (3, 13):
    from typing import ReadOnly, Required
else:
    from typing_extensions import ReadOnly, Required

from .tracks_types import TrackResponse


class RemoteTrackResponse(TypedDict, total=False):
    """Readonly dict for a streaming track loaded in the player.

    Lexicon builds this object at load time for Beatport, Apple Music, and Spotify
    tracks. It is not a library row: ``id`` is the service's own track ID (an int
    for Beatport), so it cannot be passed to ``tracks.get()``, and ``duration`` is
    the length of the preview clip in seconds, not of the track. There is no
    ``type`` or ``streamingId`` field, and ``key`` is present only when the track
    was loaded from a library row. See docs/api-issues.md.
    """

    id: Required[ReadOnly[int | str]]
    url: ReadOnly[str]
    headers: ReadOnly[dict | None]
    streamingService: ReadOnly[str]
    title: ReadOnly[str]
    artist: ReadOnly[str | None]
    albumTitle: ReadOnly[str]
    imageUrl: ReadOnly[str]
    bpm: ReadOnly[float]
    duration: ReadOnly[float]
    key: ReadOnly[str]


class PlayingResponse(TypedDict):
    """Readonly dict returned by ``player.playing()``.

    ``progress`` is the fraction of ``track["duration"]`` played, from 0 to 1.
    ``currentTime`` is the position in seconds.
    """

    track: ReadOnly[TrackResponse | RemoteTrackResponse]
    progress: ReadOnly[float | None]
    currentTime: ReadOnly[float | None]
