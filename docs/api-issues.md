# API/Docs Issues

## Incorrect or Incomplete OpenAPI Spec Documentation

- `POST /v1/tag` returns the tag object at the top level (no `data` wrapper), while the OpenAPI spec shows
  `{"data": {...}}`.
- `PATCH /v1/tag` returns the tag object at the top level (no `data` wrapper), while the OpenAPI spec shows
  `{"data": {...}}`.
- `POST /v1/tag-category` returns the category object at the top level (no `data` wrapper), while the OpenAPI spec shows
  `{"data": {...}}`.
- `PATCH /v1/tag-category` returns the category object at the top level (no `data` wrapper), while the OpenAPI spec
  shows `{"data": {...}}`.
- `DELETE /v1/track` returns `errorCode=4` (endpoint does not exist) in current Lexicon build, but OpenAPI spec
  documents it. `DELETE /v1/tracks` with JSON body `{"ids":[...]}` succeeds.
- `DELETE /v1/playlists` fails when `ids` are passed as query params per OpenAPI spec; JSON body `{"ids":[...]}`
  succeeds.
- `GET /v1/search/tracks` & `GET /v1/tracks` sort parameters only work when sent in the JSON body, not as URL query
  parameters, contrary to OpenAPI spec and website "Try it out" examples. Multiple formats were tested:
  - Expected to work (per docs; observed working):
    - `sort` in JSON body on GET request
      - 200 OK: accepts `{"sort":[{"field":"duration","dir":"asc"}]}` when sent in JSON body alongside other params.
  - Expected to work (per OpenAPIdocs; observed failing):
    - `sort=[{"field":"duration","dir":"asc"}]` (raw JSON)
      - 400: `'sort' must be an array, value: [{'field':'duration','dir':'asc'}]` `errorCode: 5`
    - `sort=%5B%7B%22field%22%3A%20%22duration%22%2C%20%22dir%22%3A%20%22asc%22%7D%5D` (URL-encoded JSON)
      - 400: `'sort' must be an array, value: [{'field': 'duration', 'dir': 'asc'}]` `errorCode: 5`
    - `sort=%5B%7B%22field%22%3A+%22duration%22%2C+%22dir%22%3A+%22asc%22%7D%5D` (plus-encoded JSON)
      - 400: `'sort' must be an array, value: [{'field': 'duration', 'dir': 'asc'}]` `errorCode: 5`
    - `sort[0][field]=duration&sort[0][dir]=asc` (form-style array of objects)
      - 400: `'sort' must be an array, value: [object Object]` `errorCode: 5`
  - Expected to work (per "Try it out" on website; observed failing):
    - `sort=duration` (single value)
      - 400: `'sort' must be an array, value: duration` `errorCode: 5`
    - `sort=duration&sort=id` (multiple values)
      - 400: `'sort' must be an array, value: id` `errorCode: 5`
- `GET /v1/playlist-by-path` defaults `type` query parameter to `2`, but web documentation implies it is optional for
  all types and "might be useful" for disambiguation.
- `fileType` appears in the OpenAPI spec as a valid Track field, but it is not returned in `GET /v1/track` or
  `GET /v1/tracks`, and the API rejects `fields=fileType`.
- `GET /v1/search/tracks` drops comparison filters for date fields (`lastPlayed`, `dateAdded` and `dateModified`) when
  using `>` or `<` operators (works in the Lexicon UI, not via API).
- `GET /v1/search/tracks` does not support filtering for tracks with no tags (`tags=NONE` returns all tracks instead of
  only untagged tracks).
- `GET /v1/playlist` can return duplicate `trackIds` when the playlist is a folder; clients may need to deduplicate.
- `Cuepoint` schema has undocumented `activeLoop` item.

### Added 2026-04-02

- `GET /v1/search/tracks` crashes with `Cannot read properties of undefined (reading 'toUpperCase')` when a sort object
  is missing the `dir` key (e.g. `{"field": "dateAdded"}`). The `dir` key must always be provided (`"asc"` or `"desc"`).
- `PATCH /v1/tag` rejects position updates with `"Position within category already in use"` (errorCode 108) if the
  target position is occupied. There is no insert/swap behavior — the target position must be vacated first.
- `PATCH /v1/playlist` allows setting position to an already-occupied value without error. This creates overlapping
  positions with no bumping/insert behavior. Ties are broken by ID order. Inconsistent with tag position behavior which
  rejects collisions.
- `PATCH /v1/tag-category` does not accept a `position` parameter (`"'position' is not allowed"`).
- `PATCH /v1/tag-category` accepts a `tags` array parameter per the spec, and the response echoes it back, but tag
  membership is unchanged. The category's `tags` list in API responses becomes out of sync with actual state (driven by
  each tag's `categoryId`). The UI is unaffected. To move tags between categories, use `PATCH /v1/tag` with a new
  `categoryId`.
- `PATCH /v1/track` response shape varies by edit type: title/field edits return `{"id": ..., "edits": {...}}`, tag
  edits return `{}` (empty dict). Client must fall back to the input `track_id` for re-fetching.

### Added 2026-09-02 (Lexicon 1.11.13)

