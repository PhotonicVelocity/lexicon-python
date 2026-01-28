'''Types, structures, and validation for tracks'''

from typing import Literal, Mapping, ReadOnly, Required, TypedDict, Optional, Sequence, get_args, cast
from datetime import date, datetime
from dataclasses import dataclass, field
import re

from ._common_types import Color, _normalize_color

__all__ = [
    "TrackField",
    "TrackUpdate",
    "DEFAULT_TRACK_FIELDS",
    "TrackEditField",
    "CuePointResponse",
    "CuePointType",
    "CuePointUpdate",
    "TempoMarkerResponse",
    "TempoMarkerUpdate",
    "FilterField",
    "SortField",
]

#region --- FIELD TYPES AND VALIDATION ---

# Track source filters for list and search endpoints
TrackSource = Literal["non-archived", "all", "archived", "incoming"]
TRACK_SOURCES: tuple[TrackSource, ...] = get_args(TrackSource)


#region --- AVAILABLE FIELDS ---

# All fields
TrackField = Literal[
    "id", "type", "title", "artist", "albumTitle", "label", "remixer", "mix", "composer", "producer",
    "grouping", "lyricist", "comment", "key", "genre", "bpm", "rating", "color", "year", "duration",
    "bitrate", "playCount", "location", "lastPlayed", "dateAdded", "dateModified", "sizeBytes", "sampleRate",
    "trackNumber", "energy", "danceability", "popularity", "happiness", "extra1", "extra2",
    "tags", "importSource", "locationUnique", "tempomarkers", "cuepoints", "incoming", "archived",
    "archivedSince", "beatshiftCase", "fingerprint", "streamingService", "streamingId",
]
TRACK_FIELDS: tuple[TrackField, ...] = get_args(TrackField)

# Default return fields for track list and search endpoints
DEFAULT_TRACK_FIELDS: tuple[TrackField, ...] = (
    "id", "artist", "title", "albumTitle", "bpm", "key", "duration", "year"
)

def _normalize_fields(
    fields: Optional[Sequence[TrackField] | Literal["all", "*"]],
    *,
    extra_fields: Optional[Sequence[TrackField]] = None,
) -> tuple[list[TrackField] | None, Optional[str], Optional[list[str]]]:
    """Normalize field selection and return errors."""
    input_str_error: str | None = None
    if isinstance(fields, str):
        if fields.lower() in {"all", "*"}:
            return (None, None, None)
        input_str_error = f"String input must be 'all' or '*': {fields}"
        field_list = list(DEFAULT_TRACK_FIELDS)
    elif fields is None:
        field_list = list(DEFAULT_TRACK_FIELDS)
    else:
        field_list = list(fields)

    if extra_fields:
        for field in extra_fields:
            if field not in field_list:
                field_list.append(field)

    valid_fields: list[TrackField] = []
    invalid_fields: list[str] | None = []
    for field in field_list:
        if field in TRACK_FIELDS:
            valid_fields.append(field)
        else:
            invalid_fields.append(field)

    invalid_fields = invalid_fields if invalid_fields else None

    return valid_fields, input_str_error, invalid_fields

# Fields that can be filtered on by the search API endpoint
FilterField = Literal[
    "title", "artist", "albumTitle", "label", "remixer", "mix", "composer", "producer",
    "grouping", "lyricist", "comment", "key", "genre", "color", "location", "importSource",
    "extra1", "extra2", "bpm", "rating", "year", "duration", "bitrate", "playCount", 
    "sampleRate", "trackNumber", "energy", "danceability", "popularity", "happiness",
    "lastPlayed", "dateAdded", "dateModified", "tags",
]
FILTER_FIELDS: tuple[FilterField, ...] = get_args(FilterField)


