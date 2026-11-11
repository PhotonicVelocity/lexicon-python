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

### Added 2026-11-04 (Lexicon 1.11.15)

- `GET /v1/playing` after an eject returns `{"data":{"track":null,"progress":0,"currentTime":0.976}}`, where the spec
  says all three are `null` (live-tested). `currentTime` keeps the position from before the eject, so check `track`
  rather than `currentTime`. The handler falls back to `null` for `progress` and `currentTime` when the player object
  does not exist; not live-tested.
- `GET /v1/playing` returns the loaded track while paused, despite the spec's "currently playing". `currentTime` held at
  19.81 across two reads (live-tested). The response has no play state field.
- `data.track` is not always the spec's `Track`. The handler returns `musicPlayer.track ?? musicPlayer.remoteTrack`. A
  library track has the same fields as `GET /v1/track` plus `releaseDate` (live-tested). A Beatport track gives this
  shape (live-tested):
  `{"headers":null,"url":"https://geo-samples.beatport.com/track/<uuid>.LOFI.mp3","streamingService":"0","title":...,"artist":"Chase & Status, Skrillex","id":30520465,"imageUrl":...,"bpm":88,"duration":57.27,"key":"12M"}`
  - `id` is Beatport's track ID, not a library ID, and `GET /v1/track` with it returns `TrackNotExist`. Beatport's API
    returned the same title, artists, BPM, and `sample_url` for that ID.
  - `duration` is the preview length: `sample_end_ms` minus `sample_start_ms`, 57.27 s on a 166.27 s track.
  - `title` has no mix name. `type` and `streamingId` are absent.
  - `key` depends on where the track was loaded from. Loaded from a library row, it carries the row's key; loaded from
    the Beatport tab, the field is absent, because the tab's builder never sets it (live-tested on Beatport ID 30274307:
    `"12M"` from the row, absent from the tab). `imageUrl` differs the same way, 1400x1400 from the row and 500x500 from
    the tab.
  - A Beatport library row is swapped for a remote track at load, so the response loses the library ID (live-tested: row
    21130, `id` 30274307). The row has `type` `"1"`, `streamingId` `"30274307"`, `mix` `"Original Mix"`, `location`
    `beatport:/tracks/30274307`, and the full `duration` 237.241. The player still reports the 120 s preview, at the
    same `url` as the Beatport tab.
  - Per the app bundle, not live-tested: Apple Music and Spotify rows are swapped the same way. SoundCloud rows stay a
    `Track`, with the library ID in `id`. Beatsource, Tidal, Deezer, and iTunes rows are refused at load with a "not yet
    supported" alert. `id` takes the service's type: an int for Beatport, a string for Spotify.
- A file loaded from outside the library is held as an `ExternalTrack`, which sets neither `track` nor `remoteTrack`, so
  `data.track` is `null` while it plays. Read from the app bundle; not live-tested.
- The spec's `streamingService` enum stops at `3`. The app defines `0` Beatport LINK, `1` Beatsource LINK, `2`
  SoundCloud, `3` Tidal, `4` Spotify, `5` Deezer, `6` Apple Music, `7` iTunes.

### Spec published 2026-11-01 (Lexicon v1.12, not released)

The spec at lexicondj.com was rewritten on 2026-11-01. It describes v1.12, while the newest release then was 1.11.15
(changelog entry 2026-10-15). v1.12.0 shipped on 2026-11-11; see the next section for what it does.

In the spec but not in 1.11.15 (live-tested on 1.11.15 unless noted):

- `GET /v1/tracks/selected` and `GET /v1/playlists/selected` return error code 4.
- `PATCH /v1/track/location` is not in the app's route table (app bundle; not live-tested).
- `GET /v1/track?id=selected` returns `'id' must be a number`.
- `limit` and `offset` on `GET /v1/search/tracks` return `'limit' is not allowed`.
- `filter.fileType` returns `'filter.fileType' is not allowed`.
- `filter.id` is ignored: `{"id":"499"}` and `{"id":"499,500"}` each returned all 8257 tracks. Do not send it to
  1.11.15.
- `filter.tags` with `none` returned 0 tracks; the spec says it finds tracks without tags.
- `Navigation_SidebarDashboard` and the nine `Playlists_*` control actions are absent from the app bundle, so
  `POST /v1/control` should reject them with error code 5 (not live-tested).
- Bearer token authentication, which the spec marks "Starting in Lexicon v1.12".

Search filter behavior on 1.11.15 (live-tested, library of 8257 tracks, 5 added on 2026-11-04):

- `filter.importSource` is ignored and returned all 8257 tracks. It is not in the spec's filterable list.
- `filter.sizeBytes` works and is in MB. `{"sizeBytes":">100"}` returned 35 tracks.
- `filter.bpm` accepts `120~121`, which the spec defines as stopping before the upper bound.
- Date operators: `>2026-11-04` and `>=2026-11-04` both returned the 5 tracks from that day. `<2026-11-04` and
  `<=2026-11-04` both returned the other 8252, so `<=` leaves that day out.
