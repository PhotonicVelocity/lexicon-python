# Lexicon Python

Python client for the Lexicon DJ Local API.

This SDK wraps the Lexicon Local API with resource groups, sensible defaults, and
optional validation. It is designed for scripting library automation, playlist
management, and metadata edits while keeping a clean escape hatch to the raw API.

## Features

- Resource grouped client (`lex.tracks`, `lex.playlists`, `lex.tags`)
- Pagination handled for `tracks.list()` (API returns 1000 per page)
- Validation modes for inputs: warn (default), strict, or off
- Typed responses and payload hints (TypedDicts and Literals)
- Optional interactive playlist chooser via `InquirerPy`
- Raw request escape hatch via `lex.request(...)`

## Requirements

- Python 3.9+
- Lexicon DJ running with Local API enabled

## Install

```bash
pip install lexicon-python
```

## Quickstart

```python
from lexicon import Lexicon

lex = Lexicon()

# list tracks (default fields: id, artist, title, bpm, key, ...)
tracks = lex.tracks.list(limit=10) or []
for t in tracks:
    print(t.get("artist"), "-", t.get("title"))

# search — pass fields=[...] for a narrow projection, or fields="all" for the
# full payload (tempomarkers, cuepoints, tags, etc.)
results = lex.tracks.search({"artist": "Daft Punk"}) or []
print("matches:", len(results))

# get a single track by id — always returns the full record
full = lex.tracks.get(123)

# get a playlist by path
playlist = lex.playlists.get_by_path(["Genres", "Drum & Bass"], playlist_type="folder")
print(playlist)
```

## Configuration

By default the client targets:

- Host: `localhost`
- Port: `48624`

You can override these via constructor args or environment variables.

```python
lex = Lexicon(host="127.0.0.1", port=48624, raise_on_error=False)
```

Other options:

- `default_timeout`: request timeout in seconds
- `session`: optional `requests.Session`
- `raise_on_error`: raise HTTP errors instead of returning None

Environment variables:

```bash
export LEXICON_HOST=localhost
export LEXICON_PORT=48624
```

## Validation Modes

Many methods accept a `validation` parameter with three modes:

- `"warn"` (default): invalid inputs are skipped with a warning. This avoids API
  failures, but intended changes may be ignored.
- `"strict"`: invalid inputs raise `ValueError`.
- `"off"`: skips normalization and sends inputs as-is (inputs must match API-native shapes)

Example:

```python
lex.tracks.search({"rating": "bad"}, validation="warn")   # logs warning
lex.tracks.search({"rating": "bad"}, validation="strict") # raises
lex.tracks.search({"rating": "bad"}, validation="off")    # sends as-is
```

## Convenience vs Raw API

This SDK adds several quality-of-life behaviors on top of the raw Lexicon API.
In general, response shapes are unwrapped (e.g., `"data": {...}` is removed and
single-item lists are collapsed to a single dict).

### Additional Methods (Not in the Raw API)

- `tracks.get_many()` repeats `get()` and preserves input order.
- `playlists.get_many()` repeats `get()` and preserves input order.
- `playlists.tracks.get()` fetches track dicts in playlist order.
- `playlists.tracks.update()` replaces the full track list (remove + add).
- `playlists.choose()` provides an interactive chooser (wraps list + get).
- `playlists.get_path()` resolves a path from a playlist tree.

### Input Normalization (Broader Accepted Inputs)

- **ID normalization**: Many methods accept lists of IDs instead of a single ID
  for easier batch operations.
- **Field selection**: By default, `tracks.list()` and `tracks.search()` return a
  minimal set of fields rather than the full payload:
    - `id`, `artist`, `title`, `albumTitle`, `bpm`, `key`, `duration`, `year`
    - Fields used as a search filter or sort item are also returned.
- **Search filter normalization**:
  - Text fields accept `None` (becomes `"NONE"` in filter context).
  - Numeric filters accept `None` (becomes `"0"`).
  - Date filters accept `YYYY-MM-DD`, full datetime strings, or `datetime.date` /
    `datetime.datetime` inputs (time is stripped).
      - Comparisons (`>YYYY-MM-DD`) are warned/blocked because the API currently ignores them.
- **Sort normalization**:
  - Accepts tuple shorthand: `[("title", "asc")]`.
- **Track update helpers**:
  - Cuepoint and tempomarker entries are normalized (e.g., cuepoint type accepts
    name/number variants).
  - Invalid entries can be skipped in `"warn"` mode without failing the update.