- `POST /v1/control` rejects the documented action `TrackBrowser_AnalyzeStart` with `Unknown control action`
  (`errorCode: 5`). The app maps that name to the internal id `AudioAnalyzer_Analyze`, and the endpoint accepts the
  internal id. Parameters, read from the app bundle:
  - `trackIds` (required, non-empty array of track IDs; an empty array returns 200 and does nothing)
  - `analyzeKey`, `analyzeBeatgrid`, `analyzeWaveform`, `analyzeEnergy`, `doNotOverwrite` (booleans; an omitted key
    falls back to the matching Lexicon analysis setting for that run)
  - `tempoRange` (string `"<min>_<max>"`). The value is written to the Lexicon analysis setting and persists after the
    call; the boolean flags apply to that run only. The analyze dialog's dropdown stores one of eight ids: `0_300`
    ("Any"), `58_115`, `68_135`, `78_155`, `88_175`, `98_195`, `128_255`, `180_300` ("180+"). The handler accepts any
    `^\d+_\d+$` string and the analyzer clamps the stored bounds to 50..300 when it runs, but the dropdown has no label
    for a non-preset value.
  - The response is `{}`. Analysis runs in the background and the API has no completion signal.
- The `Control Actions` enum omits `Application_SetColor`, `Application_SetEnergy`, `Application_SetDanceability`,
  `Application_SetPopularity`, and `Application_SetHappiness`, although the endpoint description documents their
  parameters. All five exist in the app.
- `MusicPlayer_Load` (added to the spec between Lexicon 1.10 and 1.11.13) has an undocumented parameter `id`, the track
  ID to load into the player. With no `id` the call returns 200 and does nothing.
- `GET /v1/playing` returns `data.currentTime` where the spec documents `data.seconds`. `data.track` and `data.progress`
  match the spec.
- Four spec-listed actions are accepted and ignored over the API, per the app bundle (not live-tested):
  `MusicPlayer_TempomarkerMoveGridLeft`, `MusicPlayer_TempomarkerMoveGridRight`, `MusicPlayer_TempomarkerIncreaseBpm`,
  `MusicPlayer_TempomarkerDecreaseBpm`. Lexicon logs `disabled control action` and returns 200.

### Added 2026-09-08 (Lexicon 1.11.14)

- `POST /v1/control` with `AudioAnalyzer_Analyze` and `analyzeWaveform: true` never replaces an existing waveform. In
  the app's analyzer, `doNotOverwrite` gates key, beatgrid, energy, and cuepoints only. The waveform step runs when the
  track's row in the `Waveform` table is missing, has `data` NULL, was saved under an older `waveformIteration` setting,
  or holds a truncated WebP; otherwise it is skipped. Live-tested with
  `{"trackIds":[20240],"analyzeWaveform":true,"analyzeKey":false,"analyzeBeatgrid":false,"analyzeEnergy":false,"doNotOverwrite":false}`:
  the response is `{}`, the app shows "Nothing to analyze: all 1 track were skipped", and the stored WebP is
  byte-identical afterwards. The Analyze dialog uses the same code path. Consequence: after an audio file is replaced in
  place, the stored waveform stays stale and the API cannot refresh it.
- `waveform` is a virtual, non-editable track field. `PATCH /v1/track` with `edits: {"waveform": null}` returns
  `{"message":"'waveform' is not editable, value: null","errorCode":5}` (live-tested).
- Within the app, the only way to discard a waveform is the Cleanup dialog (Help menu, "Cleanup"; hotkey action
  `Application_OpenCleanupDialog`, absent from the spec's Control Actions enum). Cleanup type "Waveforms" deletes the
  `Waveform` rows of the tracks selected in the track browser and reloads them without a restart; with no selection it
  deletes every waveform and restarts Lexicon. The next Analyze run with Waveform enabled, or loading the track in the
  player, regenerates the row. Confirmed in the UI on 1.11.14; the dialog was not driven over the API.
- Storage, for reference: `Waveform(trackId, data BLOB, previewCues TEXT, iteration INTEGER)` in `main.db`, one row per
  track, `ON DELETE CASCADE` from `Track`.

## Undocumented Fields in API Responses

- `GET /v1/track`
  - Returns payloads that include `cloudFileState`, `hasCuepoints`, and `hasTempomarkers`, which are not documented in
    the OpenAPI spec.
    - `hasCuepoints` and `hasTempomarkers` seem to always be `false` or `none` on newly added tracks, even after
      analysis completes and cuepoints/tempomarkers are present in the payload.
  - `tempomarkers` payloads include undocumented `trackId` field and an empty `data` dict.
  - `cuepoints` payloads include undocumented `trackId` field and an empty `data` dict.
- `GET /v1/tags`
  - Tag payloads include undocumented `shortcut` field.

## Undocumented Control Actions

`POST /v1/control` accepts any action the app's hotkey executor resolves, not only the enum in the spec. Found in the
Lexicon 1.11.13 bundle, not live-tested:

- `PluginRunActionByName` with parameters `pluginName` and `pluginActionName` runs a plugin action.
- `PluginRunAction_<pluginId>:<actionId>` runs a plugin action by id; the action string carries both ids.
- `Direct2Cdj_LoadDeck`, `Direct2Cdj_LoadEmptyDeck`, and `Direct2Cdj_LoadDeck1` through `Direct2Cdj_LoadDeck8` load
  tracks onto connected CDJs.

## Other Minor Documentation Issues

- `GET /search/tracks` just says to see the track schema but not all track fields are functional for filtering. It says
  "unknown keys will be dropped" which implies that all trach schema keys are valid.
  - `cuepoints` and `tempomarkers` tend to return errors if an attempt to filter on them is made
  - `id`, `type`, `locationUnique`, `incoming`, `archived`, `archivedSince`, `beatshiftCase`, `fingerprint`,
    `streamingService`, and `streamingId` seem to drop and will return all tracks.