- A JSON body on a GET still works: the server merges it over the query string, and the spec describes both forms for
  `sort`.
- `filter.id` sent as a number makes the handler throw, and the response is HTTP 200 with only
  `{"message":"h[r].trim is not a function"}`. The shared handler copies `code` from whatever was thrown and only fails
  the request when that is set, so any uncoded error on any route looks like this. The spec's error code `8` (HTTP 500)
  is meant to replace it.

Corrected in this spec; the earlier entries above describe older specs:

- `GET /v1/playing` documents `currentTime` instead of `seconds`.
- `AudioAnalyzer_Analyze` replaces `TrackBrowser_AnalyzeStart`.
- `DELETE` for tracks moved to `/v1/tracks`, and `DELETE /v1/playlists` takes `ids` in the JSON body.
- `MusicPlayer_Load` documents its `id` parameter, and `Application_SetColor`, `Application_SetEnergy`,
  `Application_SetDanceability`, `Application_SetPopularity`, and `Application_SetHappiness` are in the enum.
- The four hotkey-only `MusicPlayer_Tempomarker*` actions are out of the enum and documented as doing nothing.
- `PluginRunActionByName`, `PluginRunAction_<pluginId>:<actionId>`, and `Direct2Cdj_*` are documented.

### Added 2026-11-11 (Lexicon 1.12.0)

v1.12.0 shipped on 2026-11-11. `docs/lexicon-api-docs.yaml` holds the spec published 2026-11-09, which differs from the
2026-11-01 one only by `POST /v1/auth/pair`, the `bearerAuth` wording, and error codes `10` to `12`. The results below
were live-tested on 1.12.0 (macOS) unless noted. Writes ran against an emptied library.

Authentication:

- A request from an app that was already allowed, sent from the same computer with only `X-Lexicon-App` and no token, is
  let in (HTTP 200). The spec's error code `11` says such a request is refused with 409; the web page says local apps
  are let in by name after approval. The web page matches 1.12.0. Not tested from another device, where the page says
  the token is always required.
- A request with an `Origin` header is answered at once with 401 and error code `9`, without a popup. The integration
  harness relies on this to check whether the API is up.
- A token in the query string is ignored (401, code `9`, with an `Origin` header). The page says tokens only work in the
  `Authorization` header.
- `POST /v1/auth/pair` returned the token in `data.token` 2.8 s after the user clicked Allow. The `X-Lexicon-Token`
  response header was present.
- Approvals are not stored in `main.db`: after `main.db` was replaced with an empty library, the paired token and the
  name-only request were both still let in.
- Without `X-Lexicon-App`, Lexicon names the app after the `User-Agent` product, so every `requests` script was the app
  "python-requests". The client now always sends `X-Lexicon-App`.

Control actions:

- `Direct2Cdj_LoadDeck` is rejected with `Unknown control action` (code `5`), and `DeckConnect_LoadDeck` is accepted.
  Lexicon 1.12 renamed DIRECT2CDJ to DeckConnect. The spec published 2026-11-09 still lists the ten `Direct2Cdj_*`
  names; the 1.12.0 hotkey enum has `DeckConnect_LoadDeck`, `DeckConnect_LoadEmptyDeck`, and `DeckConnect_LoadDeck1` to
  `DeckConnect_LoadDeck8` instead. `ControlAction` lists both.
- The 1.12.0 hotkey enum has actions the spec does not list (app bundle; not live-tested): `Appearance_ZoomReset`,
  `GhostCurator_RollDice`, `GhostCurator_ToggleFollow`, `GhostCurator_ToggleOverlay`, `GhostCurator_UseSuggestion1` to
  `3`, `Incoming_AllDone`, `MusicPlayer_MetronomeSettings`, and `Navigation_SyncMobileApp`. `ControlAction` leaves them
  out until they are tested; send them with `validation="off"`.
- `Navigation_SidebarDashboard` is accepted. `POST /v1/control` answers `{}` on success.

Track edits (`PATCH /v1/track`):

- The response is `{"data": {"track": {...}}}`, the track as stored after the edit, including relative edits
  (`playCount: "+2"` came back as 2). This replaces the 1.11 shapes `{"id": ..., "edits": ...}` and `{}` listed above.
- A cue point's `activeLoop` must be a JSON boolean: `0` is rejected with
  `'cuepoints' cue point 0 activeLoop must be true or false` (code `5`) and nothing is written. 1.11.15 accepted `0` and
  `1`. A cue sent without `activeLoop` is stored as NULL and read back as `false` (seen from another client; not
  re-tested here).
- Every cuepoint edit replaces all cues, and every cue gets a new `id`. A cue or tempo marker sent without `data` is
  stored with `data: null`, so an edit that does not send `data` back erases what a DJ app import stored there (for
  example `{"traktor": {"displayOrder": 0, "originalType": "1", "repeats": -1}}`). A cue sent with `data` keeps it.
