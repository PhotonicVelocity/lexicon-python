# Lexicon API Resource Map

This document maps the Lexicon Local API (OpenAPI) endpoints to the SDK
resource namespaces and locks the allowed verb sets per resource.

Source: https://www.lexicondj.com/developer/api-docs.yaml

## Namespace Map

Tracks
- `lex.tracks.get(id)` -> `GET /v1/track` (returns: track dict from `data.track`)
- `lex.tracks.get_many(ids)` -> `GET /v1/track` (SDK helper; repeated calls; returns list aligned to input order, using `None` for missing IDs)
- `lex.tracks.list(...)` -> `GET /v1/tracks` (returns: track list from `data.tracks`)
  - Default fields: `id`, `artist`, `title`, `albumTitle`, `bpm`, `key`, `duration`, `year` (override with `fields=[...]`).
  - Pagination: API returns pages of 1000. Wrapper handles `limit` and `offset` params to collect larger sets.
- `lex.tracks.search(filter, ...)` -> `GET /v1/search/tracks` (returns: track list from `data.tracks`)
  - Default fields: `id`, `artist`, `title`, `albumTitle`, `bpm`, `key`, `duration`, `year`, plus any fields in the search filter (override with `fields=[...]`).
  - Results are capped at 1000 per API; wrapper returns the matching list only.
- `lex.tracks.add(locations)` -> `POST /v1/tracks` (returns: track list from `data.tracks`)
- `lex.tracks.update(id, edits)` -> `PATCH /v1/track` (returns: updated track dict from `data.track`)
- `lex.tracks.delete(ids)` -> `DELETE /v1/tracks` (returns: no body)

Playlists
- `lex.playlists.get(id)` -> `GET /v1/playlist` (returns: playlist dict from `data.playlist`)
- `lex.playlists.get_by_path(path, type)` -> `GET /v1/playlist-by-path` (returns: playlist dict from `data.playlist`)
- `lex.playlists.get_many(ids)` -> `GET /v1/playlist` (SDK helper; repeated calls; returns list aligned to input order, using `None` for missing IDs)
- `lex.playlists.list()` -> `GET /v1/playlists` (returns: playlist tree list from `data.playlists`)
- `lex.playlists.add(name, type, parent_id, smartlist)` -> `POST /v1/playlist` (returns: new playlist ID from `data.id`)
- `lex.playlists.update(id, ...)` -> `PATCH /v1/playlist` (returns: updated playlist dict from `data.playlist`)
- `lex.playlists.delete(ids)` -> `DELETE /v1/playlists` (returns: no body)

Playlist tracks (nested under playlists)
- `lex.playlists.tracks.get(playlist_id)` -> `GET /v1/playlist` + `lex.tracks.get_many(ids)` (SDK helper; returns track dicts in playlist order)
- `lex.playlists.tracks.list(playlist_id)` -> `GET /v1/playlist` (returns: track ID list from `data.playlist.trackIds`)
- `lex.playlists.tracks.add(playlist_id, track_ids, index)` -> `PATCH /v1/playlist-tracks` (returns: no body)
- `lex.playlists.tracks.update(playlist_id, track_ids)` -> `GET /v1/playlist` + `DELETE /v1/playlist-tracks` + `PATCH /v1/playlist-tracks` (SDK helper; replace track list by removing all then adding in order; type 2 only; warn that duplicates are rejected by Lexicon; returns: no body)
- `lex.playlists.tracks.remove(playlist_id, track_ids)` -> `DELETE /v1/playlist-tracks` (returns: no body)

Tags (custom tags)
- `lex.tags.list()` -> `GET /v1/tags` (returns: tag list from `data.tags`)
- `lex.tags.add(category_id, label)` -> `POST /v1/tag` (returns: tag dict from `data`)
- `lex.tags.update(id, ...)` -> `PATCH /v1/tag` (returns: tag dict from `data`)
- `lex.tags.delete(id)` -> `DELETE /v1/tag` (returns: no body)

Tag categories (nested under tags)
- `lex.tags.categories.list()` -> `GET /v1/tags` (returns: category list from `data.categories`)
- `lex.tags.categories.add(label, color)` -> `POST /v1/tag-category` (returns: category dict from `data`)
- `lex.tags.categories.update(id, label, color, tags)` -> `PATCH /v1/tag-category` (returns: category dict from `data`)
- `lex.tags.categories.delete(id)` -> `DELETE /v1/tag-category` (returns: no body)

## Verb Sets (Locked)

- tracks: get, get_many, list, search, add, update, delete
- playlists: get, get_many, list, add, update, delete, get_by_path
- playlists.tracks: get, list, add, remove, update
- tags: list, add, update, delete
- tags.categories: list, add, update, delete

## Escape Hatch

Always supported:
`lex.request(method, path, **params)` -> raw HTTP request to `/v1/...`

## Tools (Interactive Helpers)

These helpers are intentionally kept outside the resource verb sets.

Playlists
- `lex.tools.playlists.choose(...)` -> interactive chooser that returns a playlist dict (uses `list()` then `get(...)`).

## File Map

Proposed module layout for the namespace:

- `lex` -> `src/lexicon/client.py` (client + `request(...)`)
- `lex.tracks` -> `src/lexicon/resources/tracks.py`
- `lex.playlists` -> `src/lexicon/resources/playlists.py`
- `lex.playlists.tracks` -> `src/lexicon/resources/playlist_tracks.py`
- `lex.tags` -> `src/lexicon/resources/tags.py`
- `lex.tags.categories` -> `src/lexicon/resources/tag_categories.py`
- `lex.tools.playlists` -> `src/lexicon/tools/playlists.py`