def _normalize_filters(
    filters: Mapping[FilterField, object],
) -> tuple[dict[FilterField, object], list[str] | None, list[str] | None]:
    """Normalize filter values and return errors."""
    if not isinstance(filters, Mapping):
        raise ValueError(f"Filter input must be a dict: {type(filters)}")

    filter_payload: dict[FilterField, object] = {}
    invalid_fields: list[str] | None= []
    value_errors: list[str] | None = []
    for field, value in filters.items():
        if field not in FILTER_FIELDS:
            invalid_fields.append(str(field))
            continue
        try:
            if field in BOOL_FIELDS:
                value = _normalize_bool(value, context="filter")  # pragma: no cover
            if field in TEXT_FIELDS:
                value = _normalize_text(value, context="filter")
            if field in NUMBER_FIELDS:
                value = _normalize_number(value, context="filter")
            if field in DATE_FIELDS:
                value = _normalize_date(value, context="filter")
            if field == "tags":
                value = _normalize_tag_filter(value)
            filter_payload[field] = value
        except ValueError as exc:
            value_errors.append(f"{field}: {exc}")

    invalid_fields = invalid_fields if invalid_fields else None
    value_errors = value_errors if value_errors else None
    return filter_payload, invalid_fields, value_errors

# Fields that can be edited
TrackEditField = Literal[
    "title", "artist", "albumTitle", "label", "remixer", "mix", "composer", "producer",
    "grouping", "lyricist", "comment", "key", "genre", "rating", "color", "year",
    "playCount", "trackNumber", "energy", "danceability", "popularity", "happiness",
    "extra1", "extra2", "tags", "tempomarkers", "cuepoints", "incoming", "archived",
]
TRACK_EDIT_FIELDS: tuple[TrackEditField, ...] = get_args(TrackEditField)


def _normalize_edits(
    edits: Mapping[TrackEditField, object],
) -> tuple[dict[TrackEditField, object], list[str] | None, list[str] | None]:
    """Normalize edit values and return errors."""
    if not isinstance(edits, Mapping):
        raise ValueError(f"Edits input must be a dict: {type(edits)}")
    
    edits_payload: dict[TrackEditField, object] = {}
    invalid_fields: list[str] | None = []
    value_errors: list[str] | None = []
    for field, value in edits.items():
        if field not in TRACK_EDIT_FIELDS:
            invalid_fields.append(str(field))
            continue
        try:
            if field in BOOL_FIELDS:
                value = _normalize_bool(value, context="edit")
            if field in TEXT_FIELDS:
                value = _normalize_text(value, context="edit")
            if field in NUMBER_FIELDS:
                value = _normalize_number(value, context="edit")
            if field in DATE_FIELDS:
                value = _normalize_date(value, context="edit")  # pragma: no cover
            if field == "tags":
                value = _normalize_tags(value)
            if field == "cuepoints":
                value, cue_errors = _normalize_cuepoints(value)
                if cue_errors.fatal:
                    value_errors.extend([f"cuepoints: {err}" for err in cue_errors.fatal])
                if cue_errors.dropped:
                    value_errors.extend([f"cuepoints: {err}" for err in cue_errors.dropped])
                if cue_errors.partial:
                    value_errors.extend([f"cuepoints: {err}" for err in cue_errors.partial])
            if field == "tempomarkers":
                value, tempo_errors = _normalize_tempomarkers(value)
                if tempo_errors.fatal:
                    value_errors.extend([f"tempomarkers: {err}" for err in tempo_errors.fatal])
                if tempo_errors.dropped:
                    value_errors.extend([f"tempomarkers: {err}" for err in tempo_errors.dropped])
            edits_payload[field] = value
        except ValueError as exc:
            value_errors.append(f"{field}: {exc}")

    invalid_fields = invalid_fields if invalid_fields else None
    value_errors = value_errors if value_errors else None
    return edits_payload, invalid_fields, value_errors

# Fields that can be sorted in list/search API endpoints
SortFieldDisallowed: tuple[TrackField, ...] = ("cuepoints", "tempomarkers", "tags")
SortField = Literal[
    "id", "type", "title", "artist", "albumTitle", "label", "remixer", "mix", "composer", "producer",
    "grouping", "lyricist", "comment", "key", "genre", "bpm", "rating", "color", "year", "duration",
    "bitrate", "playCount", "location", "lastPlayed", "dateAdded", "dateModified", "sizeBytes", "sampleRate", 
    "trackNumber", "energy", "danceability", "popularity", "happiness", "extra1", "extra2", "importSource", 
    "locationUnique", "incoming", "archived","archivedSince", "beatshiftCase", "fingerprint", 
    "streamingService", "streamingId",
]
SORT_FIELDS: tuple[SortField, ...] = get_args(SortField)
SortDirection = Literal["asc", "desc"]
SORT_DIRECTIONS: tuple[SortDirection, ...] = get_args(SortDirection)
SortDirectionInput = SortDirection | None
SortInput = Sequence[tuple[SortField, SortDirectionInput]] | Sequence[dict[str, str]]


