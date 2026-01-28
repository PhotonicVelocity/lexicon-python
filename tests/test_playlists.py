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


class PlaylistsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.playlists = Playlists(DummyClient())  # type: ignore[arg-type]

    def test_get_invalid_id_warn(self):
        with patch.object(self.playlists, "_get") as mocked_get:
            result = self.playlists.get("nope", validation="warn")  # type: ignore[arg-type]
        self.assertIsNone(result)
        mocked_get.assert_not_called()

    def test_get_invalid_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.get(0, validation="strict")

    def test_get_invalid_id_off_calls_get(self):
        with patch.object(self.playlists, "_get") as mocked_get:
            result = self.playlists.get(0, validation="off")
        self.assertIsNone(result)
        mocked_get.assert_not_called()

    def test_get_response_not_dict(self):
        with patch.object(self.playlists, "_get", return_value=[]):
            self.assertIsNone(self.playlists.get(1))

    def test_get_playlist_missing(self):
        with patch.object(self.playlists, "_get", return_value={"data": {}}):
            self.assertIsNone(self.playlists.get(1))

    def test_get_dedupes_track_ids(self):
        response = {"data": {"playlist": {"id": 1, "trackIds": [1, 2, 2, 3]}}}
        with patch.object(self.playlists, "_get", return_value=response):
            result = self.playlists.get(1)
        self.assertEqual(result.get("trackIds"), [1, 2, 3])

    def test_get_track_ids_no_dedupe(self):
        response = {"data": {"playlist": {"id": 1, "trackIds": [1, 2, 3]}}}
        with patch.object(self.playlists, "_get", return_value=response):
            result = self.playlists.get(1)
        self.assertEqual(result.get("trackIds"), [1, 2, 3])

    def test_get_track_ids_not_list(self):
        response = {"data": {"playlist": {"id": 1, "trackIds": "nope"}}}
        with patch.object(self.playlists, "_get", return_value=response):
            result = self.playlists.get(1)
        self.assertEqual(result.get("trackIds"), "nope")

    def test_get_many_invalid_ids_warn(self):
        result = self.playlists.get_many([0, -1], validation="warn")
        self.assertIsNone(result)

    def test_get_many_invalid_ids_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.get_many([0], validation="strict")

    def test_get_many_invalid_ids_off(self):
        with patch.object(self.playlists, "get", return_value={"id": 1}) as mocked_get:
            result = self.playlists.get_many([0, 1], validation="off")
        self.assertEqual(result, [{"id": 1}, {"id": 1}])
        self.assertEqual(mocked_get.call_count, 2)

    def test_get_many_valid_ids_warn(self):
        with patch.object(self.playlists, "get", return_value={"id": 1}) as mocked_get:
            result = self.playlists.get_many([1, 2], validation="warn")
        self.assertEqual(result, [{"id": 1}, {"id": 1}])
        self.assertEqual(mocked_get.call_count, 2)

    def test_get_many_off_calls_get(self):
        with patch.object(self.playlists, "get", return_value={"id": 1}) as mocked_get:
            result = self.playlists.get_many([1, 2], validation="off")
        self.assertEqual(result, [{"id": 1}, {"id": 1}])
        self.assertEqual(mocked_get.call_count, 2)

    def test_list_response_not_dict(self):
        with patch.object(self.playlists, "_get", return_value=[]):
            self.assertIsNone(self.playlists.list())

    def test_list_missing_root(self):
        with patch.object(self.playlists, "_get", return_value={"data": {"playlists": []}}):
            self.assertIsNone(self.playlists.list())

    def test_list_missing_list(self):
        with patch.object(self.playlists, "_get", return_value={"data": {"playlists": {}}}):
            self.assertIsNone(self.playlists.list())

    def test_list_returns_root(self):
        response = {"data": {"playlists": [{"id": 1, "name": "ROOT"}]}}
        with patch.object(self.playlists, "_get", return_value=response):
            result = self.playlists.list()
        self.assertEqual(result.get("id"), 1)

    def test_get_path_invalid_id(self):
        self.assertIsNone(self.playlists.get_path("nope", validation="warn"))  # type: ignore[arg-type]

    def test_get_path_invalid_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.get_path(0, validation="strict")

    def test_get_path_invalid_id_off_calls_list(self):
        with patch.object(self.playlists, "list", return_value=None) as mocked_list:
            result = self.playlists.get_path(0, validation="off")
        self.assertIsNone(result)
        mocked_list.assert_not_called()

    def test_get_path_found(self):
        tree = {"id": 1, "name": "ROOT", "playlists": [{"id": 2, "name": "Genres"}]}
        with patch.object(self.playlists, "list", return_value=tree):
            result = self.playlists.get_path(2)
        self.assertEqual(result, ["Genres"])

    def test_get_path_list_not_dict(self):
        with patch.object(self.playlists, "list", return_value=None):
            self.assertIsNone(self.playlists.get_path(2))

    def test_get_path_not_found(self):
        tree = {"id": 1, "name": "ROOT", "playlists": []}
        with patch.object(self.playlists, "list", return_value=tree):
            result = self.playlists.get_path(2, validation="warn")
        self.assertIsNone(result)

    def test_add_invalid_name(self):
        self.assertIsNone(self.playlists.add("", playlist_type="2", validation="warn"))

    def test_add_invalid_name_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.add("", playlist_type="2", validation="strict")

    def test_add_invalid_name_off(self):
        self.assertIsNone(self.playlists.add("", playlist_type="2", validation="off"))

    def test_add_invalid_type_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.add("Name", playlist_type="nope", validation="strict")  # type: ignore[arg-type]

    def test_add_invalid_type_warn(self):
        self.assertIsNone(self.playlists.add("Name", playlist_type="nope", validation="warn"))  # type: ignore[arg-type]

    def test_add_invalid_parent(self):
        self.assertIsNone(self.playlists.add("Name", playlist_type="2", parent_id=0, validation="warn"))

    def test_add_invalid_parent_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.add("Name", playlist_type="2", parent_id=0, validation="strict")

    def test_add_invalid_smartlist(self):
        with patch("lexicon.resources.playlists._normalize_smartlist", return_value=None):
            self.assertIsNone(
                self.playlists.add("Name", playlist_type="3", smartlist={"bad": 1}, validation="warn")
            )

    def test_add_invalid_smartlist_strict(self):
        with patch("lexicon.resources.playlists._normalize_smartlist", return_value=None):
            with self.assertRaises(ValueError):
                self.playlists.add("Name", playlist_type="3", smartlist={"bad": 1}, validation="strict")

    def test_add_response_not_dict(self):
        with patch.object(self.playlists, "_post", return_value=[]):
            self.assertIsNone(self.playlists.add("Name", playlist_type="2"))

    def test_add_response_missing_id(self):
        with patch.object(self.playlists, "_post", return_value={"data": {}}):
            self.assertIsNone(self.playlists.add("Name", playlist_type="2"))

    def test_add_with_parent_and_smartlist(self):
        response = {"data": {"id": 11}}
        with patch("lexicon.resources.playlists._normalize_smartlist", return_value={"rules": []}), \
                patch.object(self.playlists, "_post", return_value=response) as mocked_post:
            result = self.playlists.add("Name", playlist_type="3", parent_id=2, smartlist={"rules": []})
        self.assertEqual(result, 11)
        payload = mocked_post.call_args.kwargs.get("json")
        self.assertEqual(payload.get("parentId"), 2)
        self.assertEqual(payload.get("smartlist"), {"rules": []})

    def test_add_success(self):
        response = {"data": {"id": 10}}
        with patch.object(self.playlists, "_post", return_value=response):
            result = self.playlists.add("Name", playlist_type="2")
        self.assertEqual(result, 10)

    def test_update_invalid_id_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.update(0, name="x", validation="strict")

    def test_update_invalid_id_warn(self):
        self.assertIsNone(self.playlists.update(0, name="x", validation="warn"))

    def test_update_invalid_name_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.update(1, name="", validation="strict")

    def test_update_invalid_name_warn(self):
        self.assertIsNone(self.playlists.update(1, name="", validation="warn"))

    def test_update_invalid_name_off(self):
        self.assertIsNone(self.playlists.update(1, name="", validation="off"))

    def test_update_invalid_parent_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.update(1, parent_id=0, validation="strict")

    def test_update_invalid_parent_warn(self):
        self.assertIsNone(self.playlists.update(1, parent_id=0, validation="warn"))

    def test_update_invalid_parent_off(self):
        self.assertIsNone(self.playlists.update(1, parent_id=0, validation="off"))

    def test_update_no_updates(self):
        with patch.object(self.playlists, "_patch") as mocked_patch:
            result = self.playlists.update(1, validation="warn")
        self.assertIsNone(result)
        mocked_patch.assert_not_called()

    def test_update_invalid_position_warn(self):
        result = self.playlists.update(1, position=-1, validation="warn")
        self.assertIsNone(result)

    def test_update_invalid_position_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.update(1, position=-1, validation="strict")

    def test_update_invalid_smartlist_strict(self):
        with patch("lexicon.resources.playlists._normalize_smartlist", return_value=None):
            with self.assertRaises(ValueError):
                self.playlists.update(1, smartlist={"bad": 1}, validation="strict")

    def test_update_invalid_smartlist_warn(self):
        with patch("lexicon.resources.playlists._normalize_smartlist", return_value=None):
            self.assertIsNone(self.playlists.update(1, smartlist={"bad": 1}, validation="warn"))

    def test_update_response_not_dict(self):
        with patch.object(self.playlists, "_patch", return_value=[]):
            self.assertIsNone(self.playlists.update(1, name="x"))

    def test_update_response_missing_playlist(self):
        with patch.object(self.playlists, "_patch", return_value={"data": {}}):
            self.assertIsNone(self.playlists.update(1, name="x"))

    def test_update_with_parent_position_smartlist(self):
        response = {"data": {"playlist": {"id": 1, "trackIds": []}}}
        with patch("lexicon.resources.playlists._normalize_smartlist", return_value={"rules": []}), \
                patch.object(self.playlists, "_patch", return_value=response) as mocked_patch:
            result = self.playlists.update(1, parent_id=2, position=1, smartlist={"rules": []})
        self.assertEqual(result.get("id"), 1)
        payload = mocked_patch.call_args.kwargs.get("json")
        self.assertEqual(payload.get("parentId"), 2)
        self.assertEqual(payload.get("position"), 1)
        self.assertEqual(payload.get("smartlist"), {"rules": []})

    def test_update_success(self):
        response = {"data": {"playlist": {"id": 1, "trackIds": [1, 1, 2]}}}
        with patch.object(self.playlists, "_patch", return_value=response):
            result = self.playlists.update(1, name="x")
        self.assertEqual(result.get("trackIds"), [1, 2])

    def test_update_no_dedupe(self):
        response = {"data": {"playlist": {"id": 1, "trackIds": [1, 2]}}}
        with patch.object(self.playlists, "_patch", return_value=response):
            result = self.playlists.update(1, name="x")
        self.assertEqual(result.get("trackIds"), [1, 2])

    def test_update_track_ids_not_list(self):
        response = {"data": {"playlist": {"id": 1, "trackIds": "nope"}}}
        with patch.object(self.playlists, "_patch", return_value=response):
            result = self.playlists.update(1, name="x")
        self.assertEqual(result.get("trackIds"), "nope")

    def test_delete_invalid_ids_warn(self):
        self.assertFalse(self.playlists.delete([0, -1], validation="warn"))

    def test_delete_invalid_ids_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.delete([0], validation="strict")

    def test_delete_invalid_ids_warn_returns_false(self):
        self.assertFalse(self.playlists.delete("nope", validation="warn"))  # type: ignore[arg-type]

    def test_delete_valid_ids_warn(self):
        with patch.object(self.playlists, "_delete", return_value={}):
            self.assertTrue(self.playlists.delete([1], validation="warn"))

    def test_delete_success(self):
        with patch.object(self.playlists, "_delete", return_value={}):
            self.assertTrue(self.playlists.delete([1, 2], validation="off"))

    def test_get_by_path_invalid_path(self):
        self.assertIsNone(self.playlists.get_by_path([""], playlist_type="2", validation="warn"))

    def test_get_by_path_invalid_path_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.get_by_path([""], playlist_type="2", validation="strict")

    def test_get_by_path_invalid_type_strict(self):
        with self.assertRaises(ValueError):
            self.playlists.get_by_path(["Genres"], playlist_type="nope", validation="strict")  # type: ignore[arg-type]

    def test_get_by_path_invalid_type_warn(self):
        self.assertIsNone(self.playlists.get_by_path(["Genres"], playlist_type="nope", validation="warn"))  # type: ignore[arg-type]

    def test_get_by_path_response_not_dict(self):
        with patch.object(self.playlists, "_get", return_value=[]):
            self.assertIsNone(self.playlists.get_by_path(["Genres"], playlist_type="2"))

    def test_get_by_path_success(self):
        response = {"data": {"playlist": {"id": 2}}}
        with patch.object(self.playlists, "_get", return_value=response):
            result = self.playlists.get_by_path(["Genres"], playlist_type="2")
        self.assertEqual(result.get("id"), 2)

    def test_get_by_path_missing_playlist(self):
        with patch.object(self.playlists, "_get", return_value={"data": {}}):
            self.assertIsNone(self.playlists.get_by_path(["Genres"], playlist_type="2"))

    def test_choose_no_tree(self):
        with patch.object(self.playlists, "list", return_value=None):
            self.assertIsNone(self.playlists.choose())

    def test_choose_selection_not_dict(self):
        tree = {"id": 1, "name": "ROOT"}
        with patch.object(self.playlists, "list", return_value=tree), \
                patch("lexicon.resources.playlists.choose_playlist", return_value=None):
            self.assertIsNone(self.playlists.choose())

    def test_choose_selection_without_id(self):
        tree = {"id": 1, "name": "ROOT"}
        selection = {"name": "ROOT"}
        with patch.object(self.playlists, "list", return_value=tree), \
                patch("lexicon.resources.playlists.choose_playlist", return_value=selection):
            result = self.playlists.choose()
        self.assertEqual(result, selection)

    def test_choose_returns_payload(self):
        tree = {"id": 1, "name": "ROOT"}
        with patch.object(self.playlists, "list", return_value=tree), \
                patch("lexicon.resources.playlists.choose_playlist", return_value={"id": 2}) as mocked_choose, \
                patch.object(self.playlists, "get", return_value={"id": 2}) as mocked_get:
            result = self.playlists.choose()
        self.assertEqual(result, {"id": 2})
        mocked_choose.assert_called_once()
        mocked_get.assert_called_once()
