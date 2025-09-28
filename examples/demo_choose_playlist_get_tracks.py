"""
CLI demo that browses the playlist tree and gets track metadata for the
chosen playlist.

Install lexicon-python before running demo::

    pip install lexicon-python

Optionally set ``LEXICON_HOST`` / ``LEXICON_PORT`` environment variables or 
edit the LexiconClient initialization in the code if your Lexicon instance 
is not available at the defaults (``localhost:48624``).
"""

import logging
from pprint import pprint

from lexicon import LexiconClient

logging.basicConfig(level=logging.INFO)

def main() -> None:
    # Initialize Lexicon client
    lexicon = LexiconClient()
    
    # Let user choose a playlist from the tree
    selection = lexicon.choose_playlist(flat=False, show_counts=True)
    if not selection:
        return
    playlist = selection

    # Get the full path to the chosen playlist for display
    path = lexicon.get_playlist_path(playlist)

    # Display chosen playlist info
    path_pretty = ' -> '.join(path) if path else "ROOT"
    num_tracks = len(set(playlist.get("trackIds", [])))
    print(f"\nChosen playlist: {path_pretty} [id:{playlist.get('id')}] - {num_tracks} tracks")

    # Get unique track IDs from the playlist
    track_ids = list(set(playlist.get("trackIds", []))) # Need to cast to set() for "ROOT" uniqueness bug
    if not track_ids:
        print("Playlist has no track IDs to fetch.")
        return

    # Fetch metadata for the tracks
    # Displays nice progress bar during fetch
    print(f"Playlist contains {len(track_ids)} tracks. Fetching details…")
    tracks = lexicon.get_track_batch(track_ids, max_workers=5, show_progress=True)

    # Display fetched track metadata (first 5 for brevity)
    for idx, track in enumerate(tracks[:5], start=1):
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