<!--
  AI assistant instructions for contributors and coding agents.
  Consolidated from repo `instructions.md` (temporary file removed).
-->

# copilot-instructions

Be productive quickly — the SDK must be a resource-grouped client with a stable raw-request escape hatch.

## Big picture
- Public API is resource-first: think nouns (tracks, playlists, cues) and expose small verb sets per resource.
- Required call shapes (do not invent alternatives):
  - `lex.tracks.get(id)`
  - `lex.tracks.get_many(ids)`
  - `lex.tracks.list(limit=...)`
  - `lex.tracks.search(filter, ...)`
  - `lex.tracks.add(locations)`
  - `lex.playlists.get_many(ids)`
  - `lex.playlists.get_by_path(path, playlist_type)`
  - `lex.playlists.tracks.list(playlist_id)` (explicit nested resource)
- Always include a low-level escape hatch: `lex.request(method, path, **params)` for unwrapped/future endpoints.

## Naming & contract
- Resource names are plural: `tracks`, `playlists`, `cues`, etc.
- Allowed verbs (strict): `get`, `get_many`, `get_by_path`, `list`, `search`, `add`, `update`, `delete`, `remove` — no synonyms.
- Keep returns as plain dicts/lists matching the API JSON (no domain objects by default).

## Nested resources
- Prefer explicit sub-namespaces when a nested resource has multiple operations (e.g. `lex.playlists.tracks.*`).
- Parameter-driven nesting (e.g. `lex.tracks.list(playlist_id=...)`) is only for very small/simple cases.
- `playlists.list()` should return the tree root node (not the API’s single-item list).

## Deferred design choices (do not implement yet)
- Resource objects / rich domain models are intentionally deferred. Reasons:
  - Hidden network calls on object attrs surprise users.
  - Lifecycle, caching and mutation semantics add maintenance cost.
  - Keep v1 simple: plain payloads + helpers. Add objects later if usage patterns demand them.

## Rejected interfaces (do not use)
- Flat client functions (e.g. `lex.get_track(id)`) — explode surface area and harm discoverability.
- Verb-first namespacing (e.g. `lex.get.track(id)`) — worse autocomplete and awkward nesting.

## Stability guarantees (follow exactly)
1. Never remove or rename public methods once released.
2. Add new resources as new namespaces; avoid breaking existing call sites.
3. Keep `lex.request(...)` stable forever as the escape hatch.

## Implementation hints
- Keep the public surface minimal for good autocomplete.
- Return raw JSON-like payloads; make network behavior explicit.
- Validation modes: `"warn"` (default) logs and skips invalid inputs, `"strict"` raises, `"off"` skips normalization and requires API-native shapes.
- Document the escape hatch with one example: `lex.request('GET','/tracks', params={'fields':'all'})`.
- Use NumPy-style docstrings for public methods where practical.
- TypedDict payloads are preferred for type hints; consider dataclasses or Pydantic later as an optional layer.
- Variable naming: use `payload` for request bodies, `response` for API responses, and `data` for `response["data"]` (or `data = response` when the API returns unwrapped payloads).
- Request conventions: `GET /tracks` and `GET /search/tracks` send JSON payloads in the request body; other GETs use query params. POST/PATCH/DELETE use JSON bodies.
- Tools are pure helpers (no API calls) and accept data that callers already fetched.

## Quick examples
- Resource-first: `lex.tracks.get(123)`
- Batch get: `lex.tracks.get_many([123, 456])`
- Batch get: `lex.playlists.get_many([10, 11])`
- Path lookup: `lex.playlists.get_by_path(["Music", "Techno"], playlist_type=2)`
- Add: `lex.tracks.add(["/path/to/song.mp3"])`
- Nested resource: `lex.playlists.tracks.list(playlist_id=42)`
- Raw escape hatch: `lex.request('POST','/playlist', json={'name':'New'})`

-- End of instructions --