If no SDK normalization is desired, use `validation="off"` and pass
API-native payloads. API-native shapes are also accepted in `"warn"`/`"strict"`;
those modes simply add normalization/validation on top. For fully raw access,
`lex.request(...)` can always be called directly.

## Tracks

Common operations:

```python
track = lex.tracks.get(123)
tracks = lex.tracks.get_many([1, 2, 3])
tracks = lex.tracks.list(limit=100)
tracks = lex.tracks.search({"artist": "Daft Punk"})

added = lex.tracks.add(["/path/to/file1.mp3", "/path/to/file2.mp3"])
updated = lex.tracks.update(123, {"title": "New Title"})
lex.tracks.delete([123, 456])

# Replace tempomarkers while keeping cuepoints anchored to the same beats
lex.tracks.update_tempogrid(123, [{"startTime": 0.0, "bpm": 124.0}])
```

Notes:

- `tracks.search()` results are capped at 1000 by the API.
- `tracks.get_many()` preserves input order and returns `None` for missing IDs.
- `tracks.get()` always returns the full record (no `fields` parameter).
- For `tracks.list()` / `tracks.search()`:
  - `fields=None` returns a minimal default set.
    - In `validation="off"` mode, `fields=None` returns the full API payload.
  - Pass a list of field names for a narrow projection
    (`fields=["id", "location"]`).
  - `fields="all"` or `fields="*"` requests the full payload.
  - Comma-separated strings (e.g. `"id,location"`) are *not* accepted; pass a
    list. With `validation="warn"` the call falls back to the default field
    set and logs.
- `tracks.add()` returns track dicts, but analysis fields (tempo markers, key, etc.)
  may be populated later by Lexicon.
