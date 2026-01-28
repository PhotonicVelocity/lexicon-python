# API/Docs Issues

## Incorrect or Incomplete OpenAPI Spec Documentation
- `POST /v1/tag` returns the tag object at the top level (no `data` wrapper), while the OpenAPI spec shows `{"data": {...}}`.
- `PATCH /v1/tag` returns the tag object at the top level (no `data` wrapper), while the OpenAPI spec shows `{"data": {...}}`.
- `POST /v1/tag-category` returns the category object at the top level (no `data` wrapper), while the OpenAPI spec shows `{"data": {...}}`.
- `PATCH /v1/tag-category` returns the category object at the top level (no `data` wrapper), while the OpenAPI spec shows `{"data": {...}}`.
- `DELETE /v1/track` returns `errorCode=4` (endpoint does not exist) in current Lexicon build, but OpenAPI spec documents it. `DELETE /v1/tracks` with JSON body `{"ids":[...]}` succeeds.
- `DELETE /v1/playlists` fails when `ids` are passed as query params per OpenAPI spec; JSON body `{"ids":[...]}` succeeds.
- `GET /v1/search/tracks` & `GET /v1/tracks` sort parameters only work when sent in the JSON body, not as URL query parameters, contrary to OpenAPI spec and website "Try it out" examples. Multiple formats were tested:
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
- `GET /v1/playlist-by-path` defaults `type` query parameter to `2`, but web documentation implies it is optional for all types and "might be useful" for disambiguation.
- `fileType` appears in the OpenAPI spec as a valid Track field, but it is not returned in `GET /v1/track` or `GET /v1/tracks`, and the API rejects `fields=fileType`.
- `GET /v1/search/tracks` drops comparison filters for date fields (`lastPlayed`, `dateAdded` and `dateModified`) when using  `>` or `<` operators (works in the Lexicon UI, not via API).
- `GET /v1/search/tracks` does not support filtering for tracks with no tags (`tags=NONE` returns all tracks instead of only untagged tracks).
- `GET /v1/playlist` can return duplicate `trackIds` when the playlist is a folder; clients may need to deduplicate.
- `Cuepoint` schema has undocumented `activeLoop` item.

## Undocumented Fields in API Responses
- `GET /v1/track` 
  - Returns payloads that include `cloudFileState`, `hasCuepoints`, and `hasTempomarkers`, which are not documented in the OpenAPI spec.
    - `hasCuepoints` and `hasTempomarkers` seem to always be `false` or `none` on newly added tracks, even after analysis completes and cuepoints/tempomarkers are present in the payload.
  - `tempomarkers` payloads include undocumented `trackId` field and an empty `data` dict.
  - `cuepoints` payloads include undocumented `trackId` field and an empty `data` dict.
- `GET /v1/tags`
  - Tag payloads include undocumented `shortcut` field.

## Other Minor Documentation Issues
- `GET /search/tracks` just says to see the track schema but not all track fields are functional for filtering. It says "unknown keys will be dropped" which implies that all trach schema keys are valid.
  - `cuepoints` and `tempomarkers` tend to return errors if an attempt to filter on them is made
  - `id`, `type`, `locationUnique`, `incoming`, `archived`, `archivedSince`, `beatshiftCase`, `fingerprint`, `streamingService`, and `streamingId` seem to drop and will return all tracks.
