"""Utility helpers and client for interacting with the Lexicon API."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional, Sequence

import requests

try:  # Choose notebook vs. console automatically when available
    from tqdm.auto import tqdm  # type: ignore
except Exception as exc:  # pragma: no cover - surface missing dependency clearly
    raise ImportError("tqdm is required for progress reporting") from exc

LEXICON_PORT = int(os.environ.get("LEXICON_PORT", "48624"))
DEFAULT_HOST = os.environ.get("LEXICON_HOST", "localhost")

TRACK_SOURCES: tuple[str, ...] = ("non-archived", "all", "archived", "incoming")

TRACK_FIELDS: tuple[str, ...] = (
    "id", "type", "title", "artist", "albumTitle", "label", "remixer", "mix", "composer", "producer", "grouping",
    "lyricist", "comment", "key", "genre", "bpm", "rating", "color", "year", "duration", "bitrate", "playCount",
    "location", "lastPlayed", "dateAdded", "dateModified", "sizeBytes", "sampleRate", "fileType", "trackNumber",
    "energy", "danceability", "popularity", "happiness", "extra1", "extra2", "tags", "importSource", "locationUnique",
    "tempomarkers", "cuepoints", "incoming", "archived", "archivedSince", "beatshiftCase", "fingerprint",
    "streamingService", "streamingId",
)

class LexiconClient:
    """Thin client for the Lexicon REST API."""

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: Optional[int | str] = None,
        default_timeout: int = 20,
    ) -> None:
        self.host = host or DEFAULT_HOST
        self.port = int(port or LEXICON_PORT)
        self.default_timeout = default_timeout
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    #  Metadata helpers
    # ------------------------------------------------------------------
    def available_track_sources(self) -> tuple[str, ...]:
        """Return the valid ``source`` selector values for endpoints."""

        return TRACK_SOURCES

    def available_track_fields(self) -> tuple[str, ...]:
        """Return the full list of track fields."""

        return TRACK_FIELDS

    # ------------------------------------------------------------------
    #  Low-level helpers
    # ------------------------------------------------------------------
    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"http://{self.host}:{self.port}{path}"

    # ------------------------------------------------------------------
    #  Playlist API Wrappers
    #   - See https://www.lexicondj.com/docs/developers/api
    # ------------------------------------------------------------------
    #region

    # GET /v1/playlists
    def get_playlists(self, *, timeout: Optional[int] = None) -> Optional[dict]:
        """
        Return the root folder dictionary via the ``/v1/playlists`` endpoint.
        """
        endpoint = self._build_url("/v1/playlists")
        try:
            response = requests.get(
                endpoint, 
                timeout=timeout or self.default_timeout
            )
            response.raise_for_status()
            payload = response.json() or {}
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not reach %s: %s", endpoint, exc)
            return None

        data = payload.get("data") if isinstance(payload, dict) else None
        playlists_root = data.get("playlists") if isinstance(data, dict) else None
        root_entry = playlists_root[0] if isinstance(playlists_root, list) and playlists_root else None

        if (isinstance(root_entry, dict) 
            and root_entry.get("type") == "1" 
            and root_entry.get("name") == "ROOT" 
            and isinstance(root_entry.get("playlists"), list)
            ):
            return root_entry

        self._logger.warning("Response did not contain expected root playlists structure")
        return None
        
    # GET /v1/playlist
    def get_playlist(self, playlist_id: int, *, timeout: Optional[int] = None) -> dict | None:
        """
        Get a single playlist from the Lexicon library by ID. Via ``/v1/playlist`` endpoint.

        ** Current known API issue: Retrieving the "ROOT" folder (ID 1) returns a non de-duplicated
        trackIds list. Use set(trackIds) to get unique IDs.
        """
        endpoint = self._build_url("/v1/playlist")
        try:
            response = requests.get(
                endpoint,
                params={"id": playlist_id},
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
            payload = response.json() or {}
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not reach %s: %s", endpoint, exc)
            return None
        
        data = payload.get("data") if isinstance(payload, dict) else None
        playlist = data.get("playlist") if isinstance(data, dict) else None

        if isinstance(playlist, dict):
            return playlist
        self._logger.warning("Playlist %s not found in response", playlist_id)
        return None
    
    # GET /v1/playlist-by-path
    def get_playlist_by_path(
        self,
        playlist_path: Sequence[str],
        playlist_type: Optional[int] = None,
        *,
        timeout: Optional[int] = None,
    ) -> dict | None:
        """
        Get a playlist from the Lexicon library by its folder path. 
        Via ``/v1/playlist-by-path`` endpoint.
        """
        endpoint = self._build_url("/v1/playlist-by-path")
        params: list[tuple[str, object]] = [("path", part) for part in playlist_path]
        if playlist_type is not None:
            params.append(("type", playlist_type))

        try:
            response = requests.get(
                endpoint,
                params=params,
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
            payload = response.json() or {}
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not reach %s: %s", endpoint, exc)
            return None

        data = payload.get("data") if isinstance(payload, dict) else None
        playlist = data.get("playlist") if isinstance(data, dict) else None
        
        if isinstance(playlist, dict):
            return playlist
        self._logger.warning("Playlist not found for provided path: %s", playlist_path)
        return None

    #endregion

    # ------------------------------------------------------------------
    #  Playlist Tools
    # ------------------------------------------------------------------
    #region

    def _choose_from_list(
        self,
        folder: dict,
        input_func: Callable[[str], str] = input,
        show_counts: bool = False,
    ) -> Optional[tuple[list[str], dict]]:
        """Interactively choose an item within ``folder``.

        ``0`` backs out (or cancels at the root). ``S`` selects the current folder.
        Numbered entries either drill into child folders (type ``1``) or select playlists
        (types ``2``/``3``).
        """

        if not folder.get("playlists"):
            print("No playlists available to choose from.")
            return None

        stack: list[tuple[dict, list[str]]] = [(folder, [])]
        count_cache: dict[Optional[int], Optional[int]] = {}

        while stack:
            # Get current folder and path from stack
            current_folder, current_path = stack[-1]
            
            # Get folder name and playlists
            current_name = current_folder.get("name", "(unnamed)")
            children = current_folder.get("playlists")

            # Clear screen between renders
            os.system("cls" if os.name == "nt" else "clear")

            # Generate track count suffix
            folder_suffix = ""
            if show_counts:
                id = current_folder.get("id")
                if id not in count_cache:
                    count_cache[id] = len(set(self.get_playlist(id)["trackIds"]))
                count_val = count_cache.get(id)
                folder_suffix = f" [{count_val if count_val is not None else '--'}]"
            
            # Print current folder
            if current_path:
                print(f"{' / '.join(current_path)}{folder_suffix} (Enter)")
            else:
                print(f"{current_name}{folder_suffix} (Enter)")

            # Print special options
            print("  C.    Cancel")
            if len(stack) > 1:
                print("  0. <- Back")

            # Print numbered entries
            for idx, item in enumerate(children, start=1):
                # Handles flat lists with "path" keys
                name = " / ".join(item.get("path", [])) or item.get("name", "(unnamed)")

                # Finds empty folders
                has_children = isinstance(item.get("playlists"), list) and bool(item.get("playlists"))
                
                # Determine type
                p_type = int(str(item.get("type", "0")) or 0)

                # Guide prefixes
                prefix = "   "
                if p_type == 1: # Folder
                    prefix = " > " if has_children else " - "

                # Generate track count suffix
                suffix = ""
                if show_counts:
                    id = item.get("id")
                    if id not in count_cache:
                        count_cache[id] = len(self.get_playlist(id)["trackIds"])
                    count_val = count_cache.get(id)
                    suffix = f" [{count_val if count_val is not None else '--'}]"

                print(f"{idx:>3}. {prefix}{name}{suffix}")

            # Prompt for input
            choice = input_func("\nSelect number (Enter: current folder, C: cancel)").strip()

            # Handle special inputs
            if not choice:
                playlist = self.get_playlist(current_folder.get("id")) # Fetch full details
                return playlist, current_path
            
            if choice.lower() == "c":
                print("Selection cancelled.")
                return None
            
            if choice == "0":
                if len(stack) > 1:
                    stack.pop()
                    continue
            
            # Handle invalid numeric input
            try:
                selection = int(choice)
            except ValueError:
                print(f"'{choice}' is not a valid number.")
                continue
            
            if selection < 1 or selection > len(children):
                print("Selection is out of range.")
                continue

            # Handle list selections
            selected = children[selection - 1]

            # Determine new path
            selected_name = selected.get("name", "")
            selected_has_path = bool(selected.get("path"))
            if selected_has_path and isinstance(selected.get("path"), list):
                new_path = selected.get("path", []) # Handle flat lists with "path" keys
            else:
                new_path = current_path + [selected_name] # Normal folder navigation

            # Check type
            selected_type = int(str(selected.get("type", "0")) or 0)

            # Playlist/Smartlist
            if selected_type in {2, 3}:
                playlist = self.get_playlist(selected.get("id")) # Fetch full details
                return playlist, new_path
            
            # Folder
            elif selected_type == 1:
                child_playlists = selected.get("playlists")
                if not isinstance(child_playlists, list) or not child_playlists:
                    print("Folder is empty; please choose another entry.")
                    continue
                stack.append((selected, new_path))

    def _flatten_tree(self, tree: dict, base_path=None) -> dict:
        """Return a shallow copy of ``tree`` with a flat ``playlists`` list.

        Runs recursively to gather all child playlists/folders into a single list.
        Path is preserved via a ``path`` key on each entry.

        Each child playlist/folder is cloned removing its own ``playlists`` key and
        receives a ``path`` list showing its ancestors. Folder entries (type ``1``)
        are re-labelled as type ``2`` so they can be treated as selectable by 
        ``_choose_from_list``.
        """
        # base_path = list(base_path or []) # Ensures we can append when empty
        flattened = [] # Accumulate all child entries here

        # Start with a shallow copy of the root without children
        root_dict = {k: v for k, v in tree.items() if k != "playlists"}

        # Add each child, recursing into folders
        for item in tree.get("playlists") or []:
            # Shallow copy without children
            cloned = {k: v for k, v in item.items() if k != "playlists"} 
            
            # Determine and set path
            item_name = item.get("name", "")
            item_path = (base_path + [item_name]) if base_path else [item_name]
            cloned["path"] = item_path

            # Re-label folders as selectable playlists
            if str(item.get("type")) == "1":
                cloned["type"] = "2"
            
            # Add to flat list
            flattened.append(cloned)

            # Recurse into folders
            if str(item.get("type")) == "1":
                flattened.extend(self._flatten_tree(item, item_path)["playlists"])
        
        # Add flat list to root copy and return
        root_dict["playlists"] = flattened
        return root_dict

    def choose_playlist(
        self,
        *,
        flat: bool = False,
        show_counts: bool = True,
        timeout: Optional[int] = None,
        input_func: Callable[[str], str] = input,
    ) -> Optional[tuple[dict, list[str]]]:
        """Fetch playlists and interactively choose one via stdin.

        Returns a tuple of (playlist_dict, path) or ``None`` if the user cancels.

        Parameters
        ----------
        flat: 
            When ``True`` presents a flattened list instead of navigating folders. Names are the full path.
        show_counts:
            When ``True`` (default) displays track counts by fetching each playlist's
            metadata; set to ``False`` to skip the extra API calls.
        """
        playlists = self.get_playlists(timeout=timeout)
        
        if not playlists:
            self._logger.warning("Unable to fetch playlists from Lexicon.")
            return None
        
        if not flat:
            input = playlists
            # print("Browsing playlist tree...\n")
        else:
            input = self._flatten_tree(playlists)
            # print("All playlists shown...\n")
        
        selection = self._choose_from_list(
            input,
            input_func=input_func,
            show_counts=show_counts,
        )
        if selection is None:
            self._logger.info("No playlist selected.")
        return selection

    #endregion

    # ------------------------------------------------------------------
    #  Track API Wrappers
    #   - See https://www.lexicondj.com/docs/developers/api
    # ------------------------------------------------------------------
    #region

    def get_track(self, track_id: int, *, timeout: Optional[int] = None) -> dict | None:
        """Fetch a single track's full info from Lexicon.
        Via the ``/v1/track`` endpoint.
        """
        endpoint = self._build_url("/v1/track")
        try:
            response = requests.get(
                endpoint,
                params={"id": track_id},
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
            payload = response.json() or {}
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not fetch track %s: %s", track_id, exc)
            return None
        
        data = payload.get("data") if isinstance(payload, dict) else None
        track = data.get("track") if isinstance(data, dict) else None

        if isinstance(track, dict):
            return track
        self._logger.warning("Track %s not found in response", track_id)
        return None
    
    def get_tracks(
        self,
        *,
        limit: Optional[int] = 1000,
        offset: Optional[int] = 0,
        source: Optional[str] = "non-archived",
        fields: Optional[Sequence[str]] = None,
        sort: Optional[Sequence[tuple[str, str | None]]] = None,
        timeout: Optional[int] = None,
        get_all: bool = False,
    ) -> list[dict]:
        """
        Fetch all tracks via the ``/v1/tracks`` endpoint.

        Parameters
        ----------
        limit / offset:
            Paging controls. Values below zero are clamped to zero.
        source:
            One of :meth:`available_track_sources`.
        fields:
            Iterable of field names to include. Use :meth:`available_track_fields`.
        sort:
            Temporarily unused until the upstream API clarifies the expected
            serialization. Any values supplied are currently ignored.
        get_all:
            When ``True``, fetches all pages of results. Otherwise only the first
            page is returned.
        """

        endpoint = self._build_url("/v1/tracks")
        params: list[tuple[str, object]] = []

        if limit is not None:
            params.append(("limit", max(int(limit), 0)))
        if source:
            params.append(("source", source))
        if fields:
            params.extend(("fields", field) for field in fields)

        if sort:
            self._logger.warning(
                "Track sorting is temporarily disabled pending clarified API docs; ignoring provided sort=%s",
                sort,
            )

        collected: list[dict] = []
        next_offset = max(int(offset or 0), 0)
        total_remaining = None

        while total_remaining is None or (total_remaining > 0 and get_all):
            page_params = list(params)
            page_params.append(("offset", next_offset))
            print(page_params)  # DEBUG

            try:
                response = requests.get(
                    endpoint,
                    params=page_params,
                    timeout=timeout or self.default_timeout,
                )
                response.raise_for_status()
                payload = response.json() or {}
            except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
                self._logger.warning("Could not fetch tracks from %s: %s", endpoint, exc)
                break

            data = payload.get("data") if isinstance(payload, dict) else None
            tracks = data.get("tracks") if isinstance(data, dict) else None

            if isinstance(tracks, list):
                collected.extend(tracks)
            else:
                self._logger.warning(
                    "Tracks response missing expected list; parameters were %s",
                    page_params,
                )
                break

            # Handle paging
            total = data.get("total") if isinstance(data, dict) else None
            page_limit = data.get("limit") if isinstance(data, dict) else None
            if isinstance(total, int) and isinstance(page_limit, int):
                if total_remaining:
                    total_remaining -= page_limit
                else:
                    total_remaining = total - page_limit
                next_offset += page_limit
            else:
                self._logger.warning(
                    "Tracks response missing expected total/limit; cannot page further. Returning first page only."
                )
                break  # Can't page without total/limit info

        return collected
            
    def search_tracks(
        self,
        filter: dict,
        *,
        source: Optional[str] = "non-archived",
        fields: Optional[Sequence[str]] = None,
        sort: Optional[Sequence[tuple[str, str | None]]] = None,
        timeout: Optional[int] = None,
    ) -> list[dict] | None:
        """
        Search for tracks via the ``/v1/search/tracks`` endpoint.
        Limited to 1000 results.

        Parameters
        ----------
        filter:
            Filter dictionary. 
            Keys are search fields, values are the search terms.
            Use :meth:`available_track_fields` for valid keys.
        source:
            One of :meth:`available_track_sources`.
        fields:
            Iterable of field names to include in response. Use :meth:`available_track_fields`.
        sort:
            Temporarily unused until the upstream API clarifies the expected
            serialization. Any values supplied are currently ignored.
        """

        endpoint = self._build_url("/v1/search/tracks")
        params: list[tuple[str, object]] = []

        if isinstance(filter, dict):
            for key, value in filter.items():
                if key in TRACK_FIELDS:
                    params.append((f"filter[{key}]", value))
                else:
                    self._logger.warning("Ignoring invalid track filter field: %s", key)
        if source:
            params.append(("source", source))
        if fields:
            params.extend(("fields", field) for field in fields)

        if sort:
            self._logger.warning(
                "Track sorting is temporarily disabled pending clarified API docs; ignoring provided sort=%s",
                sort,
            )

        try:
            response = requests.get(
                endpoint,
                params=params,
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
            payload = response.json() or {}
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not fetch tracks from %s: %s", endpoint, exc)
            return None

        data = payload.get("data") if isinstance(payload, dict) else None
        tracks = data.get("tracks") if isinstance(data, dict) else None

        total = data.get("total") if isinstance(data, dict) else None
        if isinstance(tracks, list):
            num_tracks = len(tracks)
            if isinstance(total, int) and total > num_tracks:
                self._logger.warning(
                    "Search matched %s total tracks but only %s were returned; consider narrowing search terms",
                    total,
                    num_tracks,
                )
            return tracks
        else:
            self._logger.warning(
                "Tracks response missing expected list; parameters were %s",
                params,
            )
            return None

    #endregion

    # ------------------------------------------------------------------
    #  Track Tools
    # ------------------------------------------------------------------
    #region

    def get_track_batch(
        self,
        track_ids: Iterable[int],
        *,
        max_workers: int = 5,
        timeout: Optional[int] = None,
    ) -> list[dict]:
        """
        Fetch metadata for a collection of tracks.
        
        Defaults to making 5 requests in parallel. 
        Set ``max_workers=0`` to fetch one at a time.
        More than 5 workers doesn't seem to improve speed but results may vary.
        """
        track_ids = list(track_ids)
        results: list[dict] = []

        if not track_ids:
            return results

        effective_timeout = timeout or self.default_timeout

        if max_workers == 0:
            for track_id in tqdm(track_ids, desc="Fetching tracks", unit=" tracks"):
                info = self.get_track(track_id, timeout=effective_timeout)
                if info:
                    results.append(info)
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.get_track, track_id, timeout=effective_timeout): track_id
                for track_id in track_ids
            }
            with tqdm(total=len(futures), desc="Fetching tracks (parallel)", unit=" tracks") as pbar:
                for future in as_completed(futures):
                    track_id = futures[future]
                    try:
                        info = future.result()
                        if info:
                            results.append(info)
                    except Exception as exc:  # noqa: BLE001 - handle worker failures gracefully
                        self._logger.warning("Track %s failed during fetch: %s", track_id, exc)
                    finally:
                        pbar.update(1)

        return results
    
    #endregion

    # ------------------------------------------------------------------
    #  Tag API Wrappers
    #   - See https://www.lexicondj.com/docs/developers/api
    # ------------------------------------------------------------------
    #region

    def get_tags(self, *, timeout: Optional[int] = None) -> dict | None:
        """Fetch all tags via the ``/v1/tags`` endpoint."""
        endpoint = self._build_url("/v1/tags")
        try:
            response = requests.get(
                endpoint,
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
            payload = response.json() or {}
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not reach %s: %s", endpoint, exc)
            return None
        
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict) and (isinstance(data.get("categories"), list) or isinstance(data.get("tags"), list)):
            return data

        self._logger.warning("Response did not contain expected tags structure")
        return None

__all__ = [
    "DEFAULT_HOST",
    "LEXICON_PORT",
    "LexiconClient",
]
