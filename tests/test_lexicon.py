import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

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


class DummyErrorResponse(DummyResponse):
    def __init__(self, payload, status_code=400):
        super().__init__(payload)
        self.status_code = status_code

    def raise_for_status(self):
        message = self._payload.get("message", "Error") if isinstance(self._payload, dict) else "Error"
        code = self._payload.get("errorCode") if isinstance(self._payload, dict) else None
        detail = f"{self.status_code} Client Error: {message}"
        if code is not None:
            detail += f" (code {code})"
        raise requests.HTTPError(detail, response=self)


class LexiconApiTests(unittest.TestCase):
    def setUp(self):
        self.client = LexiconClient()
        self.fake_playlist = lambda playlist_id, **kwargs: {
            "id": playlist_id,
            "trackIds": [1, 2, 3],
        }

    tree = {
            "id": 1,
            "name": "ROOT",
            "type": "1",
            "playlists": [
                {"id": 2, "name": "Folder 1", "type": "1", "playlists": [       # 1. 
                    {"id": 5, "name": "Playlist 1", "type": "2"},                  # 1.
                    {"id": 6, "name": "Smartlist 1", "type": "3"}                  # 2.  
                ]},
                {"id": 3, "name": "Playlist 2", "type": "2"},                   # 2.
                {"id": 4, "name": "Folder 2", "type": "1", "playlists": [       # 3.
                    {"id": 7, "name": "Playlist 3", "type": "2"},                   # 1.
                    {"id": 8, "name": "Folder 3", "type": "1", "playlists": [       # 2.
                        {"id": 9, "name": "Playlist 4", "type": "2"}                    # 1.
                    ]} 
                ]},              
            ],
        }

    def test_get_playlists_returns_root_folder(self, tree=tree):
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["timeout"] = kwargs.get("timeout")
            return DummyResponse({"data": {"playlists": [tree]}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            root = self.client.get_playlists()

        self.assertEqual(captured["url"], "http://localhost:48624/v1/playlists")
        self.assertEqual(captured["timeout"], self.client.default_timeout)
        self.assertEqual(root, tree)

    def test_get_playlists_returns_none_when_missing_root(self):
        def fake_get(url, **kwargs):
            return DummyResponse({"data": {"playlists": []}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            root = self.client.get_playlists()

        self.assertIsNone(root)

    def test_get_playlist_returns_playlist(self):
        playlist_payload = {"id": 42, "name": "Test Playlist", "trackIds": [1, 2, 3]}
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            captured["timeout"] = kwargs.get("timeout")
            return DummyResponse({"data": {"playlist": playlist_payload}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            playlist = self.client.get_playlist(42)

        self.assertEqual(playlist, playlist_payload)
        self.assertEqual(captured["url"], "http://localhost:48624/v1/playlist")
        self.assertEqual(captured["params"], {"id": 42})
        self.assertEqual(captured["timeout"], self.client.default_timeout)

    def test_get_playlist_returns_none_when_missing(self):
        error_payload = {"message": "PlaylistNotExist", "errorCode": 101}

        def fake_get(url, **kwargs):
            return DummyErrorResponse(error_payload)

        with patch("lexicon.lexicon.requests.get", fake_get):
            playlist = self.client.get_playlist(999)

        self.assertIsNone(playlist)

    def test_get_playlist_by_path_returns_playlist(self):
        playlist_payload = {"id": 99, "name": "Deep Playlist", "trackIds": [4, 5, 6]}
        playlist_path = ["Folder", "Deep"]
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            captured["timeout"] = kwargs.get("timeout")
            return DummyResponse({"data": {"playlist": playlist_payload}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            playlist = self.client.get_playlist_by_path(playlist_path, playlist_type=3)

        self.assertEqual(playlist, playlist_payload)
        self.assertEqual(captured["url"], "http://localhost:48624/v1/playlist-by-path")
        self.assertEqual(
            captured["params"],
            [("path", "Folder"), ("path", "Deep"), ("type", 3)],
        )
        self.assertEqual(captured["timeout"], self.client.default_timeout)

    def test_get_playlist_by_path_returns_none_when_missing(self):
        playlist_path = ["Missing"]
        error_payload = {"message": "PlaylistNotExist", "errorCode": 101}

        def fake_get(url, **kwargs):
            return DummyErrorResponse(error_payload)

        with patch("lexicon.lexicon.requests.get", fake_get):
            playlist = self.client.get_playlist_by_path(playlist_path)

        self.assertIsNone(playlist)

    def test_lexicon_tree_to_flat_list_builds_paths(self, tree=tree):
        flattened = self.client._flatten_tree(tree)
        self.assertEqual(
            flattened,
            {
                "id": 1, 
                "name": "ROOT", 
                "type": "1", 
                "playlists": [
                    {"id": 2, "name": "Folder 1", "type": "2", "path": ["Folder 1"]},
                    {"id": 5, "name": "Playlist 1", "type": "2", "path": ["Folder 1", "Playlist 1"]},
                    {"id": 6, "name": "Smartlist 1", "type": "3", "path": ["Folder 1", "Smartlist 1"]},
                    {"id": 3, "name": "Playlist 2", "type": "2", "path": ["Playlist 2"]},
                    {"id": 4, "name": "Folder 2", "type": "2", "path": ["Folder 2"]},
                    {"id": 7, "name": "Playlist 3", "type": "2", "path": ["Folder 2", "Playlist 3"]},
                    {"id": 8, "name": "Folder 3", "type": "2", "path": ["Folder 2", "Folder 3"]},
                    {"id": 9, "name": "Playlist 4", "type": "2", "path": ["Folder 2", "Folder 3", "Playlist 4"]},
                ]
            }
        )

    def test_choose_playlist_handles_navigation(self, tree=tree):
        inputs = iter(["3", "2", "0", "1"])  # Navigate to Folder 2 -> Folder 3 -> Folder 2 -> Select Playlist 3

        with patch.object(self.client, "get_playlists", return_value=tree), \
                patch.object(self.client, "get_playlist", side_effect=self.fake_playlist):
            playlist, path = self.client.choose_playlist(flat=False, show_counts=False, input_func=lambda _: next(inputs))

        self.assertIsNotNone(playlist)
        self.assertEqual((playlist, path), ({"id": 7, "trackIds": [1, 2, 3]}, ["Folder 2", "Playlist 3"]))

    def test_choose_playlist_handles_folder_selection(self, tree=tree):
        inputs = iter(["1", ""])  # Navigate to Folder 1 -> Select Folder 1

        with patch.object(self.client, "get_playlists", return_value=tree), \
                patch.object(self.client, "get_playlist", side_effect=self.fake_playlist):
            path, chosen = self.client.choose_playlist(flat=False, show_counts=False, input_func=lambda _: next(inputs))

        self.assertIsNotNone(chosen)
        self.assertEqual((path, chosen), ({"id": 2, "trackIds": [1, 2, 3]}, ["Folder 1"]))

    def test_choose_playlist_flat_selection(self, tree=tree):
        inputs = iter(["7"])  # Select Playlist 1 directly from flat list

        with patch.object(self.client, "get_playlists", return_value=tree), \
                patch.object(self.client, "get_playlist", side_effect=self.fake_playlist):
            path, chosen = self.client.choose_playlist(flat=True, show_counts=False, input_func=lambda _: next(inputs))

        self.assertIsNotNone(chosen)
        self.assertEqual((path, chosen), ({"id": 8, "trackIds": [1, 2, 3]}, ["Folder 2", "Folder 3"]))

    def test_choose_playlist_handles_cancel(self, tree=tree):
        inputs = iter(["3", "c"])  # Select Folder 2 then Cancel

        with patch.object(self.client, "get_playlists", return_value=tree):
            result = self.client.choose_playlist(show_counts=False, input_func=lambda _: next(inputs))
        
        self.assertIsNone(result)

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
            info = self.client.get_track(123)

        self.assertEqual(info, track_payload)
        self.assertEqual(captured["url"], "http://localhost:48624/v1/track")
        self.assertEqual(captured["params"], {"id": 123})

    def test_get_track_info_returns_none_when_missing(self):
        error_payload = {"message": "TrackNotExist", "errorCode": 100}
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            captured["timeout"] = kwargs.get("timeout")
            return DummyErrorResponse(error_payload)

        with patch("lexicon.lexicon.requests.get", fake_get):
            info = self.client.get_track(456)

        self.assertIsNone(info)
        self.assertEqual(captured["url"], "http://localhost:48624/v1/track")
        self.assertEqual(captured["params"], {"id": 456})
        self.assertEqual(captured["timeout"], self.client.default_timeout)

    def test_get_tracks_returns_bulk_payload(self):
        tracks_payload = [
            {"id": 11, "title": "Track A"},
            {"id": 22, "title": "Track B"},
        ]
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            captured["timeout"] = kwargs.get("timeout")
            return DummyResponse({"data": {"tracks": tracks_payload}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            tracks = self.client.get_tracks(
                limit=2,
                source="all",
                fields=["title", "artist"],
                sort=[("title", "desc")],
                offset=5,
            )

        self.assertEqual(tracks, tracks_payload)
        self.assertEqual(captured["url"], "http://localhost:48624/v1/tracks")
        self.assertEqual(
            captured["params"],
            [
                ("limit", 2),
                ("source", "all"),
                ("fields", "title"),
                ("fields", "artist"),
                ("offset", 5),
            ],
        )
        self.assertEqual(captured["timeout"], self.client.default_timeout)

    def test_get_tracks_currently_ignores_sort_requests(self):
        tracks_payload = [{"id": 99, "title": "Track C"}]

        captured = {}

        def fake_get(url, **kwargs):
            captured["params"] = kwargs.get("params")
            return DummyResponse({"data": {"tracks": tracks_payload}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            tracks = self.client.get_tracks(sort=[("bpm", "asc")], fields=None)

        self.assertEqual(tracks, tracks_payload)
        self.assertNotIn(("sort[]", "bpm:asc"), captured["params"])  # sorting disabled for now

    def test_get_tracks_fetches_all_pages_when_requested(self):
        pages = [
            {
                "data": {
                    "total": 5,
                    "limit": 2,
                    "offset": 0,
                    "tracks": [
                        {"id": 1},
                        {"id": 2},
                    ],
                }
            },
            {
                "data": {
                    "total": 5,
                    "limit": 2,
                    "offset": 2,
                    "tracks": [
                        {"id": 3},
                        {"id": 4},
                    ],
                }
            },
            {
                "data": {
                    "total": 5,
                    "limit": 2,
                    "offset": 4,
                    "tracks": [
                        {"id": 5},
                    ],
                }
            },
        ]

        call_counter = {"count": 0}

        def fake_get(url, **kwargs):
            params = kwargs.get("params")
            expected_offset = call_counter["count"] * 2
            self.assertIn(("offset", expected_offset), params)
            page = pages[call_counter["count"]]
            call_counter["count"] += 1
            return DummyResponse(page)

        with patch("lexicon.lexicon.requests.get", fake_get):
            tracks = self.client.get_tracks(limit=2, get_all=True)

        self.assertEqual(call_counter["count"], 3)
        self.assertEqual([t["id"] for t in tracks], [1, 2, 3, 4, 5])
   
    def test_get_tracks_handles_missing_data(self):
        def fake_get(url, **kwargs):
            return DummyResponse({"data": {}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            tracks = self.client.get_tracks()

        self.assertEqual(tracks, [])

    def test_search_tracks_filters_and_warns_on_invalid_fields(self):
        search_payload = {
            "data": {
                "tracks": [
                    {"id": 42, "title": "Found"},
                ],
                "total": 1,
            }
        }
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            captured["timeout"] = kwargs.get("timeout")
            return DummyResponse(search_payload)

        with patch("lexicon.lexicon.requests.get", fake_get):
            tracks = self.client.search_tracks(
                filter={"title": "Found", "invalid": "ignored"},
                fields=["title"],
                source="all",
            )

        self.assertEqual(tracks, search_payload["data"]["tracks"])
        self.assertEqual(captured["url"], "http://localhost:48624/v1/search/tracks")
        self.assertEqual(
            captured["params"],
            [
                ("filter[title]", "Found"),
                ("source", "all"),
                ("fields", "title"),
            ],
        )
        self.assertEqual(captured["timeout"], self.client.default_timeout)

    def test_search_tracks_returns_none_on_error(self):
        def fake_get(url, **kwargs):
            raise requests.HTTPError("boom")

        with patch("lexicon.lexicon.requests.get", fake_get):
            result = self.client.search_tracks(filter={"title": "x"})

        self.assertIsNone(result)

    def test_available_track_sources(self):
        self.assertIn("non-archived", self.client.available_track_sources())
        self.assertEqual(
            self.client.available_track_sources(),
            ("non-archived", "all", "archived", "incoming"),
        )

    def test_available_track_fields(self):
        fields = self.client.available_track_fields()

        self.assertIn("title", fields)
        self.assertIn("bpm", fields)

    def test_get_track_batch_sequential(self):
        calls = []

        def fake_info(track_id, **kwargs):
            calls.append(track_id)
            return {"id": track_id}

        with patch.object(self.client, "get_track", fake_info):
            result = self.client.get_track_batch([1, 2, 3], max_workers=0)

        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(
            result,
            [
                {"id": 1},
                {"id": 2},
                {"id": 3},
            ],
        )

    def test_get_track_batch_parallel(self):
        def fake_info(track_id, **kwargs):
            return {"id": track_id}

        with patch.object(self.client, "get_track", fake_info):
            results = self.client.get_track_batch([11, 10], max_workers=2)

        sorted_results = sorted(results, key=lambda item: item["id"])
        self.assertEqual(
            sorted_results,
            [
                {"id": 10},
                {"id": 11},
            ],
        )
    
    def test_get_tag_data(self):
        captured = {}

        tag_payload = {
            "categories": [
            {
                "id": 2,
                "label": "Vocals",
                "position": 0,
                "color": "#FF00FF",
                "tags": [
                1
                ]
            }
            ],
            "tags": [
            {
                "id": 1,
                "label": "Vocals",
                "categoryId": 2,
                "position": 0
            }
            ]
        }

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["timeout"] = kwargs.get("timeout")
            return DummyResponse({"data": tag_payload})
        
        with patch("lexicon.lexicon.requests.get", fake_get):
            tags = self.client.get_tags()
        
        self.assertEqual(captured["url"], "http://localhost:48624/v1/tags")
        self.assertEqual(captured["timeout"], self.client.default_timeout)
        self.assertEqual(tags, tag_payload)

    def test_get_tags_missing_structure_returns_none(self):
        def fake_get(url, **kwargs):
            return DummyResponse({"data": {"none": []}})

        with patch("lexicon.lexicon.requests.get", fake_get):
            tags = self.client.get_tags()

        self.assertIsNone(tags)

if __name__ == "__main__":
    unittest.main()
