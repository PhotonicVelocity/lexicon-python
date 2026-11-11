# Future Improvements

This document outlines potential enhancements organized by priority and scope.

---

## Near Future (High-Value, Lower Effort)

### 1. Post-API Filtering for Client-Side Search

**Problem**: Some simple track fields cannot be server-side search filters (e.g., `archived`, `incoming`; Lexicon v1.12
rejects them with a 400, v1.11 ignored them). Date Fields can't use comparison filters. The fields that are arrays
(`cuepoints`, `tempomarkers`) are also not accepted. `tags` is accepted with a custom comma separated string of tag
names with `!` and `~` operators (e.g. `"~Rock, !Chill"` - Has tag `Rock` AND doesn't have tag `Chill`).

**Solution**: Post fetch filtering. For simple fields this is relatively easy. For cuepoints and tempomarkers some
schema will have to be determined, or could be handled by lamdas?

- Cuepoints ideas:
  - Filter on number of cuepoints
  - Filter on cuepoints with a name
  - Filter on cuepoints colors
- Tempomarker ideas:
  - Filter on number of tempomarkers

**Implementation Options**:

```python
# Option A: Filter at method level with optional flag
# - Method runs post-api filtering on input fields when true
tracks = lex.tracks.search(
    {"artist": "Daft Punk", "incoming": True},  # incoming ignored by API
    client_side_filter=True
)

# Option B: Post-filter helper function
# - User would need to select fields not searchable by api by comparing to FILTER_FIELDS
tracks = lex.tracks.search({"artist": "Daft Punk"})
filtered = lex.tracks.filter_results(tracks, {"incoming": True, "cuepoints": lambda cp: len(cp) > 0})

```

**Implementation Location**: `src/lexicon/resources/tracks.py` (search method) or `src/lexicon/tools/tracks.py` (new
helpers file)

---

### 2. Full Tracks List Download + Local Filtering (>1000 limit)

**Problem**: API caps search results at 1000; users need to filter larger libraries locally.

**Solution**: Offer option to download full tracks list and filter client-side. This is a natural extension of the
post-API filtering in #1: if the API caps results or ignores a filter field, the same local filtering logic applies.

**Implementation Strategy**:

```python
def search(self, filter: dict, *,
           client_side_filter: bool = False,
           **kwargs) -> list[TrackResponse] | None:
    """Search tracks, optionally filtering client-side for larger results.

    Parameters
    ----------
    client_side_filter : bool
        If True and search would exceed 1000 results, download full library
        and filter locally. Much slower but complete.
    """

    # First, try server-side
    results = self._search_api(filter, **kwargs)

    if not client_side_filter or len(results) < 1000:
        return results

    # Need client-side filtering
    self._logger.warning("Search returned 1000 results; downloading full library for local filtering...")
    all_tracks = self.list(limit=None)  # Get all tracks

    # Apply filter locally (same helper as #1)
    filtered = self._apply_filter_locally(all_tracks, filter)
    return filtered

def _apply_filter_locally(self, tracks: list, filter_dict: dict) -> list:
    """Apply search filter logic locally to track list."""
    results = []

    for track in tracks:
        match = True
        for field, value in filter_dict.items():
            track_value = track.get(field)

            # Handle different filter types
            if isinstance(value, str):
                if value.lower() not in str(track_value).lower():
                    match = False
                    break
            elif isinstance(value, (int, float)):
                # For numeric: exact match or range?
                if track_value != value:
                    match = False
                    break
            elif isinstance(value, list):
                # For lists: any or all?
                if not any(item in track_value for item in value):
                    match = False
                    break

        if match:
            results.append(track)

    return results
```

**Caveats**:

- Full library download can be slow (1000s of tracks)
- Filter logic must replicate API behavior exactly
- Some filters may not be replicable (e.g., complex range queries)

**Implementation Location**: `src/lexicon/resources/tracks.py` (search method)

---

### 3. API Version Detection & Compatibility

**Problem**: SDK might break if Lexicon API schema changes; users don't know which version they're using.

**Solution**: Detect and cache API version on client init. Warn if SDK might need updating.

**Implementation Options**:

**Option A: Query API version endpoint (if available)**

```python
def _detect_api_version(self) -> str:
    """Query /v1/version or similar endpoint."""
    try:
        response = self.request("GET", "/v1/version")
        return response.get("version", "unknown")
    except:
        return "unknown"

# Usage
lex = Lexicon()
print(lex.api_version)  # "2.5.1"
```

**Option B: Fetch and cache OpenAPI schema**

```python
def _fetch_openapi_schema(self) -> dict:
    """Download OpenAPI schema from Lexicon instance."""
    try:
        response = self.request("GET", "/openapi.yaml")  # or /openapi.json
        # Parse YAML/JSON
        return schema
    except:
        return {}

lex = Lexicon()
schema_version = lex.openapi_schema.get("info", {}).get("version")
```

**Option C: Version header in responses**

```python
# Check if response includes version header
def request(...):
    response = requester.request(...)
    api_version = response.headers.get("X-Lexicon-Version")
    if api_version and api_version != self.cached_version:
        self._logger.warning(f"API version mismatch: {self.cached_version} vs {api_version}")
```

**Implementation Location**: `src/lexicon/client.py` (Lexicon.**init** method)

---

### 4. Update-Payload Constructor Helpers

**Problem**: Update operations take `TypedDict` payloads (`TempoMarkerUpdate`, `CuePointUpdate`, etc.). Today callers
either build dict literals plus a type annotation:

```python
from lexicon import TempoMarkerUpdate
markers: list[TempoMarkerUpdate] = [
    {"startTime": float(s), "bpm": float(b)} for s, b in segments
]
```

…or skip the annotation and lose type-checker coverage. Repetitive `float(...)` casts and dict literals at every
construction site are friction; for `TypedDict`s with many optional fields, dict literals are also hard to discover via
autocomplete.

**Solution**: Constructor helpers, namespaced under `lexicon.types` (or similar):

```python
from lexicon.types import tempomarker, cuepoint

markers = [tempomarker(s, b) for s, b in segments]
cues = [
    cuepoint(start_time=0.0, name="Intro", color=Color.GREEN),
    cuepoint(start_time=16.0, name="Verse"),
]
```

The helpers handle casting (`float(s)`), apply defaults, and return the matching `TypedDict`. Callers drop the explicit
annotation; type inference flows from the helper's return type.

**Tradeoffs**:

- Wins compound at sites that construct many payloads or have many optional fields; sites that construct a single short
  literal barely benefit.
- Two ways to do it (raw dict vs helper) — needs clear guidance on which pattern is canonical.
- Each helper has to track its `TypedDict` if fields change. Consider property-based / round-trip tests pinning helper
  output to the type shape.

**When it earns its keep**: a `TypedDict` with 8+ optional fields, or one with runtime validation needs (range checks,
mutual-exclusion). For flat 2-field shapes like `TempoMarkerUpdate`, the type-alias-plus-literal pattern is fine on its
own.

**Implementation Location**: new `src/lexicon/types.py` (or `src/lexicon/builders.py`) re-exported from the top-level
package alongside the existing `TempoMarkerUpdate` / `CuePointUpdate` types.

---

### 9. Probe + Document Non-GET Endpoint Return Shapes

**Problem**: lex-py methods that mutate state (PATCH/POST/DELETE) often re-fetch the full object after the mutation to
return a complete shape to callers. The trailing GET is conservative — written before the actual return shape of each
mutation endpoint was fully understood. In some cases the mutation endpoint already returns enough data to skip the
re-fetch entirely; in others it returns a minimal `{id, edits}` shape that genuinely needs the follow-up GET.

The canonical example is `tracks.update_tempogrid(...)`:

1. `GET /v1/track?id=...` — current track (for cuepoint-beat preservation).
2. `PATCH /v1/track` — apply the update.
3. `GET /v1/track?id=...` — fetch the updated track to return.

For callers that only need `dateModified` and `tempomarkers` (e.g. a sync trigger), step 3 is unnecessary if the PATCH
response already carries those fields. On Lexicon v1.12 it does: `PATCH /v1/track` returns the stored track, and
`tracks.update()` (so `update_tempogrid()` too) now returns it without step 3. The other endpoints' v1.12 shapes are in
`docs/api-issues.md` ("Added 2026-11-11"); `playlists.update()` still re-fetches because `PATCH /v1/playlist` returns
only the id.

Other affected methods include `tracks.update()`, `tracks.add()`, `playlists.{create, update, delete}`,
`cue_points.{add, remove}`, and the tag/category mutation methods. Note 8 ("Validate Update Responses Before Re-Fetch")
flags that the PATCH response shape _already varies_ (tag edits return `{}`; other edits return `{id, edits}`); that
variability makes the systematic probe more valuable, not less.

**Solution**: A two-phase pass.

1. **Probe.** Hit each non-GET endpoint against a live Lexicon and capture the response body. Document the shape per
   endpoint (`docs/non-get-return-shapes.md` or as a section in `docs/api-issues.md`). Useful even on its own — we don't
   currently have this written down.
2. **Method audit.** For each lex-py method that does an extra GET after a mutation, decide:
   - **Drop the GET** — if the mutation response is rich enough on its own, return it directly. Breaking change to
     method return shape; callers who relied on the post-fetch full record need notice.
   - **Opt-in flag** — `return_full=True` (default) preserves today's behavior; `return_full=False` returns the mutation
     response directly. Backwards compatible, opt-in optimization.
   - **`_fast` variant** — separate method (`update_tempogrid_fast()`) for callers that don't need the full record.
     Bigger surface, but keeps the canonical method's contract stable.

The first option is cleanest if the shape is uniformly rich; the second is cleanest if some callers need the full record
post-mutation; the third is appropriate if the canonical method's contract is widely relied on.

**When it earns its keep**: hot paths in client code that mutate often and don't need the full re-fetch (e.g. a sync
trigger that pushes after every edit pays a 33% HTTP overhead for a trailing GET it never uses).

