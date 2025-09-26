"""Utility helpers and client for interacting with the Lexicon API."""

from __future__ import annotations

import logging
import os
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional, Sequence

import requests

try:  # Prefer the rich notebook progress bar when available
    from tqdm.notebook import tqdm  # type: ignore
except Exception:  # pragma: no cover - fallback for non-notebook environments
    try:
        from tqdm import tqdm
    except Exception:  # pragma: no cover - if tqdm is completely unavailable
        class _NullTqdm:  # type: ignore
            def __init__(self, iterable=None, **_kwargs):
                self._iterable = iterable

            def __iter__(self):
                if self._iterable is None:
                    return iter([])
                return iter(self._iterable)

            def update(self, *_args, **_kwargs):
                return None

            def close(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                self.close()
                return False

        def tqdm(iterable=None, **kwargs):  # type: ignore
            return _NullTqdm(iterable, **kwargs)

LEXICON_PORT = int(os.environ.get("LEXICON_PORT", "48624"))
DEFAULT_HOST = os.environ.get("LEXICON_HOST", "localhost")

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
    # Low-level helpers
    # ------------------------------------------------------------------
    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"http://{self.host}:{self.port}{path}"

    # ------------------------------------------------------------------
    # API wrappers
    #  - See https://www.lexicondj.com/docs/developers/api
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    #   Playlist API
    # ------------------------------------------------------------------

    # GET /v1/playlists
    def get_playlists(self, *, timeout: Optional[int] = None) -> Optional[dict]:
        """Return the root folder dictionary from Lexicon."""
        endpoint = self._build_url("/v1/playlists")
        try:
            response = requests.get(
                endpoint, 
                timeout=timeout or self.default_timeout
            )
            response.raise_for_status()
            payload = response.json() or {}

            data = payload.get("data") if isinstance(payload, dict) else None
            playlists_root = data.get("playlists") if isinstance(data, dict) else None
            root_entry = playlists_root[0] if isinstance(playlists_root, list) and playlists_root else None

            if isinstance(root_entry, dict) and root_entry.get("root"):
                root_entry = root_entry.get("root")

            if isinstance(root_entry, dict):
                root_copy = copy.deepcopy(root_entry)
                root_copy.setdefault("name", root_copy.get("name") or "Root")
                root_copy.setdefault("playlists", root_copy.get("playlists") or [])
                return root_copy

            self._logger.warning("Response did not contain expected root playlists structure")
            return None
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not reach %s: %s", endpoint, exc)
            return None
        
    # GET /v1/playlist
    def get_playlist(self, playlist_id: int, *, timeout: Optional[int] = None) -> dict | None:
        """Get a single playlist from the Lexicon library by ID."""
        endpoint = self._build_url("/v1/playlist")
        try:
            response = requests.get(
                endpoint,
                params={"id": playlist_id},
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
            payload = response.json() or {}

            data = payload.get("data") if isinstance(payload, dict) else None
            playlist = data.get("playlist") if isinstance(data, dict) else None

            if isinstance(playlist, dict):
                return playlist
            self._logger.warning("Playlist %s not found in response", playlist_id)
            return None
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not reach %s: %s", endpoint, exc)
            return None
    
    # GET /v1/playlist-by-path
    def get_playlist_by_path(
        self,
        playlist_path: Sequence[str],
        playlist_type: Optional[int] = None,
        *,
        timeout: Optional[int] = None,
    ) -> dict | None:
        """Get a playlist from the Lexicon library by its folder path."""
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

            data = payload.get("data") if isinstance(payload, dict) else None
            playlist = data.get("playlist") if isinstance(data, dict) else None
            
            if isinstance(playlist, dict):
                return playlist
            self._logger.warning("Playlist not found for provided path: %s", playlist_path)
            return None
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not reach %s: %s", endpoint, exc)
            return None

    def flatten_tree(self, folder: dict, base_path=None):
        base_path = list(base_path or [])
        out_root = {k: v for k, v in folder.items() if k != "playlists"}
        flattened = []
        for item in folder.get("playlists") or []:
            name = item.get("name", "")
            current_path = base_path + [name]
            cloned = {k: v for k, v in item.items() if k != "playlists"}
            cloned["path"] = current_path
            if str(item.get("type")) == "1":
                cloned["type"] = "2"
            flattened.append(cloned)
            if str(item.get("type")) == "1":
                flattened.extend(self.flatten_tree(item, current_path)["playlists"])
        out_root["playlists"] = flattened
        return out_root


    def choose_from_list(
        self,
        folder: dict,
        path: Optional[list[str]] = None,
        input_func: Callable[[str], str] = input,
        show_counts: bool = False,
    ) -> Optional[tuple[list[str], dict]]:
        """Interactively choose an item within ``folder``.

        ``0`` backs out (or cancels at the root). ``S`` selects the current folder.
        Numbered entries either drill into child folders (type ``1``) or select playlists
        (types ``2``/``3``).
        """

        if not folder:
            print("No playlists available to choose from.")
            return None

        initial_path = list(path or [])
        folder_name = folder.get("name")
        if folder_name and not initial_path and folder_name != "ROOT":
            initial_path.append(folder_name)

        stack: list[tuple[dict, list[str]]] = [(folder, initial_path)]
        count_cache: dict[Optional[int], Optional[int]] = {}

        while stack:
            current_folder, current_path = stack[-1]
            children = current_folder.get("playlists")
            if not isinstance(children, list):
                children = []

            if current_path:
                print(" / ".join(current_path))

            if len(stack) > 1:
                print("  0. <- Back")
            else:
                print("  0. Cancel")

            current_name = current_folder.get("name", "(unnamed)")
            folder_suffix = ""
            if show_counts:
                identifier = current_folder.get("id")
                if identifier not in count_cache:
                    count_cache[identifier] = len(set(self.get_playlist(identifier)["trackIds"]))
                count_val = count_cache.get(identifier)
                folder_suffix = f" [{count_val if count_val is not None else '--'}]"
            print(f"  S. Select this folder ({current_name}){folder_suffix}")

            for idx, item in enumerate(children, start=1):
                name = " / ".join(item.get("path", [])) or item.get("name", "(unnamed)")
                child_playlists = item.get("playlists")
                has_children = isinstance(child_playlists, list) and bool(child_playlists)
                p_type = int(str(item.get("type", "0")) or 0)

                prefix = "  "
                if p_type == 1:
                    prefix = "> " if has_children else "- "

                suffix = ""
                if show_counts:
                    identifier = item.get("id")
                    if identifier not in count_cache:
                        count_cache[identifier] = len(self.get_playlist(identifier)["trackIds"])
                    count_val = count_cache.get(identifier)
                    suffix = f" [{count_val if count_val is not None else '--'}]"

                print(f"{idx:>3}. {prefix}{name}{suffix}")

            choice = input_func("\nEnter a playlist number (press Enter to cancel): ").strip()
            if not choice:
                print("No selection made; exiting.")
                return None

            if choice == "0":
                if len(stack) > 1:
                    stack.pop()
                    continue
                return None

            if choice.lower() == "s":
                folder_copy = dict(current_folder)
                if show_counts:
                    identifier = current_folder.get("id")
                    if identifier not in count_cache:
                        count_cache[identifier] = len(self.get_playlist(identifier)["trackIds"])
                    count_val = count_cache.get(identifier)
                    try:
                        folder_copy["numTracks"] = (
                            count_val if count_val is None else int(count_val)
                        )
                    except (TypeError, ValueError):
                        folder_copy["numTracks"] = None
                return (current_path or [current_name]), folder_copy

            try:
                selection = int(choice)
            except ValueError:
                print(f"'{choice}' is not a valid number.")
                continue

            if selection < 1 or selection > len(children):
                print("Selection is out of range.")
                continue

            selected = children[selection - 1]
            selected_name = selected.get("name", "")
            selected_type = int(str(selected.get("type", "0")) or 0)
            child_playlists = selected.get("playlists")
            new_path = current_path + [selected_name]

            if selected_type in {2, 3}:
                selected_copy = dict(selected)
                if show_counts:
                    identifier = selected.get("id")
                    if identifier not in count_cache:
                        count_cache[identifier] = len(self.get_playlist(identifier)["trackIds"])
                    count_val = count_cache.get(identifier)
                    try:
                        selected_copy["numTracks"] = (
                            count_val if count_val is None else int(count_val)
                        )
                    except (TypeError, ValueError):
                        selected_copy["numTracks"] = None
                return new_path, selected_copy

            if not isinstance(child_playlists, list) or not child_playlists:
                print("Folder is empty; please choose another entry.")
                continue

            stack.append((selected, new_path))

    def choose_playlist(
        self,
        *,
        flat: bool = False,
        show_counts: bool = True,
        timeout: Optional[int] = None,
        input_func: Callable[[str], str] = input,
    ) -> Optional[tuple[list[str], dict]]:
        """Fetch playlists and interactively choose one via stdin.

        Returns a tuple of (path, playlist_dict) or ``None`` if the user cancels.

        Parameters
        ----------
        flat:
            When ``True`` presents a flattened list instead of navigating folders.
        show_counts:
            When ``True`` (default) displays track counts by fetching each playlist's
            metadata; set to ``False`` to skip the extra API calls.
        """
        playlists = self.get_playlists(timeout=timeout)
        
        if not playlists:
            self._logger.warning("Unable to fetch playlists from Lexicon.")
            return None
        
        if not flat:
            print("Browsing playlist tree. Pick one by number:\n")
            selection = self.choose_from_list(
                playlists,
                path=[],
                input_func=input_func,
                show_counts=show_counts,
            )
            if selection is None:
                self._logger.info("No playlist selected.")
            return selection
        else:
            print("All playlists shown. Pick one by number:\n")
            flattened = self.flatten_tree(playlists)
            selection = self.choose_from_list(
                flattened,
                path=[],
                input_func=input_func,
                show_counts=show_counts,
            )
            if selection is None:
                self._logger.info("No playlist selected.")
            return selection

    def get_track_info(self, track_id: int, *, timeout: Optional[int] = None) -> dict | None:
        """Fetch a single track's full info from Lexicon."""
        endpoint = self._build_url("/v1/track")
        try:
            response = requests.get(
                endpoint,
                params={"id": track_id},
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
            return response.json()["data"]["track"]
        except Exception as exc:  # noqa: BLE001 - expose networking failures to caller
            self._logger.warning("Could not fetch track %s: %s", track_id, exc)
            return None

    def get_track_data_batch(
        self,
        track_ids: Iterable[int],
        *,
        max_workers: int = 4,
        timeout: Optional[int] = None,
    ) -> list[dict]:
        """Fetch metadata for a collection of tracks, optionally in parallel."""
        track_ids = list(track_ids)
        results: list[dict] = []

        if not track_ids:
            return results

        effective_timeout = timeout or self.default_timeout

        if max_workers == 0:
            for track_id in tqdm(track_ids, desc="Fetching tracks", unit=" tracks"):
                info = self.get_track_info(track_id, timeout=effective_timeout)
                if info:
                    results.append(info)
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.get_track_info, track_id, timeout=effective_timeout): track_id
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


__all__ = [
    "DEFAULT_HOST",
    "LEXICON_PORT",
    "LexiconClient",
]
