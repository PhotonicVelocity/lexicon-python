import sys
import unittest
from pathlib import Path

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.resources.playlists_types import (  # noqa: E402
    _normalize_playlist_type,
    _normalize_playlist_path,
    _normalize_smartlist,
)
import lexicon.resources.playlist_tracks_types as playlist_tracks_types  # noqa: E402, F401


class PlaylistsTypesTests(unittest.TestCase):
    def test_playlist_tracks_types_import(self):
        self.assertTrue(hasattr(playlist_tracks_types, "__doc__"))

    def test_normalize_playlist_type_int(self):
        self.assertEqual(_normalize_playlist_type(1), "1")

    def test_normalize_playlist_type_name(self):
        self.assertEqual(_normalize_playlist_type("playlist"), "2")

    def test_normalize_playlist_type_code(self):
        self.assertEqual(_normalize_playlist_type("3"), "3")

    def test_normalize_playlist_type_invalid(self):
        with self.assertRaises(ValueError):
            _normalize_playlist_type(9)

    def test_normalize_playlist_path_invalid_type(self):
        self.assertIsNone(_normalize_playlist_path("Genres"))

    def test_normalize_playlist_path_invalid_component(self):
        self.assertIsNone(_normalize_playlist_path([" "]))
        self.assertIsNone(_normalize_playlist_path([1]))

    def test_normalize_playlist_path_success(self):
        self.assertEqual(_normalize_playlist_path([" Genres ", "Drum & Bass "]), ["Genres", "Drum & Bass"])

    def test_normalize_smartlist_invalid(self):
        self.assertIsNone(_normalize_smartlist(["bad"]))

    def test_normalize_smartlist_success(self):
        self.assertEqual(_normalize_smartlist({"rule": 1}), {"rule": 1})