- Two cues with the same `position` are accepted with HTTP 200, and only one is stored.
- A cue `type` sent as the number `1` is rejected (`type must be one of 1, 2, 3, 4, 5`); the string `"1"` works.
  `startTime` sent as an int is accepted. A loop (`type` `"5"`) without `endTime` is rejected.
- Two tempo markers with the same `startTime` are rejected (`startTime 1 is used by another tempo marker`).
- `tempomarkers` and `cuepoints` in one edit work in either order.
- An unknown field is rejected (`'bogus' is not a valid track field`), a number field sent as a boolean is rejected
  (`'energy' must be null or a number`), and `dateAdded` is not editable.
- `archived` and `incoming` accept `0`/`1` and `true`/`false`. Track responses return them as `0`/`1`, except
  `POST /v1/tracks`, which returns `true`/`false`. Setting `archived` sets `archivedSince`.
- `color: null` is stored as an empty string (`"color": ""` in the response); `year: null` reads back as `0`.
- `id` sent as a numeric string (`"2"`) is accepted. `id: "selected"` with nothing selected fails with code `113`.
- `DELETE /v1/track` (singular) still returns code `4`; `DELETE /v1/tracks` works.

`PATCH /v1/track/location`:

- Returns `{"data": {"track": {...}}}`. The location is normalized: on macOS `/private/tmp/x.wav` is stored as
  `/Volumes/Macintosh HD/private/tmp/x.wav`, and the relative path `relative.wav` became
  `/Volumes/Macintosh HD/relative.wav`.
- Another track's location fails with code `110`, a missing file with `111` (the message suggests
  `checkFileExists: false`, which then succeeds), and an unknown track with `100`.

Search (`GET /v1/search/tracks`), live-tested against a library of 9035 tracks:

- `limit` and `offset` page the results; `total` is the full match count. With no `limit` the page is 1000. A `limit`
  above 1000 is rejected.
- A field that cannot be filtered is rejected: `'filter.bogus' is not allowed`. `importSource` and `archived` are
  rejected the same way.
- `filter.id` works as a number (`499`) or a string (`"499"`, `"12,48,153"`); an unknown id matches nothing.
- `filter.fileType` matches the extension ignoring case (`WAV` finds `.wav` files). `fields` does not accept `fileType`
  and tracks do not return it.
- `filter.tags` `"none"` finds tracks without tags (728 of 9035).
- `none` on `bpm` matched 0 tracks while `"0"` matched 1, and `none` on `year` matched 0 while `"0"` matched 903, so the
  client keeps sending `"0"` for a number filter of `None`. The spec says `none` works on `bpm`.
- A JSON `null` filter value (`{"artist": null}`) is ignored and matches the whole library. The client turns `None` into
  `"NONE"`/`"0"`/`"none"` unless `validation="off"`.
- Dates: `<=2026-11-01` and `<2026-11-01` both matched 8159 tracks, so `<=` still leaves that day out, as on 1.11.15.
- `sort` works in the query string as URL-encoded JSON and in bracket form, and a sort without `dir` no longer crashes.

Playlists, tags, player:

- `PATCH /v1/playlist` with `position` inserts: moving the third of three playlists to `0` gave positions `0, 1, 2` in
  the new order. The response is still `{"data": {"id": ...}}`.
- `GET /v1/playlist` on a folder lists each track once. Changing or deleting the root folder fails with code `112`.
- Adding a track that is already in a playlist with `PATCH /v1/playlist-tracks` returns `{}` and does not add it again.
  Adding tracks to a folder fails with code `104`.
- `PATCH /v1/tag-category` with `tags` reorders the category and moves tags in from other categories. Leaving out a tag
  the category has fails with code `5` and an unknown tag with `109`. `position` moves the category and renumbers the
  others. `color: null` is rejected (`'color' must be a string`).
- `PATCH /v1/tag` with a `position` another tag has still fails with code `108`.
- `POST`/`PATCH` for tags and categories still return the object at the top level, which the spec now documents.
- `GET /v1/tracks/selected` and `GET /v1/playlists/selected` return `{"data": {"ids": [...]}}`.
- `GET /v1/playing` after an eject still returns the old `currentTime` with `track: null`. For a library track it now
  also returns `releaseDate` and `waveform`, which `GET /v1/track` does not.
- `POST /v1/tracks` returns tracks with `cloudFileState`, `hasCuepoints`, and `hasTempomarkers`, and without `data`,
  `extra1`, `extra2`, and several other fields that `GET /v1/track` returns.

Fixed in 1.12.0 (entries above that no longer apply): `sort` in the query string, a sort without `dir`, duplicate
`trackIds` for a folder, overlapping playlist positions, the non-functional `tags` on `PATCH /v1/tag-category`, no way
to find untagged tracks with `filter.tags`, and ignored filter fields returning the whole library. Not re-tested: the
HTTP 200 answer with only a `message` for an error without a code, which the spec's code `8` is meant to replace.

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
