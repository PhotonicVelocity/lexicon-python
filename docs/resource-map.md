# Lexicon API Resource Map

This document maps the Lexicon Local API (OpenAPI) endpoints to the SDK resource namespaces and locks the allowed verb
sets per resource.

Source: https://www.lexicondj.com/developer/api-docs.yaml

## Namespace Map

Client

- `Lexicon(app_name=..., token=...)` sends `X-Lexicon-App` and, with a token, `Authorization: Bearer <token>` on every
  request (Lexicon v1.12 app approval). A token Lexicon returns in `X-Lexicon-Token` is kept in `lex.token`.
- `lex.pair(name)` -> `POST /v1/auth/pair` (returns: token from `data.token`; raises `LexiconAuthError` when refused)

Tracks

- `lex.tracks.get(id)` -> `GET /v1/track` (returns: track dict from `data.track`; `id` may be `"selected"` on v1.12)
- `lex.tracks.selected()` -> `GET /v1/tracks/selected` (returns: ID list from `data.ids`; v1.12)
- `lex.tracks.get_many(ids)` -> `GET /v1/track` (SDK helper; repeated calls; returns list aligned to input order, using
  `None` for missing IDs)
- `lex.tracks.list(...)` -> `GET /v1/tracks` (returns: track list from `data.tracks`)
  - Default fields: `id`, `artist`, `title`, `albumTitle`, `bpm`, `key`, `duration`, `year` (override with
    `fields=[...]`).
  - Pagination: API returns pages of 1000. Wrapper handles `limit` and `offset` params to collect larger sets.
- `lex.tracks.search(filter, ...)` -> `GET /v1/search/tracks` (returns: track list from `data.tracks`)
  - Default fields: `id`, `artist`, `title`, `albumTitle`, `bpm`, `key`, `duration`, `year`, plus any fields in the
    search filter (override with `fields=[...]`).
  - Pagination: the first request sends no `limit`/`offset`, which v1.11 rejects. When `data.total` is larger than the
    page, the wrapper requests the next pages with `offset` and `limit` (v1.12) until it has every match or `limit=`. On
    v1.11 the second request fails and the wrapper returns the first 1000 with a warning.
  - Filter `id` is sent as a comma separated string. When more tracks match than ids were sent, Lexicon ignored the
    filter (v1.11) and the wrapper returns `None`.
- `lex.tracks.add(locations)` -> `POST /v1/tracks` (returns: track list from `data.tracks`)
- `lex.tracks.update(id, edits)` -> `PATCH /v1/track` (returns: updated track dict from `data.track`; v1.11 returns
  `{id, edits}` or `{}`, so the wrapper falls back to `GET /v1/track`; `id` may be `"selected"` on v1.12)
- `lex.tracks.update_location(id, location, check_file_exists)` -> `PATCH /v1/track/location` (returns: track dict from
  `data.track`; v1.12)
- `lex.tracks.delete(ids)` -> `DELETE /v1/tracks` (returns: no body)
- `lex.tracks.analyze(ids, ...)` -> `POST /v1/control` with action `AudioAnalyzer_Analyze` (returns: no body)
  - Analysis runs in the background with no completion signal; `tempo_range` takes one of the analyze dropdown's eight
    presets and persists as a Lexicon setting.

Playlists

- `lex.playlists.get(id)` -> `GET /v1/playlist` (returns: playlist dict from `data.playlist`)
- `lex.playlists.get_by_path(path, type)` -> `GET /v1/playlist-by-path` (returns: playlist dict from `data.playlist`)
- `lex.playlists.get_many(ids)` -> `GET /v1/playlist` (SDK helper; repeated calls; returns list aligned to input order,
  using `None` for missing IDs)
- `lex.playlists.list()` -> `GET /v1/playlists` (returns: playlist tree list from `data.playlists`)
- `lex.playlists.selected()` -> `GET /v1/playlists/selected` (returns: ID list from `data.ids`; v1.12)
- `lex.playlists.add(name, type, parent_id, smartlist)` -> `POST /v1/playlist` (returns: new playlist ID from `data.id`)
- `lex.playlists.update(id, ...)` -> `PATCH /v1/playlist` (returns: updated playlist dict from `data.playlist`)
- `lex.playlists.delete(ids)` -> `DELETE /v1/playlists` (returns: no body)

