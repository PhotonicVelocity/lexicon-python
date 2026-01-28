"""Types and validation helpers for playlists resource."""

from __future__ import annotations

from typing import Literal, Sequence, TypedDict, get_args
from typing_extensions import ReadOnly

class PlaylistResponse(TypedDict, total=False):
    """Readonly playlist dict returned by playlist endpoints."""
    id: ReadOnly[int]
    name: ReadOnly[str]
    dateAdded: ReadOnly[str]
    type: ReadOnly[PlaylistTypeCode]
    folderType: ReadOnly[PlaylistFolderType | None]
    parentId: ReadOnly[int]
    position: ReadOnly[int]
    trackIds: ReadOnly[list[int]]
    smartlist: ReadOnly[dict[str, object]]

# --- Playlist Type Definitions --- #
PlaylistTypeInt = Literal[1, 2, 3]
PlaylistTypeCode = Literal["1", "2", "3"]
PlaylistTypeName = Literal["folder", "playlist", "smartlist"]
PlaylistType = PlaylistTypeCode | PlaylistTypeInt | PlaylistTypeName
PLAYLIST_TYPE_CODES: tuple[PlaylistTypeCode, ...] = get_args(PlaylistTypeCode)
PLAYLIST_TYPE_NAMES: tuple[PlaylistTypeName, ...] = get_args(PlaylistTypeName)

PlaylistFolderType = Literal["1", "2"]


def _normalize_playlist_type(playlist_type: PlaylistType | object) -> PlaylistTypeCode:
    """Normalize playlist type input to string numeric codes.
    
    Parameters
    ----------
    playlist_type
        Playlist type: int (1/2/3), string code ("1"/"2"/"3"), 
        or name ("folder"/"playlist"/"smartlist").
    
    Returns
    -------
    PlaylistTypeCode
        Normalized type code ("1", "2", or "3").
    
    Raises
    ------
    ValueError
        If the type cannot be parsed or is invalid.
    """
    if isinstance(playlist_type, int):
        if playlist_type in (1, 2, 3):
            return PLAYLIST_TYPE_CODES[playlist_type - 1]
        raise ValueError(f"Invalid playlist type: {playlist_type}")
    if playlist_type in PLAYLIST_TYPE_CODES:
        return playlist_type
    if playlist_type in PLAYLIST_TYPE_NAMES:
        return PLAYLIST_TYPE_CODES[PLAYLIST_TYPE_NAMES.index(playlist_type)]
    raise ValueError(f"Invalid playlist type: {playlist_type}")


# --- Other Normalization Helpers --- #
def _normalize_playlist_path(playlist_path: Sequence[str] | object) -> list[str] | None:
    """Normalize playlist path to validated component list.
    
    Parameters
    ----------
    playlist_path
        Ordered folder path components. Must be a sequence of non-empty strings.
    
    Returns
    -------
    list[str] | None
        Validated path components (stripped), or None if invalid.
        - Returns None if not a sequence (or is str/bytes)
        - Returns None if empty after stripping
        - Returns None if any component is not a string or is empty
    """
    if not isinstance(playlist_path, Sequence) or isinstance(playlist_path, (str, bytes)):
        return None
    
    components: list[str] = []
    for component in playlist_path:
        if not isinstance(component, str):
            return None
        stripped = component.strip()
        if not stripped:
            return None
        components.append(stripped)
    
    return components if components else None


def _normalize_smartlist(smartlist: dict | object) -> dict | None:
    """Normalize smartlist payload dict.
    
    Parameters
    ----------
    smartlist
        Smartlist rule payload. Must be a dict; full schema validation 
        is deferred to the API.
    
    Returns
    -------
    dict | None
        The smartlist dict as-is, or None if not a dict.
    """
    if not isinstance(smartlist, dict):
        return None
    return smartlist
