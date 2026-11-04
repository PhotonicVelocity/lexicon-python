"""Core Lexicon client with a raw-request escape hatch."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests

from .resources._common_types import ValidationMode
from .resources.control_types import CONTROL_ACTIONS, ControlAction
from .resources.player import Player
from .resources.playlist_tracks import PlaylistTracks
from .resources.playlists import Playlists
from .resources.tag_categories import TagCategories
from .resources.tags import Tags
from .resources.tracks import Tracks
from .tools import playlists as playlist_tools
from .tools import tracks as track_tools

DEFAULT_HOST = os.environ.get("LEXICON_HOST", "localhost")
LEXICON_PORT = int(os.environ.get("LEXICON_PORT", "48624"))


class LexiconConnectionError(ConnectionError):
    """Raised when the client cannot reach the Lexicon Local API on construction."""


class Tools:
    """Namespace for helper tools."""

    playlists = playlist_tools
    tracks = track_tools


class Lexicon:
    """Resource-grouped client for the Lexicon Local API."""

    tracks: Tracks
    playlists: Playlists
    tags: Tags
    player: Player
    tools: Tools

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: Optional[int | str] = None,
        default_timeout: int = 20,
        session: Optional[requests.Session] = None,
        raise_on_error: bool = False,
        raw_enums: bool = True,
        verify_connection: bool = True,
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
        raw_enums
            If True (default), return API enum values as raw codes (e.g. ``"1"``).
            If False, convert to human-readable names (e.g. ``"normal"``).
        verify_connection
            If True (default), probe the Lexicon API on construction and raise
            :class:`LexiconConnectionError` if it isn't reachable. Set to False
            to construct without a running Lexicon (e.g. for tests).
        """
        self.host = host or DEFAULT_HOST
        self.port = int(port or LEXICON_PORT)
        self.default_timeout = default_timeout
        self.raise_on_error = raise_on_error
        self.raw_enums = raw_enums
        self._logger = logging.getLogger(__name__)
        self._session = session

        self.tracks: Tracks = Tracks(self)
        self.playlists: Playlists = Playlists(self)
        self.playlists.tracks = PlaylistTracks(
            self, tracks=self.tracks, playlists=self.playlists
        )
        self.tags: Tags = Tags(self)
        self.tags.categories = TagCategories(self)
        self.player: Player = Player(self, tracks=self.tracks)
        self.tools = Tools()

        if verify_connection:
            self._verify_connection()

    def _verify_connection(self) -> None:
        """Probe the Lexicon API to confirm it's reachable.

        Sends a single ``GET /v1/playing`` request, bypassing the swallow-and-warn
        behavior of :meth:`request`. Logs at INFO on success; raises
        :class:`LexiconConnectionError` on any failure.
        """
        url = f"http://{self.host}:{self.port}/v1/playing"
        requester = self._session or requests
        try:
            response = requester.request("GET", url, timeout=self.default_timeout)
            response.raise_for_status()
        except (
            requests.ConnectionError,
            requests.Timeout,
            requests.HTTPError,
        ) as exc:
            raise LexiconConnectionError(
                f"Could not reach Lexicon at {self.host}:{self.port} "
                f"({exc.__class__.__name__}: {exc}). "
                "Is Lexicon running with the Local API enabled?"
            ) from exc
        self._logger.info("Connected to Lexicon at %s:%s", self.host, self.port)

    def control(
        self,
        action: ControlAction,
        /,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
        **parameters: Any,
    ) -> bool:
        """Run a Lexicon command, the same ones that can be bound to a hotkey.

        Parameters
        ----------
        action
            Action name, such as ``"MusicPlayer_Eject"``.
        validation
            Validation mode: ``"off"`` sends any action name, ``"warn"`` logs a
            name missing from ``ControlAction`` and sends nothing, and ``"strict"``
            raises on one. Use ``"off"`` for
            ``PluginRunAction_<pluginId>:<actionId>``, which is not in the list.
        timeout
            Timeout in seconds for this request.
        **parameters
            The action's parameters under their API names, such as
            ``lex.control("MusicPlayer_Load", id=123)``. See the Control Actions
            schema in ``docs/lexicon-api-docs.yaml``.

        Returns
        -------
        bool
            True if Lexicon accepted the request, otherwise False.

        Notes
        -----
        True does not mean the action did anything. Lexicon returns before the
        action finishes, has no completion signal, and accepts an action whose
        target is missing, such as a hotkey for the selected tracks with nothing
        selected, or ``MusicPlayer_Load`` without ``id``.

        ``ControlAction`` follows the newest spec, so it can name actions that the
        running Lexicon rejects. See ``docs/api-issues.md``.
        """
        if validation != "off" and action not in CONTROL_ACTIONS:
            if validation == "strict":
                raise ValueError(f"Invalid action for control: {action}")
            self._logger.warning("Invalid action for control: %s", action)
            return False

        payload: dict[str, Any] = {"action": action}
        if parameters:
            payload["parameters"] = parameters
        response = self.request("POST", "/control", json=payload, timeout=timeout)
        # Lexicon 1.11.15 answers HTTP 200 with only a "message" when a handler throws
        # an error that has no code. See docs/api-issues.md.
        return isinstance(response, dict) and "message" not in response

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