Playlist tracks (nested under playlists)

- `lex.playlists.tracks.get(playlist_id)` -> `GET /v1/playlist` + `lex.tracks.get_many(ids)` (SDK helper; returns track
  dicts in playlist order)
- `lex.playlists.tracks.list(playlist_id)` -> `GET /v1/playlist` (returns: track ID list from `data.playlist.trackIds`)
- `lex.playlists.tracks.add(playlist_id, track_ids, index)` -> `PATCH /v1/playlist-tracks` (returns: no body)
- `lex.playlists.tracks.update(playlist_id, track_ids)` -> `GET /v1/playlist` + `DELETE /v1/playlist-tracks` +
  `PATCH /v1/playlist-tracks` (SDK helper; replace track list by removing all then adding in order; type 2 only; warn
  that duplicates are rejected by Lexicon; returns: no body)
- `lex.playlists.tracks.remove(playlist_id, track_ids)` -> `DELETE /v1/playlist-tracks` (returns: no body)

Tags (custom tags)

- `lex.tags.list()` -> `GET /v1/tags` (returns: tag list from `data.tags`)
- `lex.tags.add(category_id, label)` -> `POST /v1/tag` (returns: tag dict from `data`)
- `lex.tags.update(id, ...)` -> `PATCH /v1/tag` (returns: tag dict from `data`)
- `lex.tags.delete(id)` -> `DELETE /v1/tag` (returns: no body)

Tag categories (nested under tags)

- `lex.tags.categories.list()` -> `GET /v1/tags` (returns: category list from `data.categories`)
- `lex.tags.categories.add(label, color)` -> `POST /v1/tag-category` (returns: category dict from `data`)
- `lex.tags.categories.update(id, label, color, tags, position)` -> `PATCH /v1/tag-category` (returns: category dict at
  the top level; `tags` and `position` take effect on v1.12 only)
- `lex.tags.categories.delete(id)` -> `DELETE /v1/tag-category` (returns: no body)

Player

- `lex.player.playing()` -> `GET /v1/playing` (returns: dict with `track`, `progress`, `currentTime` from `data`, or
  `None` when `data.track` is null)
  - Returns the loaded track whether playing or paused. The API has no play state field.
  - For Beatport, Apple Music, and Spotify, `track` is a remote track rather than a library row: `id` is the service's
    own ID and `duration` is the preview length. See api-issues.md.
- `lex.player.queue()` -> `GET /v1/queue` (returns: track list from `data.tracks`; does not include the track in the
  player)

Control

- `lex.control(action, **parameters)` -> `POST /v1/control` (returns: bool; no body)
  - `True` means Lexicon accepted the request. It does not wait for the action and accepts one whose target is missing.
  - Action names follow the newest spec plus the `DeckConnect_*` names v1.12 uses for the spec's `Direct2Cdj_*`, so each
    Lexicon version rejects some of them. See api-issues.md.

## Verb Sets (Locked)

- client: request, control, pair
- tracks: get, get_many, list, search, selected, add, update, update_location, delete, analyze
- playlists: get, get_many, list, selected, add, update, delete, get_by_path
- playlists.tracks: get, list, add, remove, update
- tags: list, add, update, delete
- tags.categories: list, add, update, delete
- player: playing, queue

## Escape Hatch

Always supported: `lex.request(method, path, **params)` -> raw HTTP request to `/v1/...`

## Tools (Interactive Helpers)

These helpers are intentionally kept outside the resource verb sets.

Playlists

- `lex.tools.playlists.choose(...)` -> interactive chooser that returns a playlist dict (uses `list()` then `get(...)`).

## File Map

Proposed module layout for the namespace:

- `lex` -> `src/lexicon/client.py` (client + `request(...)` + `control(...)` + `pair(...)`)
- `lex.tracks` -> `src/lexicon/resources/tracks.py`
- `lex.playlists` -> `src/lexicon/resources/playlists.py`
- `lex.playlists.tracks` -> `src/lexicon/resources/playlist_tracks.py`
- `lex.tags` -> `src/lexicon/resources/tags.py`
- `lex.tags.categories` -> `src/lexicon/resources/tag_categories.py`
- `lex.player` -> `src/lexicon/resources/player.py`
- `lex.tools.playlists` -> `src/lexicon/tools/playlists.py`
