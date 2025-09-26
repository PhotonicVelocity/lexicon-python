# lexicon-python

A lightweight Python client for the [Lexicon DJ](https://www.lexicondj.com/) API.  It wraps the REST endpoints used for playlist browsing and track lookups, while staying simple enough to embed inside scripts or larger automation projects.

## Features

- `LexiconClient` with configurable host/port.
- Helpers for fetching playlists (by tree, id, or path) with safe JSON handling.
- Interactive `choose_playlist` prompt for quick CLI workflows.
- Batched track metadata retrieval with optional parallelism.
- Pure-Python implementation with minimal runtime dependencies (`requests`, `tqdm`).

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

client = LexiconClient()
selection = client.choose_playlist(show_counts=True)
if selection:
    path, playlist = selection
    print("Selected:", " / ".join(path))
    print("Tracks reported:", playlist.get("numTracks"))

    track_ids = playlist.get("trackIds", [])
    tracks = client.get_track_data_batch(track_ids, max_workers=4)
    for track in tracks:
        print(track["title"], "-", track["artist"])
else:
    print("No playlist selected.")
```

See `examples/demo_lexicon.py` for a more complete walkthrough.

## Development

- Run the test suite: `python -m unittest discover -s tests`
- Style: keep the package pure Python, logging via `logging.getLogger(__name__)`, and prefer small, testable helpers.
- Packaging metadata lives in `pyproject.toml` (see below).

Contributions welcome—open an issue or PR with ideas!