def _normalize_sorts(
    sort: SortInput,
) -> tuple[list[dict[str, str]], list[str] | None, list[str] | None]:
    """Normalize sort values and return errors."""
    if not isinstance(sort, Sequence):
        raise ValueError(f"Sort input must be a list: {type(sort)}")
    if isinstance(sort, (str, bytes)):
        raise ValueError("Sort must be a list/tuple, not a string")
        
    sort_payload: list[dict[str, str]] = []
    invalid_fields: list[str] | None= []
    value_errors: list[str] | None = []
    for item in sort:
        if isinstance(item, dict):
            keys = item.keys()
            if "field" not in keys:
                value_errors.append(f"Invalid keys: {keys}")
                continue
            item = (item["field"], item.get("dir"))

        if isinstance(item, tuple):
            field, direction = item
            if field not in SORT_FIELDS:
                invalid_fields.append(str(field))
                continue
            if direction:
                if direction not in SORT_DIRECTIONS:
                    value_errors.append(f"Invalid sort direction for {field}: {direction}")
                    direction = None
            entry: dict[str, str] = {"field": field}
            if direction:
                entry["dir"] = direction
            sort_payload.append(entry)

    invalid_fields = invalid_fields if invalid_fields else None
    value_errors = value_errors if value_errors else None
    return sort_payload, invalid_fields, value_errors

# Field Types
BoolField = Literal["archived", "incoming"]
BOOL_FIELDS: tuple[BoolField, ...] = get_args(BoolField)

def _normalize_bool(
    value: object,
    *,
    context: Literal["filter", "edit"],
) -> int:
    """Normalize bool-like values to int."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        if value in (0, 1):
            return int(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes"}:
            return 1
        if normalized in {"0", "false", "no"}:
            return 0
    raise ValueError(f"Input must be bool-like. Given [{value!r}]")


TextField = Literal[
    "title", "artist", "albumTitle", "label", "remixer", "mix", "composer", "producer",
    "grouping", "lyricist", "comment", "key", "genre", "color", "location", "importSource",
    "extra1", "extra2", "fingerprint", "locationUnique", "streamingId", 
]
TEXT_FIELDS: tuple[TextField, ...] = get_args(TextField)

def _normalize_text(
    value: object,
    *,
    context: Literal["filter", "edit"],
) -> str | None:
    """Normalize text values."""
    if value is None and context == "filter":
        return "NONE"
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"Input must be [str | None]. Given [{type(value)}]")


NumberField = Literal[
    "bpm", "rating", "year", "duration", "bitrate", "playCount", "sampleRate", "id",
    "trackNumber", "energy", "danceability", "popularity", "happiness", "beatshiftCase",
    "sizeBytes", "streamingService", "type"
]
NUMBER_FIELDS: tuple[NumberField, ...] = get_args(NumberField)

def _normalize_number(
    value: object,
    *,
    context: Literal["filter", "edit"],
) -> str | int | float | None:
    """Normalize numeric values."""
    if value is None:
        return "0" if context == "filter" else None
    if isinstance(value, (int, float)):
        if value > 0:
            return value
        raise ValueError(f"Numbers must be positive. Given: {value!r}")
    if isinstance(value, str):
        if context == "filter":
            none_match = re.match(r"^\s*none\s*$", value, flags=re.IGNORECASE)
            range_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$", value)
            compare_match = re.match(r"^\s*(?:[<>!]|<=|>=)?\s*\d+(?:\.\d+)?\s*$", value)
            if not any([none_match, range_match, compare_match]):
                raise ValueError(
                    "String input does not match range, inequality, or exclusion patterns. "
                    f"Given [{value!r}]"
                )
            if none_match:
                value = "0"
            if range_match:
                value = f"{range_match.group(1)}-{range_match.group(2)}"
            return value
        elif context == "edit":
            if re.match(r"^\s*[+-]?\d+(?:\.\d+)?\s*$", value):
                return value.strip()
            raise ValueError(f"Input must be numeric or +/- delta string. Given [{value!r}]")
        raise ValueError(f"Invalid context [{context}]")
    raise ValueError(f"Input must be numerical [str | int | float]. Given [{type(value)}]")


DateField = Literal["lastPlayed", "dateAdded", "dateModified", "archivedSince"]
DATE_FIELDS: tuple[DateField, ...] = get_args(DateField)

def _normalize_date(
    value: object,
    *,
    context: Literal["filter", "edit"],
) -> str | None:
    """Normalize date values."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return "NONE" if context == "filter" else None
    if isinstance(value, str):
        if value.lower().strip() == "none":
            return "NONE" if context == "filter" else None
        if context == "filter":
            date_match = re.match(r"^(?P<op>[<>]=?)?\s*(\d{4}-\d{2}-\d{2})", value)
            if not date_match:
                raise ValueError(f"Input must be in YYYY-MM-DD format. Given [{value!r}]")
            if date_match.group("op"):
                raise ValueError("Comparison operators on date filters are not supported by the API")
            date_iso = cast(str, date_match.group(2))
            return date_iso
        elif context == "edit":
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
            if not date_match:
                raise ValueError(f"Input must be YYYY-MM-DD. Given [{value!r}]")
            date_iso = cast(str, date_match.group(1))
            return date_iso
        raise ValueError(f"Invalid context [{context}]")
    raise ValueError(f"Input must be a date. Given [{type(value)}]")

