"""Playlist tracks nested resource."""

from __future__ import annotations

from typing import Optional, Sequence, cast

from .base import Resource
from .playlists import Playlists
from .playlists_types import PlaylistResponse
from .tracks import Tracks
from .tracks_types import TrackResponse
from ._common_types import ValidationMode, _normalize_id_sequence
from ..utils import unique_in_order


class PlaylistTracks(Resource):
    """Track operations scoped to a playlist."""

    def __init__(self, client, *, tracks: Tracks, playlists: Playlists) -> None:
        """Initialize playlist track helpers.

        Parameters
        ----------
        client
            Core Lexicon client instance.
        tracks
            Tracks resource wrapper.
        playlists
            Playlists resource wrapper.
        """
        super().__init__(client)
        self._tracks = tracks
        self._playlists = playlists


    def get(
        self,
        playlist_id: int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TrackResponse | None] | None:
        """Return full track dicts for a playlist, preserving order.

        Parameters
        ----------
        playlist_id
            Playlist identifier.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        list[TrackResponse | None] or None
            Track dicts aligned with playlist order, or ``None`` on failure.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id: {playlist_id}")
            if validation == "warn":
                self._logger.warning("Invalid playlist_id for remove: %s", playlist_id)
            return None
        
        track_ids = self.list(playlist_id, validation=validation, timeout=timeout)
        if track_ids is None:
            return None
        if not track_ids:
            return []
        return self._tracks.get_many(track_ids, validation="off", timeout=timeout)
    

    def list(
        self,
        playlist_id: int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[int] | None:
        """Return the track ID list for a playlist.

        Parameters
        ----------
        playlist_id
            Playlist identifier.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        list[int] or None
            Track IDs in playlist order, or ``None`` on failure.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id: {playlist_id}")
            if validation == "warn":
                self._logger.warning("Invalid playlist_id for list: %s", playlist_id)
            return None

        playlist = self._playlists.get(playlist_id, validation="off", timeout=timeout)
        if playlist is None:
            return None

        track_ids = cast(PlaylistResponse, playlist).get("trackIds")
        if isinstance(track_ids, list):
            return [track_id for track_id in track_ids if isinstance(track_id, int)]
        self._logger.warning("Playlist %s missing expected trackIds list", playlist_id)
        return None
    

    def add(
        self,
        playlist_id: int,
        track_ids: Sequence[int] | int,
        *,
        index: Optional[int] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Add tracks to a playlist.

        Parameters
        ----------
        playlist_id
            Playlist identifier.
        track_ids
            Track ID or list of track IDs to append.
        index
            Optional insert position (0-based).
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        bool
            ``True`` when the add request succeeds.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id: {playlist_id}")
            if validation == "warn":
                self._logger.warning("Invalid playlist_id for add: %s", playlist_id)
            return False
        
        # When validation is off, pass input directly without transformation
        if validation == "off":
            normalized_ids = [track_ids] if isinstance(track_ids, int) else track_ids
        else:
            # Normalize input to list of IDs with validation
            normalized_ids = _normalize_id_sequence(track_ids)
            if normalized_ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid track_ids: {track_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid track_ids for add: %s", track_ids)
                    return False
        
        if index is not None and (not isinstance(index, int) or index < 0):
            if validation == "strict":
                raise ValueError(f"Invalid index: {index}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid index for add: %s", index)
                return False

        payload: dict[str, object] = {"id": playlist_id, "trackIds": normalized_ids}
        if index is not None:
            payload["index"] = index

        response = self._patch("/playlist-tracks", json=payload, timeout=timeout)
        return response is not None

    def remove(
        self,
        playlist_id: int,
        track_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Remove tracks from a playlist.

        Parameters
        ----------
        playlist_id
            Playlist identifier.
        track_ids
            Track ID or list of track IDs to remove.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        bool
            ``True`` when the remove request succeeds.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id: {playlist_id}")
            if validation == "warn":
                self._logger.warning("Invalid playlist_id for remove: %s", playlist_id)
            return False
        
        # When validation is off, pass input directly without transformation
        if validation == "off":
            normalized_ids = [track_ids] if isinstance(track_ids, int) else track_ids
        else:
            # Normalize input to list of IDs with validation
            normalized_ids = _normalize_id_sequence(track_ids)
            if normalized_ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid track_ids: {track_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid track_ids for remove: %s", track_ids)
                    return False
        
        payload = {"id": playlist_id, "trackIds": normalized_ids}
        response = self._delete("/playlist-tracks", json=payload, timeout=timeout)
        return response is not None

    def update(
        self,
        playlist_id: int,
        track_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Replace a playlist's track list by removing all then adding new tracks.

        Parameters
        ----------
        playlist_id
            Playlist identifier.
        track_ids
            Track ID or list of track IDs to set.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        bool
            ``True`` when the update request succeeds.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id: {playlist_id}")
            if validation == "warn":
                self._logger.warning("Invalid playlist_id for update: %s", playlist_id)
            return False

        playlist = self._playlists.get(playlist_id, validation="off", timeout=timeout)
        if playlist is None:
            return False

        playlist_type = cast(PlaylistResponse, playlist).get("type")
        if playlist_type is not None and str(playlist_type) != "2":
            if validation == "strict":
                raise ValueError(f"Playlist {playlist_id} is not a normal playlist (type=2)")
            if validation == "warn":
                self._logger.warning("Playlist %s is not a normal playlist (type=2)", playlist_id)
            return False

        existing_ids = cast(PlaylistResponse, playlist).get("trackIds")
        if isinstance(existing_ids, list) and existing_ids:
            if not self.remove(playlist_id, existing_ids, validation="off", timeout=timeout):
                return False

        # When validation is off, pass input directly without transformation
        if validation == "off":
            normalized_ids = [track_ids] if isinstance(track_ids, int) else track_ids
        else:
            # Normalize input to list of IDs with validation
            normalized_ids = _normalize_id_sequence(track_ids)
            if normalized_ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid track_ids: {track_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid track_ids for update: %s", track_ids)
                    return False
        if not normalized_ids:
            return True

        return self.add(playlist_id, normalized_ids, index=0, validation="off", timeout=timeout)
