"""Track resource wrapper."""

from __future__ import annotations

import builtins
from typing import Optional, Sequence, Literal, Mapping, cast

from .base import Resource
from .tracks_types import (
    TRACK_SOURCES,
    FilterField,
    SortInput,
    TempoMarkerUpdate,
    TempoRange,
    TrackEditField,
    TrackField,
    TrackSource,
    TrackResponse,
    TrackUpdate,
    _normalize_edits,
    _normalize_fields,
    _normalize_filters,
    _normalize_sorts,
    _normalize_tempo_range,
    _cuepoint_type_name,
)
from ..tools.tempo import beats_to_seconds, seconds_to_beats
from ._common_types import ValidationMode, _normalize_id_sequence

# Lexicon 1.11.13 rejects the name older specs gave this action, "TrackBrowser_AnalyzeStart", with
# HTTP 400 and accepts only this internal id, which the spec has documented since 2026-11-01.
ANALYZE_ACTION = "AudioAnalyzer_Analyze"

# GET /track and PATCH /track take this in place of an ID for the selection in Lexicon
# (v1.12 and newer).
SELECTED = "selected"

# Search pages hold at most this many tracks.
PAGE_SIZE = 1000


def _is_track_ref(track_id: object) -> bool:
    """Report whether a value is a track ID or ``"selected"``."""
    if track_id == SELECTED:
        return True
    return (
        isinstance(track_id, int) and not isinstance(track_id, bool) and track_id >= 1
    )