**Coordination with note 8**: probe + method audit naturally feed into the validation work. Once we have the shape per
endpoint documented, "validate edits before re-fetch" becomes "validate edits and _also_ decide whether re-fetch is
needed at all."

**Implementation Location**: `docs/api-issues.md` (or new `docs/non-get-return-shapes.md`) for the probe artifacts;
`src/lexicon/resources/tracks.py`, `playlists.py`, `cue_points.py` for the method-level changes.

---

## Far Future (Significant Effort, Strategic Value)

### 5. Smartlist Builder Helper

**Problem**: Smartlists require complex nested dicts; hard to build correctly.

**Solution**: Fluent builder API for smartlists.

**Example API Design**:

```python
# Build a smartlist: "Artist = 'Daft Punk' AND BPM >= 120"
smartlist = (
    SmartlistBuilder()
    .add_rule("artist", "is", "Daft Punk")
    .add_rule("bpm", ">=", 120)
    .match_all()  # AND logic
    .build()
)

playlist = lex.playlists.add(
    "High-Energy Daft Punk",
    playlist_type=3,
    smartlist=smartlist
)

# Generated payload:
# {
#   "matchType": "all",
#   "rules": [
#     {"field": "artist", "operator": "is", "value": "Daft Punk"},
#     {"field": "bpm", "operator": ">=", "value": 120}
#   ]
# }
```

