# Future Improvements

This document outlines potential enhancements organized by priority and scope.

---

## Near Future (High-Value, Lower Effort)

### 1. Post-API Filtering for Client-Side Search

**Problem**: Some simple track fields are ignored as server-side search filters (e.g., `archived`, `incoming`, `sizeBytes`). Date Fields can't use comparison filters. The fields that are arrays (`cuepoints`, `tempomarkers`) are also not accepted. `tags` is accepted with a custom comma separated string of tag names with `!` and `~` operators (e.g. `"~Rock, !Chill"` - Has tag `Rock` AND doesn't have tag `Chill`).

**Solution**: Post fetch filtering. For simple fields this is relatively easy. For cuepoints and tempomarkers some schema will have to be determined, or could be handled by lamdas?
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

**Implementation Location**: `src/lexicon/resources/tracks.py` (search method) or `src/lexicon/tools/tracks.py` (new helpers file)

---

### 2. Full Tracks List Download + Local Filtering (>1000 limit)

**Problem**: API caps search results at 1000; users need to filter larger libraries locally.

**Solution**: Offer option to download full tracks list and filter client-side. This is a natural extension of the post-API filtering in #1: if the API caps results or ignores a filter field, the same local filtering logic applies.

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

**Implementation Location**: `src/lexicon/client.py` (Lexicon.__init__ method)

---

### 4. Get Playlist by Name with Disambiguation

**Problem**: Users know playlist names but not IDs; need helper to find playlists by name.

**Solution**: Add name-based lookup with disambiguation for duplicates. When multiple matches exist, include the full playlist path in the disambiguation output (e.g., `ROOT > Genres > Drum & Bass`).

**Implementation Options**:

**Option A: Simple search helper**
```python
def get_by_name(self, name: str, strict: bool = False) -> int | list[tuple[int, str]] | None:
    """Find playlist ID(s) by name.
    
    Parameters
    ----------
    name : str
        Playlist name to search for.
    strict : bool
        If True, require exact match. If False, substring match.
    
    Returns
    -------
    int | list[tuple[int, str]] | None
        Single ID if exactly one match. If multiple matches, return a list
        of (id, path) tuples to disambiguate. None if no matches.
    """
    tree = self.list()
    matches = self._find_playlists_by_name(tree, name, exact=strict)
    
    if len(matches) == 1:
        return matches[0]["id"]
    elif len(matches) > 1:
        return [(p["id"], p["path"]) for p in matches]
    return None
```

**Option B: Interactive selection**
```python
def get_by_name_interactive(self, name: str) -> int | None:
    """Find playlist by name with interactive disambiguation."""
    matches = self._find_playlists_by_name(self.list(), name)
    
    if not matches:
        print(f"No playlists found matching '{name}'")
        return None
    
    if len(matches) == 1:
        return matches[0]["id"]
    
    # Multiple matches: use interactive chooser
    print(f"Found {len(matches)} playlists matching '{name}':")
    for i, p in enumerate(matches, 1):
        path = self.get_path_from_id(p["id"])
        print(f"  {i}. {' / '.join(path)}")
    
    choice = int(input("Select one (number): "))
    return matches[choice - 1]["id"] if 1 <= choice <= len(matches) else None
```

**Implementation Location**: `src/lexicon/resources/playlists.py` or `src/lexicon/tools/playlists.py`

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

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Post-API filtering (#1) | Medium | High | Medium |
| Full tracks download + local filtering (#2) | High | High | Medium |
| API version detection (#3) | Low | Low | Medium |
| Get playlist by name (#4) | Medium | High | Medium |
| Smartlist builder (#5) | High | High | Medium |
| Response caching (#6) | High | Medium | Low |
| Dataclass/Pydantic models (#7) | High | Medium | Low |

---

## Notes

- All features should maintain backward compatibility
- Add features as opt-in (e.g., `client_side_filters=True`, `model=Track`)
- Keep SDK lightweight; optional dependencies recommended for advanced features
- Document trade-offs (e.g., caching vs freshness, filtering vs performance)