- `tracks.update_tempogrid()` replaces tempomarkers while preserving each
  cuepoint's beat position by rewriting `startTime`/`endTime` against the new
  grid. Use `tracks.update(track_id, {"tempomarkers": [...]})` directly if you
  want the raw field replacement (cuepoints' seconds stay put, beats shift).

### Track Payload Shapes

Rich-payload fields like `cuepoints` and `tempomarkers` aren't in the default
field set; request them explicitly (`fields=["cuepoints", "tempomarkers"]`) or
ask for everything (`fields="all"`). Their shapes are typed via
`CuePointResponse` and `TempoMarkerResponse`, both re-exported from `lexicon`:

```python
from lexicon import TrackResponse, TempoMarkerResponse, CuePointResponse
```

Color values (cuepoint/tag/etc. `color` fields) are Lexicon-specific name strings
declared by the `Color` literal type. To convert a name to RGB:

```python
from lexicon import color_rgb

color_rgb("red_dark")  # → (158, 15, 7)
```

### Track Search, Filters, and Sort

`tracks.search(filter=...)` accepts a dict of field names and values. The SDK
validates fields/values in `"warn"`/`"strict"` modes and can send API-native values
in `"off"` mode.

Examples:

```python
# text filters
lex.tracks.search({"artist": "Daft Punk"})

# numeric filters (strings)
lex.tracks.search({"bpm": "120"})
lex.tracks.search({"bpm": "120-128"})
lex.tracks.search({"bpm": ">=120"})

# date filters (YYYY-MM-DD)
lex.tracks.search({"dateAdded": "2024-01-01"})

# tag filters (comma-separated names)
# - default: OR across tags
# - prefix with "~" to require ALL tags (AND)
# - prefix with "!" to exclude a tag
lex.tracks.search({"tags": "Rock, Chill"})     # Rock OR Chill
lex.tracks.search({"tags": "~Rock, Chill"})    # Rock AND Chill
lex.tracks.search({"tags": "~Rock, !Chill"})   # Rock AND NOT Chill
```

Tag filter details:

- Input is a single string with comma-separated tag names.
- Whitespace is ignored around commas.
- `~` at the start switches from OR to AND for the list.
- `!` before a tag name negates that tag.
- There is no supported way to search for “no tags”; `NONE` is not accepted.

Sort can be expressed in two shapes:

- API-native: list of dicts: `[{"field": "title", "dir": "asc"}]`
- Alternative: list of tuples: `[("title", "asc")]`

API-native dicts work in all modes; `validation="off"` requires the dict shape.

## Playlists

```python
playlist = lex.playlists.get(42)
playlist = lex.playlists.get_by_path(["Genres", "Drum & Bass"], playlist_type="playlist")
tree = lex.playlists.list()

new_id = lex.playlists.add("Demo Playlist", playlist_type="playlist", parent_id=1)
lex.playlists.update(new_id, name="Renamed Playlist")
lex.playlists.delete([new_id])
```

Playlist type accepts:

- `"folder"`, `"playlist"`, `"smartlist"`
- `1`, `2`, `3` (or string numerals `"1"`, `"2"`, `"3"`)

### Playlist tracks helpers
For getting the tracks of a playlist or editing the tracklist.

```python
track_ids = lex.playlists.tracks.list(42)
tracks = lex.playlists.tracks.get(42)
lex.playlists.tracks.add(42, [1, 2, 3])
lex.playlists.tracks.remove(42, [1, 2])
lex.playlists.tracks.update(42, [3, 2, 1])
```

## Tags

```python
tags = lex.tags.list()
new_tag = lex.tags.add(category_id=1, label="Demo Tag")
lex.tags.update(new_tag["id"], label="Renamed Tag")
lex.tags.delete(new_tag["id"])

categories = lex.tags.categories.list()
new_cat = lex.tags.categories.add(label="Demo Category", color="red")
lex.tags.categories.update(new_cat["id"], label="Renamed Category")
lex.tags.categories.delete(new_cat["id"])
```

## Tools

Interactive playlist chooser (requires InquirerPy):

```python
choice = lex.playlists.choose()
print(choice)

# Or avoid an API call if you already have the tree
playlist_tree = lex.playlists.list()
choice = lex.tools.playlists.choose_playlist(playlist_tree) if playlist_tree else None
print(choice)
```

Helper to resolve a playlist path from a tree:

```python
path = lex.playlists.get_path(42)
print(path)

# Or avoid an API call if you already have the tree
playlist_tree = lex.playlists.list()
path = lex.tools.playlists.get_path_from_tree(playlist_tree, playlist_id=42)
print(path)

# -> ["Genres", "Drum & Bass"]
```

## Raw Requests (Escape Hatch)
The API can always be accessed directly with `lex.request`:

```python
payload = lex.request("GET", "/tracks", params={"fields": "all"})
```

## Resource Overview

High level namespaces (full mapping in `docs/resource-map.md`):

- `lex.tracks`: get, get_many, list, search, add, update, delete
- `lex.playlists`: get, get_many, list (tree root), get_path, get_by_path, add, update, delete, choose
- `lex.playlists.tracks`: list (IDs), get (track dicts), add, remove, update
- `lex.tags`: list, add, update, delete
- `lex.tags.categories`: list, add, update, delete

## Type Hints

The SDK includes TypedDict and Literal types for payloads and enums. These are
intended to improve editor autocomplete and static checks.

For full payload schemas and endpoint details, refer to the Lexicon API docs:

- https://www.lexicondj.com/docs/developers/api
- https://www.lexicondj.com/developer/api-docs.yaml

## Development

### Setup

#### Pip 

Ensure that you have Python 3.9+ installed locally.
To install all runtime and dev dependencies into a local virtual environment using pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

#### uv

To use [uv](https://docs.astral.sh/uv/) to install all runtime and dev dependencies into a local virtual environment, simply install `uv` and run:

```bash
uv sync --dev
```

The lockfile (`uv.lock`) is checked in to ensure reproducible installs.

### Running Tests

```bash
# Unit tests
make run-tests

# Integration tests (requires Lexicon running)
# Note: Integration tests enforce an empty library state to avoid destructive edits on existing libraries.
# The fixture setup will back up the existing library, clear it for testing, and restore it afterward.
make run-integration-tests
```

### Linting and Formatting

The project uses [ruff](https://docs.astral.sh/ruff/) for both linting and
formatting.

`make test` runs the full suite: format, lint (with auto-fix), then tests.
`make fix` runs all auto-fixers (lint + format) without running tests.

```bash
make test               # format-fix → lint-fix → format-check → lint-check → tests
make fix                # lint-fix → format-fix
make clean              # remove __pycache__, .pytest_cache, .ruff_cache, etc.
```

If you want to run the linters or formatters manually, you can use the following commands:

```bash
make lint-check         # check for lint issues
make lint-fix           # auto-fix lint issues
make format-check       # check formatting
make format-fix         # auto-fix formatting
```

### CI

GitHub Actions runs on every push to `main` and on pull requests
targeting those branches. The pipeline includes:

- **Tests** across Python 3.9, 3.10, 3.11, and 3.12
- **Lint and format checks** via ruff on Python 3.12

Before opening a PR, make sure `make test` passes locally.

### Pull Requests

A PR template is provided at `.github/pull_request_template.md`. When opening a
PR, fill in the description, check the relevant change-type boxes, and confirm
testing/checklist items.

## License

MIT (see `LICENSE`).