**Implementation Location**: `src/lexicon/tools/smartlists.py` (new file)

---

### 6. Response Caching Layer

**Problem**: Frequent API calls for same data; Lexicon is local but still adds latency.

**Solution**: Optional built-in caching with TTL and invalidation.

**Design**:

```python
lex = Lexicon(
    host="localhost",
    cache_ttl=300,  # 5 minutes
    cache_size=1000  # entries
)

# Auto-cached (first call fetches, subsequent calls within 300s use cache)
track1 = lex.tracks.get(123)
track2 = lex.tracks.get(123)  # Cached

# Manual cache control
lex.cache.clear()
lex.cache.invalidate("track:123")
lex.cache.set_ttl("playlist", 60)
```

**Implementation**: LRU cache with TTL per resource type

**Implementation Location**: `src/lexicon/cache.py` (new file) + `src/lexicon/client.py` (integration)

---

### 7. Dataclass/Pydantic Models Layer (Optional)

**Problem**: Raw dicts are flexible but lack IDE support and validation; some users want type safety.

**Solution**: Offer optional Pydantic models as convenience layer.

**Design** (with optional dependency):

```python
# Without Pydantic (default)
track = lex.tracks.get(123)  # dict
print(track["title"])

# With Pydantic (optional)
from lexicon.models import Track

track = lex.tracks.get(123, model=Track)  # Track instance
print(track.title)  # IDE autocomplete, validation

# Or wrapper function
track = Track.from_api(lex.tracks.get(123))
```