TagField = Literal["tags"]
TAG_FIELDS: tuple[TagField, ...] = get_args(TagField)

def _normalize_tag_filter(
    value: object,
) -> str:
    """Normalize tag filter string."""
    if value is None:
        raise ValueError("API does not support filtering on absence of tags")
    if not isinstance(value, str):
        raise ValueError(f"Input must be [str]. Given [{type(value)}]")
    tag_match = re.match(r"^\s*~?\s*!?[^,]+(?:\s*,\s*!?[^,]+)*\s*$", value)
    if not tag_match:
        raise ValueError(f"Tag filter string is invalid. Given [{value!r}]")
    return value

def _normalize_tags(
    value: object,
) -> list[int]:
    """Normalize tag ID list."""
    if isinstance(value, list):
        tag_ids = {tag_id for tag_id in value if isinstance(tag_id, int) and tag_id >= 1}
        if tag_ids:
            return list(tag_ids)
        raise ValueError("Tag list must contain positive ints")
    raise ValueError(f"Input must be list[int]. Given [{type(value)}]")


# Response shape for track resource responses
class CuePointResponse(TypedDict, total=False):
    """Readonly cuepoint dict returned in track responses."""
    id: ReadOnly[int]
    name: ReadOnly[str]
    type: Required["CuePointTypeCode"]
    startTime: Required[float]
    endTime: ReadOnly[float | None]
    activeLoop: ReadOnly[bool]
    position: Required[int]
    color: ReadOnly[Color]

class TempoMarkerResponse(TypedDict, total=False):
    """Readonly tempo marker dict returned in track responses."""
    id: ReadOnly[int]
    trackId: ReadOnly[int]
    startTime: ReadOnly[float]
    bpm: ReadOnly[float]
    data: ReadOnly[dict]

