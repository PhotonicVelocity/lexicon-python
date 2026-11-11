# Lexicon Python

Python client for the Lexicon DJ Local API.

This SDK wraps the Lexicon Local API with resource groups, sensible defaults, and optional validation. It is designed
for scripting library automation, playlist management, and metadata edits while keeping a clean escape hatch to the raw
API.

## Features

- Resource grouped client (`lex.tracks`, `lex.playlists`, `lex.tags`, `lex.player`)
- Player and hotkey commands via `lex.player` and `lex.control()`
- Pagination handled for `tracks.list()` and `tracks.search()` (API returns 1000 per page)
- Lexicon v1.12 app approval and tokens, with v1.11 still supported
- Validation modes for inputs: warn (default), strict, or off
- Typed responses and payload hints (TypedDicts and Literals)
- Optional interactive playlist chooser via `InquirerPy`
- Raw request escape hatch via `lex.request(...)`

## Requirements

- Python 3.10+
- Lexicon DJ running with the Local API enabled (Lexicon settings, Local API). Lexicon v1.12 is the target; v1.11 works
  for everything that existed in it (see [Lexicon versions](#lexicon-versions)).

## Install

```bash
pip install lexicon-python
```

## Quickstart

```python
from lexicon import Lexicon

# Verifies the API is reachable; raises LexiconConnectionError otherwise. On Lexicon v1.12
# the first run shows the user a popup asking to allow the app; see Authentication.
lex = Lexicon(app_name="My Lexicon Tool")
playlist = lex.playlists.choose()

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
- `verify_connection` (default `True`): probe the API on construction and raise `LexiconConnectionError` if Lexicon
  isn't reachable, or `LexiconAuthError` if it refuses the app. Set to `False` to build a client without a running
  Lexicon (e.g. for tests).
- `app_name` (default `"lexicon-python"`): the name the user sees in Lexicon's approval popup and settings.
- `token`: the app's API token for Lexicon v1.12 (see below).

Environment variables:

```bash
export LEXICON_HOST=localhost
export LEXICON_PORT=48624         # Lexicon v1.12 lets the user change it in the Local API settings
export LEXICON_APP_NAME="My Lexicon Tool"
export LEXICON_TOKEN=...          # optional, see Authentication
```

## Authentication

Starting in Lexicon v1.12, the user has to allow each app before it can use the API. Every request names the app in the
`X-Lexicon-App` header (`app_name`, default `"lexicon-python"`). Lexicon asks once per name, so give each tool its own.

- **First run:** the first request from a new app name shows the user a popup, and Lexicon holds the request until they
  answer. `Lexicon()` waits up to 70 seconds for that. When the user allows the app, Lexicon sends a token, which the
  client keeps in `lex.token`.
- **On the computer running Lexicon:** an allowed app is let in by name alone, so a local script needs no token.
- **From another device:** every request needs the token. Store `lex.token` and pass it back as `token=` or
  `LEXICON_TOKEN`. Lexicon only keeps a hash, so it cannot show the token again.
- **Pairing explicitly:** `lex.pair()` asks the user right away (waiting up to two minutes) and returns the token.
- **Personal scripts:** the user can instead copy the API token from the Lexicon settings under Local API. Lexicon
  always lets that token in.

```python
from lexicon import Lexicon, LexiconAuthError

try:
    lex = Lexicon(app_name="My Lexicon Tool", token=load_saved_token())
except LexiconAuthError as exc:
    print(exc.error_code, exc)  # 10: not answered yet, 6: blocked, 11: allowed but token missing
```

`LexiconAuthError` (a `LexiconConnectionError`) carries Lexicon's error code:

| Code | Meaning                                                                                        |
| ---- | ---------------------------------------------------------------------------------------------- |
| `10` | The popup was not answered in time, or was closed. Lexicon waits a minute before asking again. |
| `6`  | The user blocked the app. Unblock it in the Lexicon settings.                                  |
| `11` | The name is already allowed, but the request did not send its token.                           |
| `9`  | The token is wrong, or the request looked like it came from a web page.                        |

The user can block or remove an app at any time in the Lexicon settings, which stops its token from working. Lexicon
v1.11 and older have no authentication and ignore these headers.

## Validation Modes

Many methods accept a `validation` parameter with three modes:

- `"warn"` (default): invalid inputs are skipped with a warning. This avoids API failures, but intended changes may be
  ignored.
- `"strict"`: invalid inputs raise `ValueError`.
- `"off"`: skips normalization and sends inputs as-is (inputs must match API-native shapes)

Example:

```python
lex.tracks.search({"rating": "bad"}, validation="warn")   # logs warning
lex.tracks.search({"rating": "bad"}, validation="strict") # raises
lex.tracks.search({"rating": "bad"}, validation="off")    # sends as-is
```

## Convenience vs Raw API

This SDK adds several quality-of-life behaviors on top of the raw Lexicon API. In general, response shapes are unwrapped
(e.g., `"data": {...}` is removed and single-item lists are collapsed to a single dict).

### Additional Methods (Not in the Raw API)

- `tracks.get_many()` repeats `get()` and preserves input order.
- `playlists.get_many()` repeats `get()` and preserves input order.
- `playlists.tracks.get()` fetches track dicts in playlist order.
- `playlists.tracks.update()` replaces the full track list (remove + add).
- `playlists.choose()` provides an interactive chooser (wraps list + get).
- `playlists.get_path()` resolves a path from a playlist tree.

### Input Normalization (Broader Accepted Inputs)

- **ID normalization**: Many methods accept lists of IDs instead of a single ID for easier batch operations.
- **Field selection**: By default, `tracks.list()` and `tracks.search()` return a minimal set of fields rather than the
  full payload:
  - `id`, `artist`, `title`, `albumTitle`, `bpm`, `key`, `duration`, `year`
  - Fields used as a search filter or sort item are also returned.
- **Search filter normalization**:
  - Text fields accept `None` (becomes `"NONE"` in filter context).
  - Numeric filters accept `None` (becomes `"0"`).
  - Date filters accept `YYYY-MM-DD`, full datetime strings, or `datetime.date` / `datetime.datetime` inputs (time is
    stripped).
    - Comparisons (`>YYYY-MM-DD`) are warned/blocked because the API currently ignores them.
- **Sort normalization**:
  - Accepts tuple shorthand: `[("title", "asc")]`.
- **Track update helpers**:
  - Cuepoint and tempomarker entries are normalized (e.g., cuepoint type accepts name/number variants).
  - Invalid entries can be skipped in `"warn"` mode without failing the update.

If no SDK normalization is desired, use `validation="off"` and pass API-native payloads. API-native shapes are also
accepted in `"warn"`/`"strict"`; those modes simply add normalization/validation on top. For fully raw access,
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

# Lexicon v1.12: the selection in Lexicon, and relocating a track to another file
ids = lex.tracks.selected()                      # [12, 7, 33]
track = lex.tracks.get("selected")               # the topmost selected track
lex.tracks.update("selected", {"rating": 5})     # every selected track
moved = lex.tracks.update_location(123, "/Music/new/file.mp3")

# Replace tempomarkers while keeping cuepoints anchored to the same beats
lex.tracks.update_tempogrid(123, [{"startTime": 0.0, "bpm": 124.0}])

# Start Lexicon's analyzer on specific tracks
lex.tracks.analyze([123, 456], analyze_beatgrid=True, do_not_overwrite=False)
```

Notes:

- `tracks.search()` returns every match on Lexicon v1.12, which pages results 1000 at a time; pass `limit=` to cap it.
  Lexicon v1.11 returns at most 1000 matches and logs a warning when there are more.
- `tracks.update()` returns the track as Lexicon stored it. On v1.12 that comes from the PATCH response; on older
  versions the client fetches it again.
- A `cuepoints` or `tempomarkers` edit replaces the whole list, and Lexicon clears the `data` of any cue or marker sent
  without it. That `data` holds what a DJ app import stored (Traktor, Rekordbox, ...), so to keep it, edit the list from
  `tracks.get()` and send it back. `update_tempogrid()` does this for cuepoints.
- `tracks.update_location()` only changes the library; the file is never moved. Lexicon normalizes the path, so read
  `location` back from the returned track.
- `tracks.get_many()` preserves input order and returns `None` for missing IDs.
- `tracks.get()` always returns the full record (no `fields` parameter).
- For `tracks.list()` / `tracks.search()`:
  - `fields=None` returns a minimal default set.
    - In `validation="off"` mode, `fields=None` returns the full API payload.
  - Pass a list of field names for a narrow projection (`fields=["id", "location"]`).
  - `fields="all"` or `fields="*"` requests the full payload.
  - Comma-separated strings (e.g. `"id,location"`) are _not_ accepted; pass a list. With `validation="warn"` the call
    falls back to the default field set and logs.
- `tracks.add()` returns track dicts, but analysis fields (tempo markers, key, etc.) may be populated later by Lexicon.
- `tracks.update_tempogrid()` replaces tempomarkers while preserving each cuepoint's beat position by rewriting
  `startTime`/`endTime` against the new grid. Use `tracks.update(track_id, {"tempomarkers": [...]})` directly if you
  want the raw field replacement (cuepoints' seconds stay put, beats shift).
- `tracks.analyze()` returns as soon as Lexicon accepts the request. Analysis runs in the background and the API has no
  completion signal, so poll `tracks.get()` and watch `tempomarkers`, `bpm`, `key`, or `dateModified`.
- `tracks.analyze(tempo_range=...)` takes one of the eight ids Lexicon's analyze dropdown stores: `"0_300"` (Any),
  `"58_115"`, `"68_135"`, `"78_155"`, `"88_175"`, `"98_195"`, `"128_255"`, `"180_300"` (180+). An equivalent
  `(min, max)` tuple works too. The value is written to Lexicon's stored analysis setting and persists after the call;
  the boolean options apply to that run only.

### Track Payload Shapes

Rich-payload fields like `cuepoints` and `tempomarkers` aren't in the default field set; request them explicitly
(`fields=["cuepoints", "tempomarkers"]`) or ask for everything (`fields="all"`). Their shapes are typed via
`CuePointResponse` and `TempoMarkerResponse`, both re-exported from `lexicon`:

```python
from lexicon import TrackResponse, TempoMarkerResponse, CuePointResponse
```

Color values (cuepoint/tag/etc. `color` fields) are Lexicon-specific name strings declared by the `Color` literal type.
To convert a name to RGB:

```python
from lexicon import color_rgb

color_rgb("red_dark")  # → (158, 15, 7)
```

### Track Search, Filters, and Sort

`tracks.search(filter=...)` accepts a dict of field names and values. The SDK validates fields/values in
`"warn"`/`"strict"` modes and can send API-native values in `"off"` mode.

Examples:

```python
# text filters
lex.tracks.search({"artist": "Daft Punk"})

# numeric filters (strings)
lex.tracks.search({"bpm": "120"})
lex.tracks.search({"bpm": "120-128"})
lex.tracks.search({"bpm": ">=120"})
lex.tracks.search({"bpm": "120~128"})  # stops before 128

# date filters (YYYY-MM-DD)
# - ">" is that day and later, "<" is before that day
lex.tracks.search({"dateAdded": "2024-01-01"})
lex.tracks.search({"dateAdded": ">2024-01-01"})

# tag filters (comma-separated names)
# - default: OR across tags
# - prefix with "~" to require ALL tags (AND)
# - prefix with "!" to exclude a tag
lex.tracks.search({"tags": "Rock, Chill"})     # Rock OR Chill
lex.tracks.search({"tags": "~Rock, Chill"})    # Rock AND Chill
lex.tracks.search({"tags": "~Rock, !Chill"})   # Rock AND NOT Chill
lex.tracks.search({"tags": None})              # no tags at all (v1.12)

# Lexicon v1.12: look tracks up by id, or by file extension
lex.tracks.search({"id": [12, 48, 153]}, fields=["id", "title"])
lex.tracks.search({"fileType": "flac"})
```

Tag filter details:

- Input is a single string with comma-separated tag names.
- Whitespace is ignored around commas.
- `~` at the start switches from OR to AND for the list.
- `!` before a tag name negates that tag.
- `None` finds tracks without any tag on Lexicon v1.12 (unless a tag is labeled "None").

Lexicon v1.12 rejects a filter on a field it cannot filter with an error, where v1.11 silently ignored it. The `id`
filter is the dangerous case on v1.11, which ignores it and matches the whole library, so `search()` returns `None` when
more tracks come back than ids were asked for.

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
lex.playlists.update(new_id, position=0)  # v1.12: the others shift down, like dragging
lex.playlists.delete([new_id])

selected = lex.playlists.selected()  # v1.12: IDs selected in the playlist tree
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

# Lexicon v1.12: reorder a category's tags (every tag it has, in the new order; tags from
# other categories move in), and move the category itself
lex.tags.categories.update(new_cat["id"], tags=[12, 10, 11])
lex.tags.categories.update(new_cat["id"], position=0)
```

## Player

```python
playing = lex.player.playing()  # None when no track is loaded
if playing:
    print(playing["track"]["title"], playing["currentTime"], playing["progress"])

queue = lex.player.queue()  # the tracks after the loaded one
```

`playing()` returns the loaded track whether it is playing or paused. For Beatport, Apple Music, and Spotify tracks,
`track` is not a library row: `id` is the service's own track ID, and `duration` is the length of the preview clip.

## Control

`lex.control()` runs the commands that can be bound to a hotkey. Parameters use their API names.

```python
lex.control("MusicPlayer_TogglePlay")
lex.control("MusicPlayer_Load", id=123)
lex.control("MusicPlayer_Seek", seconds=30)
```

It returns `True` when Lexicon accepts the request. Lexicon does not wait for the action to finish and has no completion
signal, and it accepts an action whose target is missing, such as one for the selected tracks with nothing selected.
Names are checked against the `ControlAction` list; pass `validation="off"` for one that is not listed. The list covers
Lexicon v1.11 and v1.12, so it holds both names of the actions v1.12 renamed: v1.12 calls the `Direct2Cdj_*` player
actions `DeckConnect_*` (`DeckConnect_LoadDeck`, `DeckConnect_LoadDeck1` to `8`, `DeckConnect_LoadEmptyDeck`) and
rejects the old names.

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

- `lex.tracks`: get, get_many, list, search, selected, add, update, update_location, update_tempogrid, add_tags,
  remove_tags, delete, analyze
- `lex.playlists`: get, get_many, list (tree root), selected, get_path, get_by_path, add, update, delete, choose
- `lex.playlists.tracks`: list (IDs), get (track dicts), add, remove, update
- `lex.tags`: list, add, update, delete
- `lex.tags.categories`: list, add, update, delete
- `lex.player`: playing, queue
- `lex.control()`: run a control action
- `lex.pair()`: ask the user to allow the app and get its token (v1.12)

## Lexicon versions

The client targets Lexicon v1.12 and keeps working with v1.11. Requests are the same, and the client falls back where
v1.11 answers differently:

| Feature                                              | v1.12                   | v1.11                                                    |
| ---------------------------------------------------- | ----------------------- | -------------------------------------------------------- |
| App approval, `token`, `pair()`                      | required                | no authentication; headers ignored                       |
| `selected()`, `get("selected")`, `update_location()` | yes                     | `None` (endpoint does not exist)                         |
| `search()` past 1000 matches                         | pages through all       | first 1000, with a warning                               |
| `search()` filters `id`, `fileType`, `tags=None`     | yes                     | `id`: `None`; `fileType`: error; `tags=None`: no matches |
| `update()` result                                    | from the PATCH response | fetched again                                            |
| `playlists.update(position=)`                        | inserts, others shift   | stores the number, positions can overlap                 |
| `tags.categories.update(tags=, position=)`           | yes                     | accepted but ignored                                     |
| Cue `activeLoop`                                     | sent as `true`/`false`  | not tested with booleans                                 |
| DeckConnect actions                                  | `DeckConnect_*`         | `Direct2Cdj_*`                                           |

## Type Hints

The SDK includes TypedDict and Literal types for payloads and enums. These are intended to improve editor autocomplete
and static checks.

For full payload schemas and endpoint details, refer to the Lexicon API docs:

- https://www.lexicondj.com/docs/developers/api
- https://www.lexicondj.com/developer/api-docs.yaml

## Development

### Setup

#### Pip

Ensure that you have Python 3.9+ installed locally. To install all runtime and dev dependencies into a local virtual
environment using pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

#### uv

To use [uv](https://docs.astral.sh/uv/) to install all runtime and dev dependencies into a local virtual environment,
simply install `uv` and run:

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

The integration fixture quits Lexicon and renames `main.db` while it runs. If the Lexicon data folder is synced to
another machine (Syncthing, Dropbox, iCloud), pause the sync first. On Lexicon v1.12 the first run shows an approval
popup for "lexicon-python integration tests"; Lexicon remembers the answer outside the library, so later runs do not ask
again.

### Linting and Formatting

The project uses [ruff](https://docs.astral.sh/ruff/) for both linting and formatting.

`make test` runs the full suite: format, lint (with auto-fix), then tests. `make fix` runs all auto-fixers (lint +
format) without running tests.

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

### Pre-commit hook (recommended)

The repo ships a [pre-commit](https://pre-commit.com/) config (`.pre-commit-config.yaml`) that mirrors the CI lint job.
After cloning, install the hook once:

```bash
uv tool install pre-commit  # or: pipx install pre-commit
pre-commit install
```

`git commit` now runs `ruff format` + `ruff check --fix` on staged files and blocks the commit on any failure. Run
against the whole repo any time with:

```bash
pre-commit run --all-files
```

The ruff version is pinned in `.pre-commit-config.yaml`; bump it when CI bumps to keep them aligned.

### CI

GitHub Actions runs on every push to `main` and on pull requests targeting those branches. The pipeline includes:

- **Tests** across Python 3.9, 3.10, 3.11, and 3.12
- **Lint and format checks** via ruff on Python 3.12

Before opening a PR, make sure `make test` passes locally.

### Pull Requests

A PR template is provided at `.github/pull_request_template.md`. When opening a PR, fill in the description, check the
relevant change-type boxes, and confirm testing/checklist items.

## License

MIT (see `LICENSE`).
