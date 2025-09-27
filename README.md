# lexicon-python

A lightweight Python client for the [Lexicon DJ](https://www.lexicondj.com/) API.  It wraps the REST endpoints used for playlist browsing and track lookups, while staying simple enough to embed inside scripts or larger automation projects.

## Features

- Class `LexiconClient` with configurable host/port.
- All GET requests for Playlists, Tracks, and Tags available
- Handy helpers:
    - Interactive `choose_playlist` prompt for fast CLI workflows.
    - GET for all tracks can automatically retrieve all pages with `get_all`
    - Batch function `get_track_batch` can retrieve full metadata for a list of tracks (including progress bar
    for large retrievals)
- Minimal dependencies (`requests`, `tqdm`) and a pure-Python implementation suitable for scripts or larger apps.

## Quickstart

1. Create a virtual environment and install requirements:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the example script (ensure your Lexicon instance is reachable):

   ```bash
   python examples/demo_lexicon.py
   ```

   The script prompts you to choose a playlist, then fetches metadata for the first five tracks.

## Usage

```python
from lexicon import LexiconClient

lexicon = LexiconClient()

# Choose playlist interactively and fetch it's tracks
selection = lexicon.choose_playlist(show_counts=True)
if selection:
    path, playlist = selection
    print("Selected:", " / ".join(path))
    track_ids = set(playlist.get("trackIds", []))
    print("Tracks reported: ", len(track_ids))

    tracks = lexicon.get_track_batch(track_ids, max_workers=5)
    for track in tracks:
        print(track["title"], "-", track["artist"])
else:
    print("No playlist selected.")

# Fetch the complete library in chunks of 250
tracks = lexicon.get_tracks(limit=250, get_all=True) or []
print(f"Fetched {len(tracks)} tracks")

# Search within your library
results = lexicon.search_tracks({"artist": "Daft Punk", "bpm": ">=120"}) or []
print(f"Found {len(results)} matching tracks")

# Inspect tags and categories
tags_payload = lexicon.get_tags()
    if tags_payload:
        for category in tags_payload["categories"]:
            print("Category:", category["label"])
            for tag_id in category["tags"]:
                tag = next((t for t in tags_payload["tags"] if t["id"] == tag_id), None)
                print("->", tag["label"])
```

See `examples/demo_lexicon.py` for a more complete walkthrough.

## Development

- Run the test suite: `PYTHONPATH=src python -m unittest discover -s tests`
- Style: keep the package pure Python, logging via `logging.getLogger(__name__)`, and prefer small, testable helpers.
- Packaging metadata lives in `pyproject.toml` (see below).

Contributions welcome—open an issue or PR with ideas!