class TrackResponse(TypedDict, total=False):
    """Readonly track dict returned by track endpoints."""
    id: ReadOnly[int]
    type: ReadOnly[int | str]
    title: ReadOnly[str]
    artist: ReadOnly[str]
    albumTitle: ReadOnly[str]
    label: ReadOnly[str]
    remixer: ReadOnly[str]
    mix: ReadOnly[str]
    composer: ReadOnly[str]
    producer: ReadOnly[str]
    grouping: ReadOnly[str]
    lyricist: ReadOnly[str]
    comment: ReadOnly[str]
    key: ReadOnly[str]
    genre: ReadOnly[str]
    bpm: ReadOnly[float]
    rating: ReadOnly[int]
    color: ReadOnly[Color]
    year: ReadOnly[int]
    duration: ReadOnly[float]
    bitrate: ReadOnly[int]
    playCount: ReadOnly[int]
    location: ReadOnly[str]
    lastPlayed: ReadOnly[str]
    dateAdded: ReadOnly[str]
    dateModified: ReadOnly[str]
    sizeBytes: ReadOnly[int]
    sampleRate: ReadOnly[int]
#    fileType: ReadOnly[str] - not currently returned by API
    trackNumber: ReadOnly[int]
    energy: ReadOnly[float]
    danceability: ReadOnly[float]
    popularity: ReadOnly[float]
    happiness: ReadOnly[float]
    extra1: ReadOnly[str]
    extra2: ReadOnly[str]
    tags: ReadOnly[list[int]]
    importSource: ReadOnly[str]
    locationUnique: ReadOnly[str]
    tempomarkers: ReadOnly[list[TempoMarkerResponse]]
    cuepoints: ReadOnly[list[CuePointResponse]]
    incoming: ReadOnly[bool]
    archived: ReadOnly[bool]
    archivedSince: ReadOnly[str]
    beatshiftCase: ReadOnly[int]
    fingerprint: ReadOnly[str]
    streamingService: ReadOnly[str]
    streamingId: ReadOnly[str]

# Payload shape for updating track resources
class CuePointUpdate(TypedDict, total=False):
    """Editable cuepoint dict used when updating tracks."""
    position: Required[int]
    startTime: Required[float]
    type: Required["CuePointType"]
    name: str
    activeLoop: int
    endTime: float
    color: Color | None

# Cuepoint type helpers
CuePointTypeInt = Literal[1, 2, 3, 4, 5]
CuePointTypeCode = Literal["1", "2", "3", "4", "5"]
CuePointTypeName = Literal["normal", "fade-in", "fade-out", "load", "loop"]
CuePointType = CuePointTypeCode | CuePointTypeInt | CuePointTypeName
CUEPOINT_TYPE_CODES: tuple[CuePointTypeCode, ...] = get_args(CuePointTypeCode)
CUEPOINT_TYPE_NAMES: tuple[CuePointTypeName, ...] = get_args(CuePointTypeName)

def _normalize_cuepoint_type(cuepoint_type: CuePointType) -> CuePointTypeCode:
    """Normalize cuepoint type to numeric code."""
    if isinstance(cuepoint_type, int):
        if cuepoint_type in (1, 2, 3, 4, 5):
            return CUEPOINT_TYPE_CODES[cuepoint_type - 1]
        raise ValueError(f"Invalid cuepoint type: {cuepoint_type}")
    if cuepoint_type in CUEPOINT_TYPE_CODES:
        return cuepoint_type
    if cuepoint_type in CUEPOINT_TYPE_NAMES:
        return CUEPOINT_TYPE_CODES[CUEPOINT_TYPE_NAMES.index(cuepoint_type)]
    raise ValueError(f"Invalid cuepoint type: {cuepoint_type}")

@dataclass
class CuepointErrors:
    """Structured cuepoint validation errors."""
    fatal: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)

