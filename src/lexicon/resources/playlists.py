"""Playlist resource wrapper."""

from __future__ import annotations

from typing import Optional, Sequence, TYPE_CHECKING, cast

from .base import Resource
from .playlists_types import (
    _normalize_playlist_type,
    _normalize_playlist_path,
    _normalize_smartlist,
    PlaylistResponse,
    PlaylistType,
)
from ._common_types import ValidationMode, _normalize_id_sequence
from ..tools.playlists import choose_playlist, get_path_from_tree
from ..utils import unique_in_order

if TYPE_CHECKING:  # pragma: no cover
    from .playlist_tracks import PlaylistTracks

class Playlists(Resource):
    """Playlist resource operations."""

    tracks: "PlaylistTracks"

    def get(
        self,
        playlist_id: int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> PlaylistResponse | None:
        """Fetch a playlist by ID.

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
        dict or None
            Playlist dict when found, otherwise ``None``.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id for get: {playlist_id}")
            if validation == "warn":
                self._logger.warning("Invalid playlist_id for get: %s", playlist_id)
            return None

        response = self._get("/playlist", params={"id": playlist_id}, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        playlist = data.get("playlist") if isinstance(data, dict) else None
        if isinstance(playlist, dict):
            track_ids = playlist.get("trackIds")
            if isinstance(track_ids, list):
                deduped = unique_in_order(track_ids)  # Needed since API returns concatenated tracklist for folders
                if len(deduped) != len(track_ids):
                    playlist = dict(playlist)
                    playlist["trackIds"] = deduped
            return cast(PlaylistResponse, playlist)
        self._logger.warning("Playlist %s not found in response", playlist_id)
        return None

    def get_many(
        self,
        playlist_ids: Sequence[int],
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[PlaylistResponse | None] | None:
        """Fetch multiple playlists by ID, preserving input order.

        Parameters
        ----------
        playlist_ids
            Sequence of playlist identifiers.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        list of dict or None
            Playlist dicts aligned with input IDs; invalid entries return ``None``, or ``None`` on validation error.
        """
        # When validation is off, pass input directly without transformation
        if validation == "off":
            ids = playlist_ids
        else:
            # Normalize input to list of IDs with validation
            ids = _normalize_id_sequence(playlist_ids)
            if ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid playlist_ids: {playlist_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid playlist_ids for get_many: %s", playlist_ids)
                    return None

        results: list[PlaylistResponse | None] = []
        for playlist_id in ids:
            results.append(self.get(playlist_id, validation="off", timeout=timeout))
        return results

    def list(
        self,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> PlaylistResponse | None:
        """Fetch the playlist tree root node.

        Parameters
        ----------
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        dict or None
            Root playlist folder dict, or ``None`` on failure. Note: the tree
            does not include track lists.
        """
        response = self._get("/playlists", timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        playlists = data.get("playlists") if isinstance(data, dict) else None
        if isinstance(playlists, list):
            root = playlists[0] if playlists else None
            if isinstance(root, dict):
                return cast(PlaylistResponse, root)
            self._logger.warning("Playlists response missing expected root entry.")
            return None
        self._logger.warning("Playlists response missing expected list.")
        return None

    def get_path(
        self,
        playlist_id: int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[str] | None:
        """Fetch the full folder path for a playlist ID.

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
        list[str] or None
            Folder path from root to playlist, or ``None`` when not found.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id for get_path: {playlist_id}")
            if validation == "warn":
                self._logger.warning("Invalid playlist_id for get_path: %s", playlist_id)
            return None

        root = self.list(validation=validation, timeout=timeout)
        if not isinstance(root, dict):
            return None
        root_dict = cast(dict[str, object], root)

        result = get_path_from_tree(cast(PlaylistResponse, root_dict), playlist_id)
        if result is None and validation == "warn":
            self._logger.warning("Playlist path not found for ID: %s", playlist_id)
        return result

    def choose(
        self,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> PlaylistResponse | None:
        """Interactively choose a playlist/folder from the tree.

        Parameters
        ----------
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        dict or None
            Selected playlist payload, or ``None`` if the user cancels.
        """
        tree = self.list(validation=validation, timeout=timeout)
        if not tree:
            return None
        selection = choose_playlist(tree)
        if not isinstance(selection, dict):
            return None
        playlist_id = selection.get("id")
        if isinstance(playlist_id, int):
            return self.get(playlist_id, validation=validation, timeout=timeout)
        return cast(PlaylistResponse, selection)

    def add(
        self,
        name: str,
        *,
        playlist_type: PlaylistType,
        parent_id: Optional[int] = None,
        smartlist: Optional[dict[str, object]] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> int | None:
        """Create a new playlist or folder.

        Parameters
        ----------
        name
            Playlist or folder name.
        playlist_type
            Playlist type code/name or integer (``"1"``/``"2"``/``"3"``).
        parent_id
            Parent folder ID. Omit to create at root.
        smartlist
            Smartlist rule payload for type ``"3"`` playlists.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        int or None
            New playlist ID on success, otherwise ``None``.
        """
        if not isinstance(name, str) or not name.strip():
            if validation == "strict":
                raise ValueError(f"Invalid playlist name: {name}")
            if validation == "warn":
                self._logger.warning("Invalid playlist name for add: %s", name)
            return None
        
        try:
            playlist_type_code = _normalize_playlist_type(playlist_type)
        except ValueError as e:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_type: {e}") from e
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid playlist_type for add: %s", playlist_type)
                return None
        
        if parent_id is not None and (not isinstance(parent_id, int) or parent_id < 1):
            if validation == "strict":
                raise ValueError(f"Invalid parent_id: {parent_id}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid parent_id for add: %s", parent_id)
                return None
        
        if smartlist is not None:
            normalized_smartlist = _normalize_smartlist(smartlist)
            if normalized_smartlist is None:
                if validation == "strict":
                    raise ValueError(f"Invalid smartlist payload: {smartlist}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid smartlist payload for add: %s", smartlist)
                    return None
            smartlist = normalized_smartlist

        payload: dict[str, object] = {"name": name, "type": playlist_type_code}
        if parent_id is not None:
            payload["parentId"] = parent_id
        if smartlist is not None:
            payload["smartlist"] = smartlist

        response = self._post("/playlist", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        playlist_id = data.get("id") if isinstance(data, dict) else None
        if isinstance(playlist_id, int):
            return playlist_id
        self._logger.warning("Create playlist response missing expected ID.")
        return None

    def update(
        self,
        playlist_id: int,
        *,
        name: Optional[str] = None,
        parent_id: Optional[int] = None,
        position: Optional[int] = None,
        smartlist: Optional[dict[str, object]] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> PlaylistResponse | None:
        """Update playlist properties.

        Parameters
        ----------
        playlist_id
            Playlist identifier.
        name
            New name for the playlist.
        parent_id
            New parent folder ID.
        position
            New position among siblings.
        smartlist
            Updated smartlist rule payload (type ``"3"``).
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        PlaylistResponse or None
            Updated playlist dict, or ``None`` on error.
        """
        if not isinstance(playlist_id, int) or playlist_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_id: {playlist_id}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid playlist_id for update: %s", playlist_id)
                return None
        
        if name is not None and (not isinstance(name, str) or not name.strip()):
            if validation == "strict":
                raise ValueError(f"Invalid playlist name: {name}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid playlist name for update: %s", name)
                return None
        
        if parent_id is not None and (not isinstance(parent_id, int) or parent_id < 1):
            if validation == "strict":
                raise ValueError(f"Invalid parent_id: {parent_id}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid parent_id for update: %s", parent_id)
                return None
        
        if position is not None and (not isinstance(position, int) or position < 0):
            if validation == "strict":
                raise ValueError(f"Invalid position: {position}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid position for update: %s", position)
                return None
        
        if smartlist is not None:
            normalized_smartlist = _normalize_smartlist(smartlist)
            if normalized_smartlist is None:
                if validation == "strict":
                    raise ValueError(f"Invalid smartlist payload: {smartlist}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid smartlist payload for update: %s", smartlist)
                    return None
            smartlist = normalized_smartlist

        payload: dict[str, object] = {"id": playlist_id}
        if name is not None:
            payload["name"] = name
        if parent_id is not None:
            payload["parentId"] = parent_id
        if position is not None:
            payload["position"] = position
        if smartlist is not None:
            payload["smartlist"] = smartlist

        if len(payload) == 1:
            self._logger.warning("No updates provided for playlist %s", playlist_id)
            return None

        response = self._patch("/playlist", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        playlist = data.get("playlist") if isinstance(data, dict) else None
        if isinstance(playlist, dict):
            track_ids = playlist.get("trackIds")
            if isinstance(track_ids, list):
                deduped = unique_in_order(track_ids)  # Needed since API returns concatenated tracklist for folders
                if len(deduped) != len(track_ids):  # pragma: no branch - exercised by tests
                    playlist = dict(playlist)
                    playlist["trackIds"] = deduped
            return cast(PlaylistResponse, playlist)
        self._logger.warning("Update playlist response missing expected playlist data.")
        return None

    def delete(
        self,
        playlist_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Delete one or more playlists.

        Parameters
        ----------
        playlist_ids
            Playlist ID or iterable of IDs.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        bool
            ``True`` when the delete request succeeds.
        """
        # When validation is off, pass input directly without transformation
        if validation == "off":
            payload = {"ids": playlist_ids}
        else:
            # Normalize input to list of IDs with validation
            ids = _normalize_id_sequence(playlist_ids)
            if ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid playlist_ids: {playlist_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid playlist_ids for delete: %s", playlist_ids)
                    return False
            payload = {"ids": ids}

        response = self._delete("/playlists", json=payload, timeout=timeout)
        return response is not None

    def get_by_path(
        self,
        playlist_path: Sequence[str],
        playlist_type: PlaylistType = '2',
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> PlaylistResponse | None:
        """Fetch a playlist by its folder path.

        Parameters
        ----------
        playlist_path
            Ordered folder path components.
        playlist_type
            Playlist type code/name or integer (defaults to ``"2"``).
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Request timeout in seconds.

        Returns
        -------
        dict or None
            Playlist dict when found, otherwise ``None``.
        """
        normalized_path = _normalize_playlist_path(playlist_path)
        if normalized_path is None:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_path: {playlist_path}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid playlist_path for get_by_path: %s", playlist_path)
            return None

        params: list[tuple[str, object]] = [("path", part) for part in normalized_path]
        try:
            playlist_type_code = _normalize_playlist_type(playlist_type)
        except ValueError as e:
            if validation == "strict":
                raise ValueError(f"Invalid playlist_type: {e}") from e
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid playlist_type for get_by_path: %s", playlist_type)
                return None
        params.append(("type", playlist_type_code))

        response = self._get("/playlist-by-path", params=params, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        playlist = data.get("playlist") if isinstance(data, dict) else None
        if isinstance(playlist, dict):
            return cast(PlaylistResponse, playlist)
        self._logger.warning("Playlist not found for provided path: %s", playlist_path)
        return None
