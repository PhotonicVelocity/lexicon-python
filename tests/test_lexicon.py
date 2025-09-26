import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon import LexiconClient  # noqa: E402  pylint: disable=wrong-import-position


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class LexiconApiTests(unittest.TestCase):
    def setUp(self):
        self.client = LexiconClient()

    def test_lexicon_tree_to_flat_list_builds_paths(self):
        data = [
            {
                "id": 1,
                "name": "Folder",
                "type": "1",
                "playlists": [
                    {"id": 2, "name": "Playlist A", "type": "0"},
                ],
            }
        ]
        flattened = self.client.flatten_tree(data)
        self.assertEqual(
            flattened,
            [
                {"id": 1, "name": "Folder", "type": "2", "path": ["Folder"]},
                {
                    "id": 2,
                    "name": "Playlist A",
                    "type": "0",
                    "path": ["Folder", "Playlist A"],
                },
            ],
        )

    def test_get_track_info_returns_full_track(self):
        track_payload = {
            "id": 123,
            "title": "Example Track",
            "artist": "Example Artist",
            "label": "Label",
            "nested": {"key": "value"},
        }

        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            return DummyResponse({"data": {"track": track_payload}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            info = self.client.get_track_info(123)

        self.assertEqual(info, track_payload)
        self.assertEqual(captured["url"], "http://localhost:48624/v1/track")
        self.assertEqual(captured["params"], {"id": 123})

    def test_get_track_data_batch_sequential(self):
        calls = []

        def fake_info(track_id, **kwargs):
            calls.append(track_id)
            return {"id": track_id}

        with patch.object(self.client, "get_track_info", fake_info):
            result = self.client.get_track_data_batch([1, 2, 3], max_workers=0)

        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(
            result,
            [
                {"id": 1},
                {"id": 2},
                {"id": 3},
            ],
        )

    def test_get_track_data_batch_parallel(self):
        def fake_info(track_id, **kwargs):
            return {"id": track_id}

        with patch.object(self.client, "get_track_info", fake_info):
            results = self.client.get_track_data_batch([10, 11], max_workers=2)

        sorted_results = sorted(results, key=lambda item: item["id"])
        self.assertEqual(
            sorted_results,
            [
                {"id": 10},
                {"id": 11},
            ],
        )

    def test_choose_playlist_handles_valid_selection(self):
        tree = [
            {
                "name": "Folder",
                "type": "1",
                "playlists": [
                    {"id": 1, "name": "P1", "type": "2"},
                    {"id": 2, "name": "P2", "type": "2"},
                ],
            }
        ]

        inputs = iter(["1", "2"])

        with patch.object(self.client, "get_playlists", return_value=tree), \
                patch.object(self.client, "get_playlist", return_value={"trackIds": [1, 2, 3]}):
            result = self.client.choose_playlist(show_counts=False, input_func=lambda _: next(inputs))

        self.assertIsNotNone(result)
        path, chosen = result
        self.assertEqual(path, ["Folder", "P2"])
        self.assertEqual(chosen["id"], 2)
        self.assertEqual(chosen["name"], "P2")

    def test_choose_playlist_handles_cancel(self):
        tree = [
            {
                "name": "Folder",
                "type": "1",
                "playlists": [
                    {"id": 1, "name": "P1", "type": "2"},
                ],
            }
        ]

        with patch.object(self.client, "get_playlists", return_value=tree):
            result = self.client.choose_playlist(show_counts=False, input_func=lambda _: "")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
