"""Core Lexicon client with a raw-request escape hatch."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests

from .resources.playlist_tracks import PlaylistTracks
from .resources.playlists import Playlists
from .resources.tag_categories import TagCategories
from .resources.tags import Tags
from .resources.tracks import Tracks
from .tools import playlists as playlist_tools
DEFAULT_HOST = os.environ.get("LEXICON_HOST", "localhost")
LEXICON_PORT = int(os.environ.get("LEXICON_PORT", "48624"))


class Lexicon:
    """Resource-grouped client for the Lexicon Local API."""

    tracks: Tracks
    playlists: Playlists
    tags: Tags
    tools: Any

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: Optional[int | str] = None,
        default_timeout: int = 20,
        session: Optional[requests.Session] = None,
        raise_on_error: bool = False,
    ) -> None:
        """Create a Lexicon client bound to an API instance.

        Parameters
        ----------
        host
            Hostname or IP for the Lexicon API.
        port
            API port number.
        default_timeout
            Default request timeout in seconds.
        session
            Optional requests session to reuse connections.
        raise_on_error
            If True, raise HTTP errors instead of returning None.
        """
        self.host = host or DEFAULT_HOST
        self.port = int(port or LEXICON_PORT)
        self.default_timeout = default_timeout
        self.raise_on_error = raise_on_error
        self._logger = logging.getLogger(__name__)
        self._session = session

        self.tracks: Tracks = Tracks(self)
        self.playlists: Playlists = Playlists(self)
        self.playlists.tracks = PlaylistTracks(self, tracks=self.tracks, playlists=self.playlists)
        self.tags: Tags = Tags(self)
        self.tags.categories = TagCategories(self)
        self.tools = type("Tools", (), {})()
        self.tools.playlists = playlist_tools

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any] | list[tuple[str, Any]]] = None,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[dict[str, Any] | list[Any]]:
        """Send a raw request to the Lexicon API.

        Parameters
        ----------
        method
            HTTP method (GET, POST, PATCH, DELETE).
        path
            Endpoint path, with or without a leading `/v1`.
        params
            Query parameters for the request.
        json
            JSON payload for the request.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        dict | list | None
            Parsed JSON payload, or None if the response is empty or non-JSON.
        """
        if not path.startswith("/"):
            path = "/" + path
        if not path.startswith("/v1/"):
            path = "/v1" + path
        url = f"http://{self.host}:{self.port}{path}"

        requester = self._session or requests
        try:
            response = requester.request(
                method,
                url,
                params=params,
                json=json,
                timeout=timeout or self.default_timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            if self.raise_on_error:
                raise
            # Extract error message from response body if available
            error_msg = str(exc)
            try:
                error_body = response.json()
                if isinstance(error_body, dict):
                    # Try common error message fields
                    if "message" in error_body:
                        error_msg = f"{exc}\nServer message: {error_body['message']}"
                    elif "error" in error_body:
                        error_msg = f"{exc}\nServer error: {error_body['error']}"
                    elif "detail" in error_body:
                        error_msg = f"{exc}\nDetails: {error_body['detail']}"
            except (ValueError, AttributeError, KeyError):
                pass  # Response wasn't JSON or didn't have expected fields
            self._logger.warning("Request failed for %s %s: %s", method, url, error_msg)
            return None
        except Exception as exc:  # noqa: BLE001 - surface request failures
            if self.raise_on_error:
                raise
            self._logger.warning("Request failed for %s %s: %s", method, url, exc)
            return None

        if not response.content:
            return None
        try:
            payload = response.json()
        except ValueError:  # noqa: PERF203 - only attempt JSON when present
            self._logger.warning("Response from %s %s was not JSON", method, url)
            return None
        if isinstance(payload, (dict, list)):
            return payload
        return None