class Tracks(Resource):
    """Track resource operations."""

    def _parse_enums(self, track: dict) -> dict:
        """Convert enum codes to names if raw_enums is disabled."""
        if self._client.raw_enums:
            return track
        track = dict(track)
        cuepoints = track.get("cuepoints")
        if isinstance(cuepoints, list):
            track["cuepoints"] = [
                {**cp, "type": _cuepoint_type_name(str(cp["type"]))}
                if isinstance(cp, dict) and "type" in cp
                else cp
                for cp in cuepoints
            ]
        return track

    def get(
        self,
        track_id: int | Literal["selected"],
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Fetch a single track by ID.

        Parameters
        ----------
        track_id
            Track ID to fetch, or ``"selected"`` for the track selected in Lexicon
            (the topmost one when several are selected; see :meth:`selected`).
            ``"selected"`` needs Lexicon v1.12 or newer, and fails with error code
            113 when no track is selected.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        dict | None
            Track dict, or None if not found or on error.
        """
        if not _is_track_ref(track_id):
            if validation == "strict":
                raise ValueError(f"Invalid track_id for get: {track_id}")
            if validation == "warn":
                self._logger.warning("Invalid track_id for get: %s", track_id)
                return None

        response = self._get("/track", params={"id": track_id}, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        track = data.get("track") if isinstance(data, dict) else None
        if isinstance(track, dict):
            return cast(TrackResponse, self._parse_enums(track))
        self._logger.warning("Track %s not found in response", track_id)
        return None

    def selected(self, *, timeout: Optional[int] = None) -> builtins.list[int] | None:
        """Fetch the IDs of the tracks selected in Lexicon.

        The selection is the one in the track browser the user last worked in, in
        the order Lexicon shows it. Needs Lexicon v1.12 or newer.

        Parameters
        ----------
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        list of int | None
            Selected track IDs, empty when nothing is selected or no track browser
            is open, or None on error (including Lexicon v1.11 and older).
        """
        response = self._get("/tracks/selected", timeout=timeout)
        data = response.get("data") if isinstance(response, dict) else None
        ids = data.get("ids") if isinstance(data, dict) else None
        if isinstance(ids, list):
            return [track_id for track_id in ids if isinstance(track_id, int)]
        if response is not None:
            self._logger.warning("Selected tracks response missing expected ids.")
        return None

    def get_many(
        self,
        track_ids: Sequence[int],
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TrackResponse | None] | None:
        """Fetch multiple tracks by ID, preserving input order.

        Parameters
        ----------
        track_ids
            Sequence of track IDs to fetch.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        list of dict | None
            Track dicts (or None for each missing ID).
        """
        if validation == "off":
            # Pass through without any validation
            ids = track_ids
        else:
            # Normalize and validate
            ids = _normalize_id_sequence(track_ids)
            if ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid track_ids for get_many: {track_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning(
                        "Invalid track_ids for get_many: %s", track_ids
                    )
                    return None

        # Always fetch IDs to estimate library size for the 5% cutoff.
        all_ids = self.list(fields=["id"], timeout=timeout)
        if not all_ids:
            return [
                self.get(track_id, timeout=timeout) if track_id in ids else None
                for track_id in ids
            ]

        # Large requests are considered to be > 5% of total library size
        cutoff = len(all_ids) * 0.05

        # Get all tracks and trim by id for large requests
        if len(ids) >= cutoff:
            all_tracks = self.list(fields="all", timeout=timeout) or []
            by_id = {
                track.get("id"): track
                for track in all_tracks
                if isinstance(track, dict)
            }
            return [
                by_id.get(cast(int, track_id))
                if isinstance(track_id, int) and track_id in ids
                else None
                for track_id in ids
            ]

        # Get tracks one-by-one for small requests
        return [
            self.get(cast(int, track_id), timeout=timeout)
            if isinstance(track_id, int) and track_id in ids
            else None
            for track_id in ids
        ]

    def list(
        self,
        *,
        limit: Optional[int] = None,
        source: Optional[TrackSource] = "non-archived",
        fields: Optional[Sequence[TrackField] | Literal["all", "*"]] = None,
        sort: Optional[SortInput] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TrackResponse] | None:
        """List tracks with optional paging and field selection.

        Parameters
        ----------
        limit
            Maximum number of tracks to return. If None, fetches all pages.
        source
            Track source filter (e.g., "non-archived").
        fields
            Fields to include in each track dict.
            - For a subset, pass a list of field names:
              ``fields=["id", "location"]``. The API accepts the projection
              and the response is correspondingly narrower.
            - Use ``"all"`` or ``"*"`` to request every field the API exposes.
            - ``None`` returns ``DEFAULT_TRACK_FIELDS`` — a curated default
              that omits expensive fields like ``cuepoints`` / ``tempomarkers``.
            - Comma-separated strings (e.g. ``"id,location"``) are *not*
              accepted; use a list. With validation ``"warn"`` (default) the
              call falls back to ``DEFAULT_TRACK_FIELDS`` and logs.
            - With validation ``"off"``, ``None`` returns all fields and a
              list is passed to the API as-is.
        sort
            Sort fields and directions.
            - API native: list of dicts with ``"field"`` and optional ``"dir"`` keys
            - Alternative: list of tuples ``(field, dir)``
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        list of dict | None
            List of track dicts, or ``None`` on API error.

        Examples
        --------
        Narrow projection — useful for resolving file paths to ids without
        pulling tempomarkers, cuepoints, etc.::

            >>> lex.tracks.list(fields=["id", "location"], limit=100)
            [{"id": 499, "location": "..."}, ...]
        """
        payload: dict[str, object] = {}

        # Source - validate and add to payload
        if source:
            if source in TRACK_SOURCES:
                payload["source"] = source
            elif validation == "off":
                payload["source"] = source
            elif validation == "strict":
                raise ValueError(f"Invalid track source: {source}")
            else:
                self._logger.warning(
                    "Ignoring invalid track source: %s", source
                )  # pragma: no branch

        # Sort - validate and add to payload
        sort_fields = []
        if sort:
            if validation == "off":
                payload["sort"] = sort
            else:
                try:
                    sort_payload, invalid_fields, value_errors = _normalize_sorts(sort)
                    if invalid_fields:
                        if validation == "strict":
                            raise ValueError(f"Invalid sort fields: {invalid_fields}")
                        self._logger.warning(
                            "Skipping invalid sort fields: %s", invalid_fields
                        )
                    if value_errors:
                        if validation == "strict":
                            raise ValueError(f"Invalid sort values: {value_errors}")
                        self._logger.warning(
                            "Skipping invalid sort values: %s", value_errors
                        )
                    if sort_payload:
                        sort_fields = cast(
                            list[TrackField], [entry["field"] for entry in sort_payload]
                        )
                        payload["sort"] = sort_payload
                except ValueError as e:
                    if validation == "strict":
                        raise
                    self._logger.warning("Skipping sort: %s", e)

        # Collect return fields, ensuring sort fields are included.
        # If fields="all", omit the fields list so the API returns all fields.
        if validation == "off":
            if fields is not None:
                payload["fields"] = fields
        else:
            fields_payload, input_str_error, invalid_fields = _normalize_fields(
                fields, extra_fields=sort_fields
            )
            if input_str_error:
                if validation == "strict":
                    raise ValueError(f"Fields: {input_str_error}")
                self._logger.warning("Using default fields: %s", input_str_error)
            if invalid_fields:
                if validation == "strict":
                    raise ValueError(f"Invalid field names: {invalid_fields}")
                self._logger.warning(
                    "Skipped returning invalid field names: %s", invalid_fields
                )

            if fields_payload is not None:
                payload["fields"] = fields_payload

        # Perform paged request. The API expects paging payloads in the GET body.
        return cast(
            list[TrackResponse] | None,
            self._paged_tracks_json(
                "/tracks", payload, limit=limit, offset=0, timeout=timeout
            ),
        )

    def search(
        self,
        filter: Mapping[FilterField, str | int | float | None],
        *,
        source: TrackSource | None = "non-archived",
        fields: Optional[Sequence[TrackField] | Literal["all", "*"]] = None,
        sort: Optional[SortInput] = None,
        limit: Optional[int] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TrackResponse] | None:
        """Search for tracks by field filters.

        Parameters
        ----------
        filter
            Mapping of track fields to values for filtering. A track has to match
            all of them. See ``FilterField`` for the fields Lexicon can filter;
            Lexicon v1.12 rejects any other field.

            - ``id``: a track ID, a list of IDs, or ``"12,48,153"``. Resolves many
              IDs in one request. Needs Lexicon v1.12; older versions ignore it, so
              the search returns None rather than the whole library.
            - ``fileType``: the file extension, such as ``"mp3"`` (v1.12).
            - ``tags``: labels separated by commas; ``None`` finds untagged tracks
              (v1.12).
        limit
            Maximum number of tracks to return. ``None`` (default) returns every
            match. Lexicon v1.12 pages search results 1000 at a time and this
            method follows the pages; older versions return at most 1000 matches.
        source
            Track source filter (e.g., "non-archived").
        fields
            Fields to include in each track dict. Same semantics as
            :meth:`list` — pass a list (``fields=["id", "location"]``) for a
            narrow projection, ``"all"``/``"*"`` for everything, ``None`` for
            ``DEFAULT_TRACK_FIELDS``. Comma-separated strings are *not*
            accepted.
        sort
            Sort fields and directions (optional; defaults to no sort).
            - API native: list of dicts with ``"field"`` and optional ``"dir"`` keys
            - Alternative: list of tuples ``(field, dir)``
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        list of dict | None
            Matching track dicts, or None on error.
        """
        payload: dict[str, object] = {}

        # Filter (search parameters) - validate and add to payload
        if validation == "off":
            payload["filter"] = filter
            filter_fields = []
            id_filter: object = None
        else:
            try:
                filter_payload, invalid_fields, value_errors = _normalize_filters(
                    filter
                )
            except ValueError as e:
                if validation == "strict":
                    raise
                self._logger.warning(f"Skipping search: {e}")
                return None
            if invalid_fields:
                if validation == "strict":
                    raise ValueError(f"Invalid filter fields: {invalid_fields}")
                self._logger.warning(
                    "Skipping invalid filter fields: %s", invalid_fields
                )
            if value_errors:
                if validation == "strict":
                    raise ValueError(f"Invalid filter values: {value_errors}")
                self._logger.warning("Skipping invalid filter values: %s", value_errors)

            # An empty filter matches the whole library, which is not what a caller
            # who passed filters asked for.
            if filter and not filter_payload:
                self._logger.warning("Skipping search: no valid filters remain.")
                return None

            filter_fields = cast(
                list[TrackField], [field for field in filter_payload.keys()]
            )
            payload["filter"] = filter_payload
            id_filter = filter_payload.get("id")

        # Source - validate and add to payload
        if source:
            if source in TRACK_SOURCES:
                payload["source"] = source
            elif validation == "off":
                payload["source"] = source
            elif validation == "strict":
                raise ValueError(f"Invalid track source: {source}")
            else:
                self._logger.warning(
                    "Ignoring invalid track source: %s", source
                )  # pragma: no branch

        # Sort - validate and add to payload
        sort_fields = []
        if sort:
            if validation == "off":
                payload["sort"] = sort
            else:
                try:
                    sort_payload, invalid_fields, value_errors = _normalize_sorts(sort)
                    if invalid_fields:
                        if validation == "strict":
                            raise ValueError(f"Invalid sort fields: {invalid_fields}")
                        self._logger.warning(
                            "Skipping invalid sort fields: %s", invalid_fields
                        )
                    if value_errors:
                        if validation == "strict":
                            raise ValueError(f"Invalid sort values: {value_errors}")
                        self._logger.warning(
                            "Skipping invalid sort values: %s", value_errors
                        )
                    if sort_payload:
                        sort_fields = cast(
                            list[TrackField], [entry["field"] for entry in sort_payload]
                        )
                        payload["sort"] = sort_payload
                except ValueError as e:
                    if validation == "strict":
                        raise
                    self._logger.warning(f"Skipping sort: {e}")

        # Collect return fields, ensuring sort fields are included.
        # If fields="all", omit the fields list so the API returns all fields.
        if validation == "off":
            if fields is not None:
                payload["fields"] = fields
        else:
            fields_payload, input_str_error, invalid_fields = _normalize_fields(
                fields, extra_fields=sort_fields + filter_fields
            )
            if input_str_error:
                if validation == "strict":
                    raise ValueError(f"Field returns: {input_str_error}")
                self._logger.warning(f"Using default field returns: {input_str_error}")
            if invalid_fields:
                if validation == "strict":
                    raise ValueError(
                        f"Invalid field names for return: {invalid_fields}"
                    )
                self._logger.warning(
                    f"Skipped returning invalid field names: {invalid_fields}"
                )

            if fields_payload is not None:
                payload["fields"] = fields_payload

        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                if validation == "strict":
                    raise ValueError(f"Invalid limit for search: {limit}")
                self._logger.warning("Ignoring invalid limit for search: %s", limit)
                limit = None
            elif limit == 0:
                return []

        # Perform request. The API expects search payloads in the GET body. The first
        # request sends no paging keys, because Lexicon v1.11 rejects "limit" and
        # "offset" here and answers with at most 1000 matches.
        response = self._request("GET", "/search/tracks", json=payload, timeout=timeout)
        page = self._search_page(response)
        if page is None:
            return None
        tracks, total = page

        # Lexicon v1.11 ignores filter.id and answers with the whole library.
        if isinstance(id_filter, str) and isinstance(total, int):
            if total > len(id_filter.split(",")):
                self._logger.warning(
                    "Lexicon ignored the id filter and matched %s tracks; filtering by "
                    "id needs Lexicon v1.12 or newer.",
                    total,
                )
                return None

        collected: builtins.list[dict] = [*tracks]
        wanted = total if isinstance(total, int) else len(collected)
        if limit is not None:
            wanted = min(wanted, limit)
        while len(collected) < wanted:
            page_payload = dict(payload)
            page_payload["offset"] = len(collected)
            page_payload["limit"] = min(PAGE_SIZE, wanted - len(collected))
            response = self._request(
                "GET", "/search/tracks", json=page_payload, timeout=timeout
            )
            page = self._search_page(response)
            if page is None or not page[0]:
                self._logger.warning(
                    "Search matched %s tracks but returned only %s; Lexicon versions "
                    "older than v1.12 cannot page search results, so refine your filter.",
                    total,
                    len(collected),
                )
                break
            collected.extend(page[0])

        if limit is not None:
            collected = collected[:limit]
        return cast(
            list[TrackResponse],
            [self._parse_enums(t) if isinstance(t, dict) else t for t in collected],
        )

    def _search_page(
        self, response: object
    ) -> tuple[builtins.list[dict], Optional[int]] | None:
        """Return the tracks and match total of one search response."""
        if not isinstance(response, dict):
            return None
        data = response.get("data")
        tracks = data.get("tracks") if isinstance(data, dict) else None
        if not isinstance(tracks, list):
            self._logger.warning(
                "Tracks search response missing expected list; Response was %s",
                response,
            )
            return None
        total = data.get("total") if isinstance(data, dict) else None
        return tracks, total if isinstance(total, int) else None

    def add(
        self,
        locations: Sequence[str],
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TrackResponse] | None:
        """Add new tracks by file location.

        Parameters
        ----------
        locations
            File paths to add to Lexicon.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        list of dict | None
            Added track dicts, or None on error.

        Notes
        -----
        Lexicon options "Auto analyze new tracks" and "Auto re-encode new MP3, MP4, and M4A files"
        will cause the track to be processed after addition. The returned track dict will be out
        of date until processing is complete. Probe the track again (check dateModified) to check for
        processing completion.
        """
        if isinstance(locations, (str, bytes)) or not isinstance(locations, Sequence):
            if validation == "strict":
                raise ValueError(f"Invalid locations payload for add: {locations}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid locations payload for add: %s", locations)
                return None

        location_list = list(locations)
        if not location_list or any(
            not isinstance(path, str) or not path for path in location_list
        ):
            if validation == "strict":
                raise ValueError(f"Invalid locations payload for add: {locations}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid locations payload for add: %s", locations)
                return None

        response = self._post(
            "/tracks", json={"locations": location_list}, timeout=timeout
        )
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        tracks = data.get("tracks") if isinstance(data, dict) else None
        if isinstance(tracks, list):
            return cast(
                list[TrackResponse],
                [self._parse_enums(t) if isinstance(t, dict) else t for t in tracks],
            )
        if isinstance(tracks, dict):
            return [cast(TrackResponse, self._parse_enums(tracks))]
        self._logger.warning("Add tracks response missing expected track list.")
        return None

    def update(
        self,
        track_id: int | Literal["selected"],
        edits: Mapping[TrackEditField, object] | TrackUpdate,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Update a track via patch.

        Parameters
        ----------
        track_id
            Track ID to update, or ``"selected"`` to give every track selected in
            Lexicon the same edits (v1.12 and newer). A relative edit then counts
            from each track's own value, and the return value is the first
            edited track. Fails with error code 113 when nothing is selected.
        edits
            Mapping of fields to update.
            - Most fields from the Track schema are accepted, but file-derived fields
              (e.g., location, bitrate) are not editable. Use
              :meth:`update_location` to point a track at another file.
            - Numeric fields can be provided as numbers or as strings prefixed with
              `+` or `-` to apply relative changes.
            - Date fields must be in `YYYY-MM-DD` format.
            - `cuepoints`, `tempomarkers`, and `tags` accept arrays; see the TrackUpdate
              schema for their required properties. A `cuepoints` or `tempomarkers`
              edit replaces the whole list. Lexicon clears the ``data`` of any cue or
              marker sent without it, so pass it back from the track to keep it.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        TrackResponse or None
            Updated track dict, or ``None`` on error.
        """
        if not _is_track_ref(track_id):
            if validation == "strict":
                raise ValueError(f"Invalid track_id for updates: {track_id}")
            self._logger.warning("Invalid track_id for update: %s", track_id)
            return None
        if not isinstance(edits, dict) or not edits:
            if validation == "strict":
                raise ValueError(f"Invalid edits payload for track {track_id}: {edits}")
            self._logger.warning(
                "Invalid edits payload for track %s: %s", track_id, edits
            )
            return None

        edits_map = cast(Mapping[TrackEditField, object], edits)
        if validation == "off":
            valid_edits = edits_map
        else:
            try:
                valid_edits, invalid_fields, value_errors = _normalize_edits(edits_map)
            except ValueError as e:
                if validation == "strict":
                    raise
                self._logger.warning(f"Invalid updates: {e}")
                return None
            if invalid_fields:
                if validation == "strict":
                    raise ValueError(f"Invalid edit fields: {invalid_fields}")
                self._logger.warning("Skipping invalid edit fields: %s", invalid_fields)
            if value_errors:
                if validation == "strict":
                    raise ValueError(f"Invalid edit values: {value_errors}")
                self._logger.warning("Skipping invalid edit values: %s", value_errors)
        if not valid_edits:
            if validation == "strict":
                raise ValueError(f"No valid track edit fields provided for {track_id}")
            self._logger.warning("No valid track edit fields provided for %s", track_id)
            return None

        payload = {"id": track_id, "edits": valid_edits}
        response = self._patch("/track", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        # Lexicon v1.12 returns the track as stored after the edit in data.track.
        # Older versions return {"id": ..., "edits": {...}}, or {} for a tag edit,
        # so re-fetch for those, falling back to the input track_id.
        data = response.get("data")
        track = data.get("track") if isinstance(data, dict) else None
        if isinstance(track, dict):
            return cast(TrackResponse, self._parse_enums(track))
        updated_id = response.get("id")
        if not isinstance(updated_id, int):
            updated_id = track_id
        return self.get(updated_id, validation="off", timeout=timeout)

    def update_location(
        self,
        track_id: int,
        location: str,
        *,
        check_file_exists: bool = True,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Point a track at a different file. Needs Lexicon v1.12 or newer.

        Only the library changes; the file is never moved or renamed.

        Parameters
        ----------
        track_id
            Track ID to relocate.
        location
            Full path to the new file. Lexicon normalizes it before saving (on
            macOS it prefixes the drive, ``/Volumes/Macintosh HD/...``), so read
            the location back from the returned track. A relative path is taken
            from the root of the drive.
        check_file_exists
            When True (default), Lexicon refuses a file that does not exist (error
            code 111). Pass False to relocate to a file that is not there, such as
            one on a drive that is not mounted.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        TrackResponse or None
            The relocated track, or ``None`` on error: the track does not exist
            (code 100), another track already has the location (110), the file
            does not exist (111), or the track is a streaming track.
        """
        if validation != "off":
            problem = None
            if not _is_track_ref(track_id) or track_id == SELECTED:
                problem = f"Invalid track_id for update_location: {track_id}"
            elif not isinstance(location, str) or not location.strip():
                problem = f"Invalid location for update_location: {location!r}"
            elif not isinstance(check_file_exists, bool):
                problem = f"Invalid check_file_exists: {check_file_exists!r}"
            if problem:
                if validation == "strict":
                    raise ValueError(problem)
                self._logger.warning(problem)
                return None

        payload: dict[str, object] = {"id": track_id, "location": location}
        if not check_file_exists:
            payload["checkFileExists"] = False
        response = self._patch("/track/location", json=payload, timeout=timeout)
        data = response.get("data") if isinstance(response, dict) else None
        track = data.get("track") if isinstance(data, dict) else None
        if isinstance(track, dict):
            return cast(TrackResponse, self._parse_enums(track))
        if response is not None:
            self._logger.warning("Update location response missing expected track.")
        return None

    def update_tempogrid(
        self,
        track_id: int,
        tempomarkers: Sequence[TempoMarkerUpdate],
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Replace a track's tempomarkers while preserving cuepoint beat positions.

        A plain ``update()`` of ``tempomarkers`` leaves cuepoints' ``startTime``
        (seconds) untouched, which silently shifts every cuepoint to a different
        beat under the new grid. This method captures each cuepoint's beat
        position under the OLD tempo grid and rewrites ``startTime`` (and
        ``endTime``, when set) so the same beat positions are preserved under
        the NEW grid.

        Parameters
        ----------
        track_id
            Track ID to update.
        tempomarkers
            New tempomarkers. Each: ``{"startTime": float, "bpm": float|int}``.
        validation
            Validation mode passed through to the underlying ``update()`` call.
        timeout
            Timeout in seconds for the underlying requests.

        Returns
        -------
        TrackResponse or None
            Updated track dict, or ``None`` on error.
        """
        new_tempomarkers = list(tempomarkers)
        current = self.get(track_id, timeout=timeout)
        if current is None:
            return None
        old_tempomarkers = current.get("tempomarkers") or []
        cuepoints = current.get("cuepoints") or []

        edits: TrackUpdate = cast(TrackUpdate, {"tempomarkers": new_tempomarkers})

        if old_tempomarkers and new_tempomarkers and cuepoints:
            updated_cuepoints: list[dict[str, object]] = []
            for cp in cuepoints:
                cp_dict = cast(dict, cp) if isinstance(cp, dict) else None
                if cp_dict is None or "startTime" not in cp_dict:
                    if cp_dict is not None:
                        updated_cuepoints.append(dict(cp_dict))
                    continue
                rewritten: dict[str, object] = dict(cp_dict)
                start_beats = seconds_to_beats(
                    float(cp_dict["startTime"]), old_tempomarkers
                )
                rewritten["startTime"] = beats_to_seconds(start_beats, new_tempomarkers)
                end_time = cp_dict.get("endTime")
                if end_time is not None:
                    end_beats = seconds_to_beats(float(end_time), old_tempomarkers)
                    rewritten["endTime"] = beats_to_seconds(end_beats, new_tempomarkers)
                updated_cuepoints.append(rewritten)
            edits["cuepoints"] = updated_cuepoints  # type: ignore[typeddict-item]

        return self.update(track_id, edits, validation=validation, timeout=timeout)

    def add_tags(
        self,
        track_id: int,
        tag_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Add tags to a track without removing existing ones.

        Parameters
        ----------
        track_id
            Track identifier.
        tag_ids
            Tag ID or list of tag IDs to add.
        validation
            Validation mode.
        timeout
            Request timeout in seconds.

        Returns
        -------
        TrackResponse or None
            Updated track dict, or None on error.
        """
        track = self.get(track_id, validation=validation, timeout=timeout)
        if track is None:
            return None
        current = track.get("tags", [])
        new_ids = [tag_ids] if isinstance(tag_ids, int) else list(tag_ids)
        merged = list(dict.fromkeys(current + new_ids))  # dedupe, preserve order
        return self.update(
            track_id, edits={"tags": merged}, validation=validation, timeout=timeout
        )

    def remove_tags(
        self,
        track_id: int,
        tag_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Remove tags from a track without affecting other tags.

        Parameters
        ----------
        track_id
            Track identifier.
        tag_ids
            Tag ID or list of tag IDs to remove.
        validation
            Validation mode.
        timeout
            Request timeout in seconds.

        Returns
        -------
        TrackResponse or None
            Updated track dict, or None on error.
        """
        track = self.get(track_id, validation=validation, timeout=timeout)
        if track is None:
            return None
        current = track.get("tags", [])
        to_remove = {tag_ids} if isinstance(tag_ids, int) else set(tag_ids)
        remaining = [t for t in current if t not in to_remove]
        return self.update(
            track_id, edits={"tags": remaining}, validation=validation, timeout=timeout
        )

    def delete(
        self,
        track_ids: Sequence[int] | int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Delete one or more tracks by ID.

        Parameters
        ----------
        track_ids
            Track ID or sequence of track IDs to delete.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        bool
            True if the delete succeeded, otherwise False.
        """
        if validation == "off":
            # Pass through directly to API without any shape validation
            payload = {"ids": track_ids}
        else:
            # Normalize and validate
            ids = _normalize_id_sequence(track_ids)
            if ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid track_ids for delete: {track_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid track_ids for delete: %s", track_ids)
                    return False

            payload = {"ids": ids}

        response = self._delete("/tracks", json=payload, timeout=timeout)
        return response is not None

    def analyze(
        self,
        track_ids: Sequence[int] | int,
        *,
        analyze_key: Optional[bool] = None,
        analyze_beatgrid: Optional[bool] = None,
        analyze_waveform: Optional[bool] = None,
        analyze_energy: Optional[bool] = None,
        do_not_overwrite: Optional[bool] = None,
        tempo_range: Optional[TempoRange | tuple[int, int]] = None,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> bool:
        """Start Lexicon's audio analyzer on one or more tracks.

        Parameters
        ----------
        track_ids
            Track ID or sequence of track IDs to analyze.
        analyze_key
            Analyze musical key. ``None`` uses Lexicon's own analysis setting.
        analyze_beatgrid
            Analyze tempo and beatgrid. ``None`` uses Lexicon's own analysis setting.
        analyze_waveform
            Analyze the waveform. ``None`` uses Lexicon's own analysis setting.
        analyze_energy
            Analyze energy. ``None`` uses Lexicon's own analysis setting.
        do_not_overwrite
            Keep existing analysis values instead of replacing them. ``None``
            uses Lexicon's own analysis setting.
        tempo_range
            Tempo range for beatgrid detection. One of Lexicon's dropdown
            presets ``"0_300"`` (Any), ``"58_115"``, ``"68_135"``,
            ``"78_155"``, ``"88_175"``, ``"98_195"``, ``"128_255"``,
            ``"180_300"`` (180+), or the matching ``(min, max)`` tuple of
            integers.
        validation
            Validation mode: ``"off"`` sends inputs as-is, ``"warn"`` drops invalid
            inputs with warnings, and ``"strict"`` raises on invalid inputs.
            In ``"off"`` mode, inputs must match the API-native shapes.
        timeout
            Timeout in seconds for this request.

        Returns
        -------
        bool
            True if Lexicon accepted the request, otherwise False.

        Notes
        -----
        Analysis runs in the background. The call returns as soon as Lexicon
        accepts the request, not when analysis finishes. The response carries no
        job id and the API has no completion signal, so poll ``tracks.get()``
        and watch ``tempomarkers``, ``bpm``, ``key``, or ``dateModified`` to see
        when a track has been processed.

        ``tempo_range`` is written to Lexicon's stored analysis tempo-range
        setting and stays changed after the call. The five boolean options apply
        to this run only.

        ``tempo_range`` must be one of the dropdown presets in ``"warn"`` and
        ``"strict"`` modes; ``"off"`` passes any string through. Lexicon's
        control handler accepts any ``"<min>_<max>"`` string and the analyzer
        clamps the stored bounds to 50..300 when it runs, but the dropdown shows
        no label for a value that is not a preset.
        """
        parameters: dict[str, object]
        if validation == "off":
            # Pass through directly to API without any shape validation
            parameters = {"trackIds": track_ids}
        else:
            # Normalize and validate
            ids = _normalize_id_sequence(track_ids)
            if ids is None:
                if validation == "strict":
                    raise ValueError(f"Invalid track_ids for analyze: {track_ids}")
                if validation == "warn":  # pragma: no branch - strict raises above
                    self._logger.warning("Invalid track_ids for analyze: %s", track_ids)
                    return False

            parameters = {"trackIds": ids}

        # A key left out of the payload makes Lexicon use its own setting for that option.
        options: tuple[tuple[str, Optional[bool]], ...] = (
            ("analyzeKey", analyze_key),
            ("analyzeBeatgrid", analyze_beatgrid),
            ("analyzeWaveform", analyze_waveform),
            ("analyzeEnergy", analyze_energy),
            ("doNotOverwrite", do_not_overwrite),
        )
        for name, value in options:
            if value is None:
                continue
            # bool is a subclass of int, so isinstance is the only check that rejects 1 and 0.
            if validation != "off" and not isinstance(value, bool):
                if validation == "strict":
                    raise ValueError(f"Invalid {name} for analyze: {value}")
                self._logger.warning("Skipping invalid %s for analyze: %s", name, value)
                continue
            parameters[name] = value

        if tempo_range is not None:
            if validation == "off":
                parameters["tempoRange"] = tempo_range
            else:
                normalized_range = _normalize_tempo_range(tempo_range)
                if normalized_range is None:
                    if validation == "strict":
                        raise ValueError(
                            f"Invalid tempo_range for analyze: {tempo_range}"
                        )
                    self._logger.warning(
                        "Skipping invalid tempo_range for analyze: %s", tempo_range
                    )
                else:
                    parameters["tempoRange"] = normalized_range

        response = self._post(
            "/control",
            json={"action": ANALYZE_ACTION, "parameters": parameters},
            timeout=timeout,
        )
        return response is not None

    def _paged_tracks_json(
        self,
        path: str,
        base_payload: dict[str, object],
        *,
        limit: Optional[int],
        offset: int,
        timeout: Optional[int],
    ) -> list[dict] | None:
        collected: list[dict] = []
        next_offset = max(int(offset), 0)
        if limit is not None:
            remaining = max(int(limit), 0)
            if remaining == 0:
                return collected
        else:
            remaining = None

        while True:
            page_limit = 1000 if remaining is None else min(remaining, 1000)
            payload = dict(base_payload)
            payload["limit"] = page_limit
            payload["offset"] = next_offset

            response = self._request("GET", path, json=payload, timeout=timeout)
            if not isinstance(response, dict):
                return None

            data = response.get("data") if isinstance(response, dict) else None
            tracks = data.get("tracks") if isinstance(data, dict) else None
            if not isinstance(tracks, list):
                self._logger.warning(
                    "Tracks response missing expected list; Response was %s", response
                )
                return None

            collected.extend(
                self._parse_enums(t) if isinstance(t, dict) else t for t in tracks
            )

            if remaining is not None:
                remaining -= len(tracks)
                if remaining <= 0:
                    break

            total = data.get("total") if isinstance(data, dict) else None
            page_size = data.get("limit") if isinstance(data, dict) else None
            if isinstance(total, int) and isinstance(page_size, int):
                if next_offset + page_size >= total:
                    break
                next_offset += page_size
                continue

            if len(tracks) < page_limit:
                break
            next_offset += page_limit

        return collected