**Trade-offs**:

- ✅ Better IDE support, validation, documentation
- ❌ Extra dependency, slightly slower serialization
- ✅ Can be entirely optional (no breaking changes)

**Implementation Location**: `src/lexicon/models/` (new directory, optional)

---

## Implementation Priority Matrix

| Feature                                     | Effort | Impact | Priority |
| ------------------------------------------- | ------ | ------ | -------- |
| Post-API filtering (#1)                     | Medium | High   | Medium   |
| Full tracks download + local filtering (#2) | High   | High   | Medium   |
| API version detection (#3)                  | Low    | Low    | Medium   |
| Get playlist by name (#4)                   | Medium | High   | Medium   |
| Smartlist builder (#5)                      | High   | High   | Medium   |
| Response caching (#6)                       | High   | Medium | Low      |
| Dataclass/Pydantic models (#7)              | High   | Medium | Low      |
| Lexicon v1.12 follow-ups (#16)              | Medium | Medium | Medium   |

---

### 8. Validate Update Responses Before Re-Fetch

**Problem**: `playlists.update()` re-fetches the playlist after a PATCH, and neither it nor `tracks.update()` verifies
that the API applied the edits. On Lexicon v1.12, `PATCH /v1/track` returns the stored track and `tracks.update()`
returns it without a re-fetch, so a check could compare the edits with that track directly.

**Solution**: Compare the `edits` echoed back in the PATCH response (e.g.
`{"id": 1, "edits": {"title": "My New Title"}}`) against what was sent. Warn or raise if they don't match before
re-fetching.

**Note**: The PATCH response shape varies by edit type — tag edits return `{}` (empty dict) with no ID or edits echo.
Other edit types may also return empty responses. The validation logic needs to account for this, and should not treat
an empty response as a failure.

**Implementation Location**: `src/lexicon/resources/tracks.py`, `src/lexicon/resources/playlists.py`

---

### 11. Position Reorder Helpers (Lexicon v1.11 only)

Lexicon v1.12 made this unnecessary: `playlists.update(position=)` inserts and shifts the other playlists,
`tags.categories.update(tags=[...])` sets a category's whole tag order, and `tags.categories.update(position=)` moves a
category. What remains is v1.11, where tag positions reject collisions (code `108`), playlist positions overlap, and
categories have no position. Only worth doing if v1.11 support lasts.

---

### 10. `[interactive]` Package Extra + `choose_playlist` Docstring

**Problem**: `lexicon.tools.playlists.choose_playlist()` imports InquirerPy lazily inside the function and raises a
`RuntimeError` at call time if it's missing:

```python
try:
    from InquirerPy.resolver import prompt
except ImportError as exc:
    raise RuntimeError("InquirerPy is required for choose_playlist.") from exc
```

InquirerPy is not a runtime dependency of `lexicon-python` itself, which is correct (it's a heavy TTY dep most users
don't need). But:

1. The `choose_playlist` docstring doesn't call out the InquirerPy requirement, so callers only discover it when they
   run the interactive picker for the first time.
2. There's no `pip install lexicon-python[interactive]` extra — users have to `pip install InquirerPy` separately and
   know to do so.

**Solution**: Two small fixes, both surface-level:

1. **Add an `interactive` extra to `pyproject.toml`** under `[project.optional-dependencies]`, pinning InquirerPy at the
   version the picker code was written against. Callers who want the picker do `pip install lexicon-python[interactive]`
   (or `uv add lexicon-python --extra interactive`) — one command, no version-guessing.
2. **Update the `choose_playlist` docstring** to mention the requirement and point at the extra. IDE tooltips + `help()`
   then surface it upfront rather than at first `RuntimeError`.

**When it earns its keep**: any downstream consumer that ships the interactive picker as a documented feature, such as a
CLI that lets the user pick a playlist. Also a small polish win for `help(lex.tools.playlists.choose_playlist)`.

**Implementation Location**: `pyproject.toml` (`[project.optional-dependencies]`), `src/lexicon/tools/playlists.py`
(docstring of `choose_playlist`).

---

### 14. `update_tempogrid` Preserves Cue Beats; Offer a Plain Time Shift

**Problem**: `tracks.update_tempogrid()` reads the current track, converts every cuepoint's `startTime` (and `endTime`)
to beats under the old grid, and writes them back as seconds under the new grid. That contract is implicit: the
docstring says the grid is replaced, and a caller finds out about the cue rewrite by reading the code. It is the right
behavior when the audio is unchanged and the grid was re-detected. It is a different operation from the other common
edit, a time shift: the audio file was replaced (a re-rip with different leading silence, an encoder-delay correction, a
trimmed intro) and every marker and cue must move by the same number of seconds. For a uniform shift the beat math
happens to give the same answer, because beats are preserved when every segment moves together, but it does so through
float beat conversions and three HTTP calls, and a caller who shifts the cues themselves before calling it moves them
twice. For a re-rip replacement the simpler path is one `tracks.update()` with both lists shifted, which is the raw
replacement the README already recommends for this case.

**Solution**: two small changes.

1. State the contract in the docstring and README: cue beat positions are preserved; seconds change whenever the grid
   changes; use `tracks.update()` for raw replacement.
2. Add `tracks.shift_grid(track_id, offset_seconds)` (or a `preserve="beats" | "seconds"` argument on
   `update_tempogrid`) that adds a constant to every tempomarker `startTime` and every cuepoint `startTime`/`endTime`
   and refuses, rather than clamps, a result below 0. One GET, one PATCH.

While there, check the edge cases of the beat path: a cue earlier than the first marker (negative beats under the first
segment's bpm), a cue past the last marker after the marker count changed, and rounding through beats for cues that were
placed exactly on a marker.

**Implementation Location**: `src/lexicon/resources/tracks.py` (`update_tempogrid`, new `shift_grid`),
`src/lexicon/tools/tempo.py`, README section on tempo grids.

## Notes

- All features should maintain backward compatibility
- Add features as opt-in (e.g., `client_side_filters=True`, `model=Track`)
- Keep SDK lightweight; optional dependencies recommended for advanced features
- Document trade-offs (e.g., caching vs freshness, filtering vs performance)

---

---

### 16. Follow-ups From Lexicon v1.12 Support

Left open when v1.12 support landed (2026-11-11):

1. **Batch track lookups with `filter.id`.** `tracks.get_many()` and `playlists.tracks.get()` fetch one track per
   request, or the whole library above a 5% cutoff. On v1.12 one `tracks.search({"id": ids})` per 1000 IDs does the
   same; v1.11 needs the current path, and `search()` already detects a v1.11 that ignored the filter.
2. **All tracks from `update("selected")`.** The response's `data.tracks` holds every edited track, but `update()`
   returns `data.track`, the first one. An `update_selected()` returning the list would expose it.
3. **Control actions found only in the app bundle.** `GhostCurator_*`, `Appearance_ZoomReset`, `Incoming_AllDone`,
   `MusicPlayer_MetronomeSettings`, and `Navigation_SyncMobileApp` are in the 1.12.0 hotkey enum but not the spec. Test
   them against an empty library before adding them to `ControlAction`.
4. **Cue `activeLoop` as a boolean on v1.11.** The client now sends `true`/`false`, which v1.12 requires. v1.11.15
   accepted `0`/`1`; booleans were not tested there.
5. **Storing tokens.** The client keeps `lex.token` in memory and leaves storage to the caller. A helper that saves it
   per host and app name (keyring or a config file) would make remote use easier.
6. **Dropping v1.11.** The fallbacks (re-fetch after `PATCH /v1/track`, the `id` filter check, the paging retry, the
   `Direct2Cdj_*` names) can go once v1.11 support ends.
