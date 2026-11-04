"""Music player resource wrapper."""

from __future__ import annotations

from typing import Optional, cast

from .base import Resource
from .player_types import PlayingResponse
from .tracks import Tracks


class Player(Resource):
    """Music player operations."""

    def __init__(self, client, *, tracks: Tracks) -> None:
        """Initialize the player resource.

        Parameters
        ----------
        client
            Core Lexicon client instance.
        tracks
            Tracks resource wrapper, used to convert enums on library tracks.
        """
        super().__init__(client)
        self._tracks = tracks

    def playing(self, *, timeout: Optional[int] = None) -> PlayingResponse | None:
        """Fetch the track loaded in the player, whether playing or paused.

        The API has no play state field. To tell playing from paused, compare
        ``currentTime`` across two calls.

        ``track`` is a library track or, for Beatport, Apple Music, and Spotify, a
        :class:`~lexicon.resources.player_types.RemoteTrackResponse`, whose ``id``
        belongs to the streaming service rather than the library.

        Parameters
        ----------
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        dict | None
            Dict with ``track``, ``progress``, and ``currentTime``, or None if no
            track is loaded or on error.
        """
        response = self._get("/playing", timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data")
        if not isinstance(data, dict):
            return None
        track = data.get("track")
        # An empty player answers {"track": null, ...}, so a missing track is
        # not an error and logs nothing.
        if not isinstance(track, dict):
            return None
        return cast(
            PlayingResponse, {**data, "track": self._tracks._parse_enums(track)}
        )
