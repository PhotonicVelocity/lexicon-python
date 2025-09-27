"""CLI demo that exercises the :class:`lexicon.LexiconClient` helpers.

Run with the virtual environment activated::

    python examples/demo_lexicon.py

Optionally set ``LEXICON_HOST`` / ``LEXICON_PORT`` environment variables if
your Lexicon instance is not available at the defaults (``localhost:48624``).
"""

import logging
import os
import sys
from pprint import pprint

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from lexicon import LexiconClient

logging.basicConfig(level=logging.INFO)

def main() -> None:
    lexicon = LexiconClient()

    tracks = lexicon.get_tracks(limit=1500)
    print(f"Fetched {len(tracks)} tracks")
    
    selection = lexicon.choose_playlist(flat=False, show_counts=True)
    if not selection:
        return

    playlist, path = selection

    print(f"\nChosen playlist: {(' -> '.join(path) if path else "ROOT")} [id:{playlist.get('id')}] - {len(set(playlist.get('trackIds')))} tracks")

    track_ids = set(playlist.get("trackIds", []))

    if not track_ids:
        print("Playlist has no track IDs to fetch.")
        return

    print(f"Playlist contains {len(track_ids)} tracks. Fetching details for the first 5…")
    tracks = lexicon.get_track_batch(track_ids[:5])

    for idx, track in enumerate(tracks, start=1):
        print(f"\nTrack {idx}:")
        pprint({
            key: track.get(key)
            for key in [
                "title",
                "artist",
                "albumTitle",
                "label",
                "comment",
                "bpm",
                "genre",
            ]
        })


if __name__ == "__main__":
    main()
