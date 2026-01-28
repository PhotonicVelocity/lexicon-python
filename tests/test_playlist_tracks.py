import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.resources.playlists import Playlists  # noqa: E402
from lexicon.resources.playlist_tracks import PlaylistTracks  # noqa: E402
from lexicon.resources.tracks import Tracks  # noqa: E402


logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stdout,
    force=True,
)


class DummyClient:
    def __init__(self) -> None:
        self._logger = logging.getLogger("lexicon.tests")
        self.request_calls: list[tuple[str, str, object, object, object]] = []

    def request(self, method, path, params=None, json=None, timeout=None):
        self.request_calls.append((method, path, params, json, timeout))
        return {}


class PlaylistTracksTests(unittest.TestCase):
    def setUp(self) -> None:
        client = DummyClient()
        self.tracks = Tracks(client)  # type: ignore[arg-type]
        self.playlists = Playlists(client)  # type: ignore[arg-type]
        self.playlist_tracks = PlaylistTracks(client, tracks=self.tracks, playlists=self.playlists)

    def test_list_invalid_playlist_id(self):
        self.assertIsNone(self.playlist_tracks.list(0, validation="warn"))

    def test_list_invalid_playlist_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.list(0, validation="strict")

    def test_list_playlist_missing(self):
        with patch.object(self.playlists, "get", return_value=None):
            self.assertIsNone(self.playlist_tracks.list(1))

    def test_list_track_ids(self):
        with patch.object(self.playlists, "get", return_value={"trackIds": [1, "bad", 2]}):
            self.assertEqual(self.playlist_tracks.list(1), [1, 2])

    def test_list_track_ids_missing(self):
        with patch.object(self.playlists, "get", return_value={"trackIds": "nope"}):
            self.assertIsNone(self.playlist_tracks.list(1))

    def test_get_invalid_playlist_id(self):
        self.assertIsNone(self.playlist_tracks.get(0, validation="warn"))

    def test_get_invalid_playlist_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.get(0, validation="strict")

    def test_get_empty_playlist(self):
        with patch.object(self.playlist_tracks, "list", return_value=[]):
            self.assertEqual(self.playlist_tracks.get(1), [])

    def test_get_list_none(self):
        with patch.object(self.playlist_tracks, "list", return_value=None):
            self.assertIsNone(self.playlist_tracks.get(1))

    def test_get_tracks(self):
        with patch.object(self.playlist_tracks, "list", return_value=[1, 2]), \
                patch.object(self.tracks, "get_many", return_value=[{"id": 1}, {"id": 2}]) as mocked_get_many:
            result = self.playlist_tracks.get(1)
        self.assertEqual(result, [{"id": 1}, {"id": 2}])
        mocked_get_many.assert_called_once()

    def test_add_invalid_playlist_id(self):
        self.assertFalse(self.playlist_tracks.add(0, [1], validation="warn"))

    def test_add_invalid_playlist_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.add(0, [1], validation="strict")

    def test_add_invalid_track_ids_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.add(1, [0], validation="strict")

    def test_add_invalid_track_ids_warn(self):
        self.assertFalse(self.playlist_tracks.add(1, [0], validation="warn"))

    def test_add_invalid_index_warn(self):
        self.assertFalse(self.playlist_tracks.add(1, [1], index=-1, validation="warn"))

    def test_add_invalid_index_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.add(1, [1], index=-1, validation="strict")

    def test_add_success(self):
        with patch.object(self.playlist_tracks, "_patch", return_value={}):
            self.assertTrue(self.playlist_tracks.add(1, [1, 2], validation="off"))

    def test_add_success_with_index(self):
        with patch.object(self.playlist_tracks, "_patch", return_value={}) as mocked_patch:
            self.assertTrue(self.playlist_tracks.add(1, [1], index=0, validation="off"))
        payload = mocked_patch.call_args.kwargs.get("json")
        self.assertEqual(payload.get("index"), 0)

    def test_remove_invalid_playlist_id(self):
        self.assertFalse(self.playlist_tracks.remove(0, [1], validation="warn"))

    def test_remove_invalid_playlist_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.remove(0, [1], validation="strict")

    def test_remove_invalid_track_ids_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.remove(1, [0], validation="strict")

    def test_remove_invalid_track_ids_warn(self):
        self.assertFalse(self.playlist_tracks.remove(1, [0], validation="warn"))

    def test_remove_success(self):
        with patch.object(self.playlist_tracks, "_delete", return_value={}):
            self.assertTrue(self.playlist_tracks.remove(1, [1], validation="off"))

    def test_remove_valid_ids_warn(self):
        with patch.object(self.playlist_tracks, "_delete", return_value={}):
            self.assertTrue(self.playlist_tracks.remove(1, [1], validation="warn"))

    def test_update_invalid_playlist_id(self):
        self.assertFalse(self.playlist_tracks.update(0, [1], validation="warn"))

    def test_update_invalid_playlist_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlist_tracks.update(0, [1], validation="strict")

    def test_update_invalid_type_strict(self):
        with patch.object(self.playlists, "get", return_value={"type": "1"}):
            with self.assertRaises(ValueError):
                self.playlist_tracks.update(1, [1], validation="strict")

    def test_update_invalid_type_warn(self):
        with patch.object(self.playlists, "get", return_value={"type": "1"}):
            self.assertFalse(self.playlist_tracks.update(1, [1], validation="warn"))

    def test_update_existing_remove_fail(self):
        playlist = {"type": "2", "trackIds": [1]}
        with patch.object(self.playlists, "get", return_value=playlist), \
                patch.object(self.playlist_tracks, "remove", return_value=False):
            self.assertFalse(self.playlist_tracks.update(1, [2]))

    def test_update_playlist_missing(self):
        with patch.object(self.playlists, "get", return_value=None):
            self.assertFalse(self.playlist_tracks.update(1, [2]))

    def test_update_empty_ids(self):
        playlist = {"type": "2", "trackIds": []}
        with patch.object(self.playlists, "get", return_value=playlist):
            self.assertFalse(self.playlist_tracks.update(1, [], validation="warn"))

    def test_update_success(self):
        playlist = {"type": "2", "trackIds": [1]}
        with patch.object(self.playlists, "get", return_value=playlist), \
                patch.object(self.playlist_tracks, "remove", return_value=True), \
                patch.object(self.playlist_tracks, "add", return_value=True):
            self.assertTrue(self.playlist_tracks.update(1, [2], validation="warn"))

    def test_update_invalid_track_ids_warn(self):
        playlist = {"type": "2", "trackIds": []}
        with patch.object(self.playlists, "get", return_value=playlist):
            self.assertFalse(self.playlist_tracks.update(1, [0], validation="warn"))

    def test_update_invalid_track_ids_strict(self):
        playlist = {"type": "2", "trackIds": []}
        with patch.object(self.playlists, "get", return_value=playlist):
            with self.assertRaises(ValueError):
                self.playlist_tracks.update(1, [0], validation="strict")

    def test_update_validation_off_empty_ids(self):
        playlist = {"type": "2", "trackIds": []}
        with patch.object(self.playlists, "get", return_value=playlist):
            self.assertTrue(self.playlist_tracks.update(1, [], validation="off"))

    def test_invalid_inputs_validation_off(self):
        with patch.object(self.playlist_tracks, "list", return_value=[]):
            self.assertIsNone(self.playlist_tracks.get(0, validation="off"))
        with patch.object(self.playlists, "get", return_value=None):
            self.assertIsNone(self.playlist_tracks.list(0, validation="off"))
        self.assertFalse(self.playlist_tracks.add(0, [1], validation="off"))
        self.assertFalse(self.playlist_tracks.remove(0, [1], validation="off"))
        self.assertFalse(self.playlist_tracks.update(0, [1], validation="off"))

    def test_update_invalid_type_off(self):
        with patch.object(self.playlists, "get", return_value={"type": "1"}):
            self.assertFalse(self.playlist_tracks.update(1, [1], validation="off"))
