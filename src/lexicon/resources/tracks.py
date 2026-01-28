"""Track resource wrapper."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Literal, Mapping, cast

from .base import Resource
from .tracks_types import (
    TRACK_SOURCES,
    FilterField,
    SortInput,
    TrackEditField,
    TrackField,
    TrackSource,
    TrackResponse,
    TrackUpdate,
    _normalize_edits,
    _normalize_fields,
    _normalize_filters,
    _normalize_sorts,
)
from ._common_types import ValidationMode, _normalize_id_sequence


class Tracks(Resource):
    """Track resource operations."""

    def get(
        self,
        track_id: int,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Fetch a single track by ID.

        Parameters
        ----------
        track_id
            Track ID to fetch.
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
        if not isinstance(track_id, int) or track_id < 1:
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
            return cast(TrackResponse, track)
        self._logger.warning("Track %s not found in response", track_id)
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
                    self._logger.warning("Invalid track_ids for get_many: %s", track_ids)
                    return None

        # Always fetch IDs to estimate library size for the 5% cutoff.
        all_ids = self.list(fields=["id"], timeout=timeout)
        if not all_ids:
            return [self.get(track_id, timeout=timeout) if track_id in ids else None for track_id in ids]

        # Large requests are considered to be > 5% of total library size
        cutoff = len(all_ids) * 0.05
        
        # Get all tracks and trim by id for large requests
        if len(ids) >= cutoff:
            all_tracks = self.list(fields="all", timeout=timeout) or []
            by_id = {track.get("id"): track for track in all_tracks if isinstance(track, dict)}
            return [
                by_id.get(cast(int, track_id)) if isinstance(track_id, int) and track_id in ids else None
                for track_id in ids
            ]
        
        # Get tracks one-by-one for small requests
        return [self.get(cast(int, track_id), timeout=timeout) if isinstance(track_id, int) and track_id in ids else None for track_id in ids]

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
            - Use ``"all"`` or ``"*"`` to request all fields from the API.
            - None returns DEFAULT_TRACK_FIELDS
            - With validation ``"off"``, list is required and None returns all fields
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
                self._logger.warning("Ignoring invalid track source: %s", source)  # pragma: no branch

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
                        self._logger.warning("Skipping invalid sort fields: %s", invalid_fields)
                    if value_errors:
                        if validation == "strict":
                            raise ValueError(f"Invalid sort values: {value_errors}")
                        self._logger.warning("Skipping invalid sort values: %s", value_errors)
                    if sort_payload:
                        sort_fields = cast(list[TrackField], [entry["field"] for entry in sort_payload])
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
            fields_payload, input_str_error, invalid_fields = _normalize_fields(fields, extra_fields=sort_fields)
            if input_str_error:
                if validation == "strict":
                    raise ValueError(f"Fields: {input_str_error}")    
                self._logger.warning("Using default fields: %s", input_str_error)
            if invalid_fields:
                if validation == "strict":
                    raise ValueError(f"Invalid field names: {invalid_fields}")
                self._logger.warning("Skipped returning invalid field names: %s", invalid_fields)

            if fields_payload is not None:
                payload["fields"] = fields_payload

        # Perform paged request. The API expects paging payloads in the GET body.
        return cast(
            list[TrackResponse] | None,
            self._paged_tracks_json("/tracks", payload, limit=limit, offset=0, timeout=timeout),
        )

    def search(
        self,
        filter: Mapping[FilterField, str | int | float | None],
        *,
        source: TrackSource | None = "non-archived",
        fields: Optional[Sequence[TrackField] | Literal["all", "*"]] = None,
        sort: SortInput,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> list[TrackResponse] | None:
        """Search for tracks by field filters.

        Parameters
        ----------
        filter
            Mapping of track fields to values for filtering.
        source
            Track source filter (e.g., "non-archived").
        fields
            Fields to include in each track dict. 
            - Use ``"all"`` or ``"*"`` to request all fields from the API.
            - None returns DEFAULT_TRACK_FIELDS
            - With validation ``"off"``, list is required and None returns all fields
        sort
            Sort fields and directions
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
        else:
            try:
                filter_payload, invalid_fields, value_errors = _normalize_filters(filter)
            except ValueError as e:
                if validation == "strict":
                    raise
                self._logger.warning(f"Skipping search: {e}")
                return None
            if invalid_fields:
                if validation == "strict":
                    raise ValueError(f"Invalid filter fields: {invalid_fields}")
                self._logger.warning("Skipping invalid filter fields: %s", invalid_fields)
            if value_errors:
                if validation == "strict":
                    raise ValueError(f"Invalid filter values: {value_errors}")
                self._logger.warning("Skipping invalid filter values: %s", value_errors)

            filter_fields = cast(list[TrackField], [field for field in filter_payload.keys()])
            payload["filter"] = filter_payload

        # Source - validate and add to payload
        if source:
            if source in TRACK_SOURCES:
                payload["source"] = source
            elif validation == "off":
                payload["source"] = source
            elif validation == "strict":
                raise ValueError(f"Invalid track source: {source}")
            else:
                self._logger.warning("Ignoring invalid track source: %s", source)  # pragma: no branch

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
                        self._logger.warning("Skipping invalid sort fields: %s", invalid_fields)
                    if value_errors:
                        if validation == "strict":
                            raise ValueError(f"Invalid sort values: {value_errors}")
                        self._logger.warning("Skipping invalid sort values: %s", value_errors)
                    if sort_payload:
                        sort_fields = cast(list[TrackField], [entry["field"] for entry in sort_payload])
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
            fields_payload, input_str_error, invalid_fields = _normalize_fields(fields, extra_fields=sort_fields + filter_fields)
            if input_str_error:
                if validation == "strict":
                    raise ValueError(f"Field returns: {input_str_error}")    
                self._logger.warning(f"Using default field returns: {input_str_error}")
            if invalid_fields:
                if validation == "strict":
                    raise ValueError(f"Invalid field names for return: {invalid_fields}")
                self._logger.warning(f"Skipped returning invalid field names: {invalid_fields}")

            if fields_payload is not None:
                payload["fields"] = fields_payload

        # Perform request. The API expects search payloads in the GET body.
        response = self._request("GET", "/search/tracks", json=payload, timeout=timeout)
        if not isinstance(response, dict):
            return None

        # Extract tracks from response
        data = response.get("data") if isinstance(response, dict) else None
        tracks = data.get("tracks") if isinstance(data, dict) else None
        if isinstance(tracks, list):
            total = data.get("total") if isinstance(data, dict) else None
            if isinstance(total, int) and total > len(tracks):
                self._logger.warning(
                    "Search matched %s total tracks but is limited to returning %s; refine your filter.",
                    total,
                    len(tracks),
                )
            return cast(list[TrackResponse], tracks)
        self._logger.warning("Tracks search response missing expected list; Response was %s", response)
        return None

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
        if not location_list or any(not isinstance(path, str) or not path for path in location_list):
            if validation == "strict":
                raise ValueError(f"Invalid locations payload for add: {locations}")
            if validation == "warn":  # pragma: no branch - strict raises above
                self._logger.warning("Invalid locations payload for add: %s", locations)
                return None

        response = self._post("/tracks", json={"locations": location_list}, timeout=timeout)
        if not isinstance(response, dict):
            return None

        data = response.get("data") if isinstance(response, dict) else None
        tracks = data.get("tracks") if isinstance(data, dict) else None
        if isinstance(tracks, list):
            return cast(list[TrackResponse], tracks)
        if isinstance(tracks, dict):
            return [cast(TrackResponse, tracks)]
        self._logger.warning("Add tracks response missing expected track list.")
        return None

    def update(
        self,
        track_id: int,
        edits: Mapping[TrackEditField, object] | TrackUpdate,
        *,
        validation: ValidationMode = "warn",
        timeout: Optional[int] = None,
    ) -> TrackResponse | None:
        """Update a track via patch.

        Parameters
        ----------
        track_id
            Track ID to update.
        edits
            Mapping of fields to update.
            - Most fields from the Track schema are accepted, but file-derived fields
              (e.g., location, bitrate) are not editable.
            - Numeric fields can be provided as numbers or as strings prefixed with
              `+` or `-` to apply relative changes.
            - Date fields must be in `YYYY-MM-DD` format.
            - `cuepoints`, `tempomarkers`, and `tags` accept arrays; see the TrackUpdate
              schema for their required properties.
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
        if not isinstance(track_id, int) or track_id < 1:
            if validation == "strict":
                raise ValueError(f"Invalid track_id for updates: {track_id}")
            self._logger.warning("Invalid track_id for update: %s", track_id)
            return None
        if not isinstance(edits, dict) or not edits:
            if validation == "strict":
                raise ValueError(f"Invalid edits payload for track {track_id}: {edits}")
            self._logger.warning("Invalid edits payload for track %s: %s", track_id, edits)
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

        data = response.get("data") if isinstance(response, dict) else None
        track = data.get("track") if isinstance(data, dict) else None
        if isinstance(track, dict):
            return cast(TrackResponse, track)

        self._logger.warning("Update track response missing expected track data.")
        return None

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
                self._logger.warning("Tracks response missing expected list; Response was %s", response)
                return None

            collected.extend(tracks)

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