def _normalize_cuepoints(
    cuepoints: object,
) -> tuple[list[CuePointUpdate], CuepointErrors]:
    """Normalize cuepoints and return errors."""
    normalized_cuepoints: list[CuePointUpdate] = []
    errors = CuepointErrors()
    if not isinstance(cuepoints, list):
        errors.fatal.append(f"Cuepoints must be a list. Given: [{type(cuepoints)}]")
        return normalized_cuepoints, errors
    
    for cuepoint in cuepoints:
        if not isinstance(cuepoint, dict):
            errors.dropped.append(f"Invalid cuepoint entry: {cuepoint}")
            continue
        cuepoint_payload = cast(CuePointUpdate, {})
        missing_required = set(("position", "startTime", "type")) - cuepoint.keys()
        if missing_required:
            errors.dropped.append(f"Missing required keys: {missing_required}")
            continue
        
        position = cuepoint["position"]
        if not isinstance(position, int):
            errors.dropped.append(f"Positions must be int: {type(position)}")
            continue
        cuepoint_payload["position"] = position
        
        startTime = cuepoint["startTime"]
        if not isinstance(startTime, float):
            errors.dropped.append(f"startTime must be float: {type(startTime)}")
            continue
        cuepoint_payload["startTime"] = startTime

        ctype = cuepoint["type"]
        try:
            cuepoint_payload["type"] = _normalize_cuepoint_type(ctype)
        except ValueError as exc:
            errors.dropped.append(str(exc))
            continue

        name = cuepoint.get("name")
        if name is not None and not isinstance(name, str):
            errors.partial.append(f"Name must be a string: {name}")
        elif name is not None:  # pragma: no branch - covered by valid cuepoints
            cuepoint_payload["name"] = name

        activeLoop = cuepoint.get("activeLoop")
        if activeLoop is not None:
            try:
                cuepoint_payload["activeLoop"] = _normalize_bool(activeLoop, context="edit")
            except ValueError as exc:
                errors.partial.append(str(exc))
        
        endTime = cuepoint.get("endTime")
        if endTime is not None and not isinstance(endTime, float):
            errors.partial.append(f"endTime must be a float: {endTime}")
        elif endTime is not None:
            cuepoint_payload["endTime"] = endTime
        
        color = cuepoint.get("color")
        if color is not None:
            try:
                cuepoint_payload["color"] = _normalize_color(color)
            except ValueError as exc:
                errors.partial.append(str(exc))
        
        normalized_cuepoints.append(cuepoint_payload)
    return normalized_cuepoints, errors

class TempoMarkerUpdate(TypedDict):
    """Editable tempo marker dict used when updating tracks."""
    startTime: float
    bpm: float | int

@dataclass
class TempomarkerErrors:
    """Structured tempomarker validation errors."""
    fatal: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

def _normalize_tempomarkers(
    tempomarkers: object,
) -> tuple[list[TempoMarkerUpdate], TempomarkerErrors]:
    """Normalize tempomarkers and return errors."""
    normalized_tempomarkers: list[TempoMarkerUpdate] = []
    errors = TempomarkerErrors()
    if not isinstance(tempomarkers, list):
        errors.fatal.append(f"Tempomarkers must be a list. Given [{type(tempomarkers)}]")
        return normalized_tempomarkers, errors
    seen_start_times: set[float] = set()
    for marker in tempomarkers:
        if not isinstance(marker, dict):
            errors.dropped.append(f"Invalid entry: {marker}")
            continue
        missing_required = set(("startTime", "bpm")) - marker.keys()
        if missing_required:
            errors.dropped.append(f"Missing required keys: {missing_required}")
            continue

        start_time = marker["startTime"]
        if not isinstance(start_time, float):
            errors.dropped.append(f"startTime must be float: {type(start_time)}")
            continue
        if start_time in seen_start_times:
            errors.dropped.append(f"Duplicate startTime: {start_time}")
            continue
        seen_start_times.add(start_time)

        bpm = marker["bpm"]
        if not isinstance(bpm, (float, int)):
            errors.dropped.append(f"bpm must be float or int: {type(bpm)}")
            continue

        normalized_tempomarkers.append({"startTime": start_time, "bpm": bpm})
    return normalized_tempomarkers, errors

class TrackUpdate(TypedDict, total=False):
    """Editable track dict used when updating track fields."""
    title: str
    artist: str
    albumTitle: str
    label: str
    remixer: str
    mix: str
    composer: str
    producer: str
    grouping: str
    lyricist: str
    comment: str
    key: str
    genre: str
    rating: int
    color: Color
    year: int
    playCount: int | str
    trackNumber: int
    energy: float | str
    danceability: float | str
    popularity: float | str
    happiness: float | str
    extra1: str
    extra2: str
    tags: list[int]
    tempomarkers: list[TempoMarkerUpdate]
    cuepoints: list[CuePointUpdate]
    incoming: bool
    archived: bool
