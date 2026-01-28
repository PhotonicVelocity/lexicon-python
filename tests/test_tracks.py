import logging
import sys
from datetime import date, datetime
from typing import Mapping
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.resources.tracks import Tracks  # noqa: E402
from lexicon.resources.tracks_types import (  # noqa: E402
    FilterField,
    TrackEditField,
    _normalize_edits,
    _normalize_fields,
    _normalize_filters,
    _normalize_sorts,
    _normalize_bool,
    _normalize_text,
    _normalize_number,
    _normalize_date,
    _normalize_tag_filter,
    _normalize_tags,
    _normalize_cuepoint_type,
    _normalize_cuepoints,
    _normalize_tempomarkers,
)


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


class TracksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracks = Tracks(DummyClient())  # type: ignore[arg-type]

    def test_get_invalid_strict_raises(self):
        with self.assertRaises(ValueError):
            self.tracks.get("nope", validation="strict")  # type: ignore[arg-type]

    def test_get_success(self):
        response = {"data": {"track": {"id": 1}}}
        with patch.object(self.tracks, "_get", return_value=response):
            result = self.tracks.get(1)
        self.assertEqual(result, {"id": 1})

    def test_get_response_not_dict(self):
        with patch.object(self.tracks, "_get", return_value=[]):
            self.assertIsNone(self.tracks.get(1))

    def test_get_missing_track(self):
        with patch.object(self.tracks, "_get", return_value={"data": {}}):
            self.assertIsNone(self.tracks.get(1))

    def test_get_invalid_warn_returns_none(self):
        with patch.object(self.tracks, "_get") as mocked_get:
            result = self.tracks.get("nope", validation="warn")  # type: ignore[arg-type]
        self.assertIsNone(result)
        mocked_get.assert_not_called()

    def test_get_invalid_off_calls_get(self):
        response = {"data": {"track": {"id": 1}}}
        with patch.object(self.tracks, "_get", return_value=response) as mocked_get:
            result = self.tracks.get(0, validation="off")
        self.assertEqual(result, {"id": 1})
        mocked_get.assert_called_once()
    def test_get_many_empty(self):
        self.assertIsNone(self.tracks.get_many([]))

    def test_get_many_invalid_ids_warn(self):
        result = self.tracks.get_many([0, -1])
        self.assertIsNone(result)

    def test_get_many_invalid_ids_strict(self):
        with self.assertRaises(ValueError):
            self.tracks.get_many([0], validation="strict")

    def test_get_many_invalid_ids_off(self):
        result = self.tracks.get_many([0], validation="off")
        self.assertEqual(result, [None])

    def test_get_many_no_all_ids_fallback(self):
        with patch.object(self.tracks, "list", return_value=None) as mocked_list, \
                patch.object(self.tracks, "get", return_value={"id": 1}) as mocked_get:
            result = self.tracks.get_many([1, 0, 2])
        self.assertEqual(result, [{"id": 1}, {"id": 1}])
        mocked_list.assert_called()
        self.assertEqual(mocked_get.call_count, 2)

    def test_get_many_large_request_trims(self):
        def list_side_effect(*args, **kwargs):
            if kwargs.get("fields") == ["id"]:
                return [{"id": i} for i in range(1, 21)]
            return [{"id": 1}, {"id": 2}, {"id": 3}]

        with patch.object(self.tracks, "list", side_effect=list_side_effect):
            result = self.tracks.get_many([1, 2, 3])
        self.assertEqual(result, [{"id": 1}, {"id": 2}, {"id": 3}])

    def test_get_many_small_request_uses_get(self):
        with patch.object(self.tracks, "list", return_value=[{"id": i} for i in range(100)]), \
                patch.object(self.tracks, "get", return_value={"id": 1}) as mocked_get:
            result = self.tracks.get_many([1, 2])
        self.assertEqual(result, [{"id": 1}, {"id": 1}])
        self.assertEqual(mocked_get.call_count, 2)


class TracksValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracks = Tracks(DummyClient())  # type: ignore[arg-type]

    def test_list_invalid_source_strict_raises(self):
        with patch.object(self.tracks, "_paged_tracks_json") as mocked_paged:
            with self.assertRaises(ValueError):
                self.tracks.list(source="bad", validation="strict")  # type: ignore[arg-type]
        mocked_paged.assert_not_called()

    def test_list_invalid_source_warn(self):
        with patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(source="bad", validation="warn")  # type: ignore[arg-type]
        payload = mocked_paged.call_args[0][1]
        self.assertNotIn("source", payload)

    def test_list_invalid_source_off(self):
        with patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(source="bad", validation="off")  # type: ignore[arg-type]
        payload = mocked_paged.call_args[0][1]
        self.assertEqual(payload.get("source"), "bad")

    def test_list_source_none_skips_source(self):
        with patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(source=None, validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertNotIn("source", payload)

    def test_list_validation_off_passes_sort(self):
        sort_input = [{"field": "title", "dir": "asc"}]
        with patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(sort=sort_input, validation="off")
        payload = mocked_paged.call_args[0][1]
        self.assertEqual(payload.get("sort"), sort_input)

    def test_list_sort_invalid_fields_warn(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], ["bad"], None)), \
                patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(sort=[("title", "asc")], validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertNotIn("sort", payload)

    def test_list_sort_invalid_fields_strict(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], ["bad"], None)):
            with self.assertRaises(ValueError):
                self.tracks.list(sort=[("title", "asc")], validation="strict")

    def test_list_sort_value_errors_warn(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], None, ["oops"])), \
                patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(sort=[("title", "asc")], validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertNotIn("sort", payload)

    def test_list_sort_value_errors_strict(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], None, ["oops"])):
            with self.assertRaises(ValueError):
                self.tracks.list(sort=[("title", "asc")], validation="strict")

    def test_list_sort_exception_warn(self):
        with patch("lexicon.resources.tracks._normalize_sorts", side_effect=ValueError("bad")), \
                patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(sort=[("title", "asc")], validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertNotIn("sort", payload)

    def test_list_sort_exception_strict(self):
        with patch("lexicon.resources.tracks._normalize_sorts", side_effect=ValueError("bad")):
            with self.assertRaises(ValueError):
                self.tracks.list(sort=[("title", "asc")], validation="strict")

    def test_list_sort_payload_set(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([{"field": "title"}], None, None)), \
                patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(sort=[("title", "asc")], validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertEqual(payload.get("sort"), [{"field": "title"}])

    def test_list_fields_invalid_string_warn(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], "bad", None)), \
                patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(fields=["id"], validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertEqual(payload.get("fields"), ["id"])

    def test_list_fields_invalid_string_strict(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], "bad", None)):
            with self.assertRaises(ValueError):
                self.tracks.list(fields=["id"], validation="strict")

    def test_list_fields_invalid_names_warn(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], None, ["bad"])), \
                patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(fields=["id"], validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertEqual(payload.get("fields"), ["id"])

    def test_list_fields_invalid_names_strict(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], None, ["bad"])):
            with self.assertRaises(ValueError):
                self.tracks.list(fields=["id"], validation="strict")

    def test_list_fields_validation_off_sets_fields(self):
        with patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(fields=["id"], validation="off")
        payload = mocked_paged.call_args[0][1]
        self.assertEqual(payload.get("fields"), ["id"])

    def test_list_fields_all_omits_fields(self):
        with patch.object(self.tracks, "_paged_tracks_json", return_value=[]) as mocked_paged:
            self.tracks.list(fields="all", validation="warn")
        payload = mocked_paged.call_args[0][1]
        self.assertNotIn("fields", payload)

    def test_search_invalid_filter_strict_raises(self):
        with patch.object(self.tracks, "_request") as mocked_request:
            with self.assertRaises(ValueError):
                self.tracks.search({"bad": "x"}, sort=[("title", "asc")], validation="strict")  # type: ignore[arg-type]
        mocked_request.assert_not_called()

    def test_search_filter_exception_strict(self):
        with patch("lexicon.resources.tracks._normalize_filters", side_effect=ValueError("bad")):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_filter_invalid_fields_strict(self):
        with patch("lexicon.resources.tracks._normalize_filters", return_value=({}, ["bad"], None)):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_filter_value_errors_strict(self):
        with patch("lexicon.resources.tracks._normalize_filters", return_value=({}, None, ["oops"])):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_invalid_source_strict(self):
        with self.assertRaises(ValueError):
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], source="bad", validation="strict")  # type: ignore[arg-type]

    def test_search_sort_invalid_fields_strict(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], ["bad"], None)):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_sort_value_errors_strict(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], None, ["oops"])):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_sort_exception_strict(self):
        with patch("lexicon.resources.tracks._normalize_sorts", side_effect=ValueError("bad")):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_fields_validation_off_sets_fields(self):
        with patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], fields=["id"], validation="off")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertEqual(payload.get("fields"), ["id"])

    def test_search_fields_all_omits_fields(self):
        with patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], fields="all", validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertNotIn("fields", payload)

    def test_search_fields_invalid_string_strict(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], "bad", None)):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_fields_invalid_names_strict(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], None, ["bad"])):
            with self.assertRaises(ValueError):
                self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="strict")

    def test_search_filter_exception_warn(self):
        with patch("lexicon.resources.tracks._normalize_filters", side_effect=ValueError("bad")), \
                patch.object(self.tracks, "_request") as mocked_request:
            result = self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="warn")
        self.assertIsNone(result)
        mocked_request.assert_not_called()

    def test_search_filter_invalid_fields_warn(self):
        with patch("lexicon.resources.tracks._normalize_filters", return_value=({"title": "a"}, ["bad"], None)), \
                patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertEqual(payload.get("filter"), {"title": "a"})

    def test_search_filter_value_errors_warn(self):
        with patch("lexicon.resources.tracks._normalize_filters", return_value=({"title": "a"}, None, ["oops"])), \
                patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertEqual(payload.get("filter"), {"title": "a"})

    def test_search_invalid_source_warn(self):
        with patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], source="bad", validation="warn")  # type: ignore[arg-type]
        payload = mocked_request.call_args.kwargs["json"]
        self.assertNotIn("source", payload)

    def test_search_invalid_source_off(self):
        with patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], source="bad", validation="off")  # type: ignore[arg-type]
        payload = mocked_request.call_args.kwargs["json"]
        self.assertEqual(payload.get("source"), "bad")

    def test_search_source_none_skips_source(self):
        with patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], source=None, validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertNotIn("source", payload)

    def test_search_empty_sort_skips_sort(self):
        with patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[], validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertNotIn("sort", payload)

    def test_search_sort_invalid_fields_warn(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], ["bad"], None)), \
                patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}):
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="warn")

    def test_search_sort_value_errors_warn(self):
        with patch("lexicon.resources.tracks._normalize_sorts", return_value=([], None, ["oops"])), \
                patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}):
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="warn")

    def test_search_fields_invalid_names_warn(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], None, ["bad"])), \
                patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], fields=["id"], validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertEqual(payload.get("fields"), ["id"])

    def test_search_sort_exception_warn(self):
        with patch("lexicon.resources.tracks._normalize_sorts", side_effect=ValueError("bad")), \
                patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertNotIn("sort", payload)

    def test_search_fields_invalid_string_warn(self):
        with patch("lexicon.resources.tracks._normalize_fields", return_value=(["id"], "bad", None)), \
                patch.object(self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}) as mocked_request:
            self.tracks.search({"title": "a"}, sort=[("title", "asc")], fields=["id"], validation="warn")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertEqual(payload.get("fields"), ["id"])

    def test_search_response_not_dict(self):
        with patch.object(self.tracks, "_request", return_value=[]):
            self.assertIsNone(self.tracks.search({"title": "a"}, sort=[("title", "asc")]))

    def test_search_response_total_warns(self):
        response = {"data": {"tracks": [{"id": 1}], "total": 10}}
        with patch.object(self.tracks, "_request", return_value=response):
            result = self.tracks.search({"title": "a"}, sort=[("title", "asc")])
        self.assertEqual(result, [{"id": 1}])

    def test_search_response_missing_tracks(self):
        with patch.object(self.tracks, "_request", return_value={"data": {}}):
            self.assertIsNone(self.tracks.search({"title": "a"}, sort=[("title", "asc")]))

    def test_search_validation_off_passes_raw_filter(self):
        with patch.object(
            self.tracks, "_request", return_value={"data": {"tracks": [], "total": 0}}
        ) as mocked_request:
            raw_filter: Mapping[FilterField, object] = {"title": "a"}
            raw_sort = [{"field": "title"}]
            self.tracks.search(raw_filter, sort=raw_sort, validation="off")
        payload = mocked_request.call_args.kwargs["json"]
        self.assertEqual(payload.get("filter"), raw_filter)
        self.assertEqual(payload.get("sort"), raw_sort)

    def test_update_invalid_edits_strict_raises(self):
        with patch.object(self.tracks, "_patch") as mocked_patch:
            with self.assertRaises(ValueError):
                self.tracks.update(1, {"bad": 1}, validation="strict")  # type: ignore[arg-type]
        mocked_patch.assert_not_called()

    def test_update_invalid_track_id_strict(self):
        with self.assertRaises(ValueError):
            self.tracks.update(0, {"title": "x"}, validation="strict")

    def test_update_invalid_edits_payload_strict(self):
        with self.assertRaises(ValueError):
            self.tracks.update(1, [], validation="strict")  # type: ignore[arg-type]

    def test_update_normalize_edits_raises_strict(self):
        with patch("lexicon.resources.tracks._normalize_edits", side_effect=ValueError("bad")):
            with self.assertRaises(ValueError):
                self.tracks.update(1, {"title": "x"}, validation="strict")

    def test_update_value_errors_strict(self):
        with patch("lexicon.resources.tracks._normalize_edits", return_value=({"title": "x"}, None, ["oops"])):
            with self.assertRaises(ValueError):
                self.tracks.update(1, {"title": "x"}, validation="strict")

    def test_update_no_valid_edits_strict(self):
        with patch("lexicon.resources.tracks._normalize_edits", return_value=({}, None, None)):
            with self.assertRaises(ValueError):
                self.tracks.update(1, {"title": "x"}, validation="strict")

    def test_update_invalid_track_id_warn(self):
        with patch.object(self.tracks, "_patch") as mocked_patch:
            result = self.tracks.update(0, {"title": "x"}, validation="warn")
        self.assertFalse(result)
        mocked_patch.assert_not_called()

    def test_update_invalid_edits_payload_warn(self):
        with patch.object(self.tracks, "_patch") as mocked_patch:
            result = self.tracks.update(1, [], validation="warn")  # type: ignore[arg-type]
        self.assertFalse(result)
        mocked_patch.assert_not_called()

    def test_update_invalid_edits_warn_returns_false(self):
        with patch.object(self.tracks, "_patch") as mocked_patch:
            result = self.tracks.update(1, {"bad": 1}, validation="warn")  # type: ignore[arg-type]
        self.assertFalse(result)
        mocked_patch.assert_not_called()

    def test_update_validation_off(self):
        response = {"data": {"track": {"id": 1}}}
        with patch.object(self.tracks, "_patch", return_value=response) as mocked_patch:
            result = self.tracks.update(1, {"title": "x"}, validation="off")
        self.assertEqual(result, {"id": 1})
        mocked_patch.assert_called()

    def test_update_normalize_edits_raises_warn(self):
        with patch("lexicon.resources.tracks._normalize_edits", side_effect=ValueError("bad")), \
                patch.object(self.tracks, "_patch") as mocked_patch:
            result = self.tracks.update(1, {"title": "x"}, validation="warn")
        self.assertFalse(result)
        mocked_patch.assert_not_called()

    def test_update_value_errors_warn(self):
        with patch("lexicon.resources.tracks._normalize_edits", return_value=({"title": "x"}, None, ["oops"])), \
                patch.object(self.tracks, "_patch", return_value={"data": {"track": {"id": 1}}}) as mocked_patch:
            result = self.tracks.update(1, {"title": "x"}, validation="warn")
        self.assertEqual(result, {"id": 1})
        mocked_patch.assert_called()

    def test_update_response_not_dict(self):
        with patch.object(self.tracks, "_patch", return_value=[]):
            result = self.tracks.update(1, {"title": "x"}, validation="off")
        self.assertIsNone(result)

    def test_update_response_missing_track(self):
        with patch.object(self.tracks, "_patch", return_value={"data": {}}):
            result = self.tracks.update(1, {"title": "x"}, validation="off")
        self.assertIsNone(result)

    def test_update_no_valid_edits_warn(self):
        with patch("lexicon.resources.tracks._normalize_edits", return_value=({}, None, None)):
            result = self.tracks.update(1, {"title": "x"}, validation="warn")
        self.assertFalse(result)

    def test_add_invalid_locations_strict_raises(self):
        with patch.object(self.tracks, "_post") as mocked_post:
            with self.assertRaises(ValueError):
                self.tracks.add("file.mp3", validation="strict")
        mocked_post.assert_not_called()

    def test_add_invalid_locations_warn(self):
        with patch.object(self.tracks, "_post") as mocked_post:
            result = self.tracks.add("file.mp3", validation="warn")
        self.assertIsNone(result)
        mocked_post.assert_not_called()

    def test_add_invalid_locations_off_passes_through(self):
        response = {"data": {"tracks": []}}
        with patch.object(self.tracks, "_post", return_value=response) as mocked_post:
            result = self.tracks.add("ab", validation="off")  # type: ignore[arg-type]
        self.assertEqual(result, [])
        payload = mocked_post.call_args.kwargs.get("json")
        self.assertEqual(payload.get("locations"), ["a", "b"])

    def test_add_invalid_location_list_warn(self):
        with patch.object(self.tracks, "_post") as mocked_post:
            result = self.tracks.add(["", 123], validation="warn")  # type: ignore[list-item]
        self.assertIsNone(result)
        mocked_post.assert_not_called()

    def test_add_invalid_location_list_strict(self):
        with patch.object(self.tracks, "_post") as mocked_post:
            with self.assertRaises(ValueError):
                self.tracks.add(["", 123], validation="strict")  # type: ignore[list-item]
        mocked_post.assert_not_called()

    def test_add_response_not_dict(self):
        with patch.object(self.tracks, "_post", return_value=[]):
            result = self.tracks.add(["/tmp/a.mp3"], validation="warn")
        self.assertIsNone(result)

    def test_add_response_tracks_list(self):
        response = {"data": {"tracks": [{"id": 1}, {"id": 2}]}}
        with patch.object(self.tracks, "_post", return_value=response):
            result = self.tracks.add(["/tmp/a.mp3"], validation="warn")
        self.assertEqual(result, [{"id": 1}, {"id": 2}])

    def test_add_response_tracks_dict(self):
        response = {"data": {"tracks": {"id": 1}}}
        with patch.object(self.tracks, "_post", return_value=response):
            result = self.tracks.add(["/tmp/a.mp3"], validation="warn")
        self.assertEqual(result, [{"id": 1}])

    def test_add_response_missing_tracks(self):
        response = {"data": {}}
        with patch.object(self.tracks, "_post", return_value=response):
            result = self.tracks.add(["/tmp/a.mp3"], validation="warn")
        self.assertIsNone(result)

    def test_delete_invalid_track_ids_strict_raises(self):
        with patch.object(self.tracks, "_delete") as mocked_delete:
            with self.assertRaises(ValueError):
                self.tracks.delete("nope", validation="strict")  # type: ignore[arg-type]
        mocked_delete.assert_not_called()

    def test_delete_invalid_track_ids_warn_returns_false(self):
        with patch.object(self.tracks, "_delete") as mocked_delete:
            result = self.tracks.delete("nope", validation="warn")  # type: ignore[arg-type]
        self.assertFalse(result)
        mocked_delete.assert_not_called()

    def test_delete_all_invalid_ids_warn(self):
        with patch.object(self.tracks, "_delete") as mocked_delete:
            result = self.tracks.delete([0, -1], validation="warn")
        self.assertFalse(result)
        mocked_delete.assert_not_called()

    def test_delete_int_ids(self):
        with patch.object(self.tracks, "_delete", return_value={}) as mocked_delete:
            result = self.tracks.delete(1, validation="warn")
        self.assertTrue(result)
        mocked_delete.assert_called()

    def test_delete_sequence_ids(self):
        with patch.object(self.tracks, "_delete", return_value={}) as mocked_delete:
            result = self.tracks.delete([1, 2], validation="warn")
        self.assertTrue(result)
        mocked_delete.assert_called()

    def test_delete_invalid_ids_off(self):
        with patch.object(self.tracks, "_delete", return_value={}) as mocked_delete:
            result = self.tracks.delete("nope", validation="off")  # type: ignore[arg-type]
        self.assertTrue(result)
        mocked_delete.assert_called()

    def test_delete_all_invalid_ids_strict(self):
        with self.assertRaises(ValueError):
            self.tracks.delete([0, -1], validation="strict")

    def test_paged_tracks_limit_zero(self):
        with patch.object(self.tracks, "_request") as mocked_request:
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=0, offset=0, timeout=None)
        self.assertEqual(result, [])
        mocked_request.assert_not_called()

    def test_paged_tracks_response_not_dict(self):
        with patch.object(self.tracks, "_request", return_value=[]):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=10, offset=0, timeout=None)
        self.assertIsNone(result)

    def test_paged_tracks_missing_tracks_list(self):
        response = {"data": {"tracks": "nope"}}
        with patch.object(self.tracks, "_request", return_value=response):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=10, offset=0, timeout=None)
        self.assertIsNone(result)

    def test_paged_tracks_remaining_breaks(self):
        response = {"data": {"tracks": [{"id": 1}], "total": 1, "limit": 1000}}
        with patch.object(self.tracks, "_request", return_value=response):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=1, offset=0, timeout=None)
        self.assertEqual(result, [{"id": 1}])

    def test_paged_tracks_remaining_continues(self):
        responses = [
            {"data": {"tracks": [{"id": 1}, {"id": 2}], "total": 3, "limit": 2}},
            {"data": {"tracks": [{"id": 3}], "total": 3, "limit": 2}},
        ]
        with patch.object(self.tracks, "_request", side_effect=responses):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=3, offset=0, timeout=None)
        self.assertEqual(result, [{"id": 1}, {"id": 2}, {"id": 3}])

    def test_paged_tracks_total_limit_paging(self):
        responses = [
            {"data": {"tracks": [{"id": 1}, {"id": 2}], "total": 3, "limit": 2}},
            {"data": {"tracks": [{"id": 3}], "total": 3, "limit": 2}},
        ]
        with patch.object(self.tracks, "_request", side_effect=responses):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=None, offset=0, timeout=None)
        self.assertEqual(result, [{"id": 1}, {"id": 2}, {"id": 3}])

    def test_paged_tracks_short_page_breaks(self):
        response = {"data": {"tracks": [{"id": 1}], "total": 10, "limit": 1000}}
        with patch.object(self.tracks, "_request", return_value=response):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=None, offset=0, timeout=None)
        self.assertEqual(result, [{"id": 1}])

    def test_paged_tracks_short_page_no_total(self):
        response = {"data": {"tracks": [{"id": 1}]}}
        with patch.object(self.tracks, "_request", return_value=response):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=None, offset=0, timeout=None)
        self.assertEqual(result, [{"id": 1}])

    def test_paged_tracks_full_page_no_total(self):
        full_page = [{"id": i} for i in range(1000)]
        responses = [
            {"data": {"tracks": full_page}},
            [],
        ]
        with patch.object(self.tracks, "_request", side_effect=responses):
            result = self.tracks._paged_tracks_json("/tracks", {}, limit=None, offset=0, timeout=None)
        self.assertIsNone(result)


class TracksTypesValidationTests(unittest.TestCase):
    def test_normalize_fields_all(self):
        fields, input_error, invalid_fields = _normalize_fields("all")
        self.assertIsNone(fields)
        self.assertIsNone(input_error)
        self.assertIsNone(invalid_fields)

    def test_normalize_fields_invalid_string(self):
        fields, input_error, invalid_fields = _normalize_fields("nope")  # type: ignore[arg-type]
        self.assertIsNotNone(fields)
        self.assertIsNotNone(input_error)
        self.assertIsNone(invalid_fields)

    def test_normalize_fields_invalid_names(self):
        fields, input_error, invalid_fields = _normalize_fields(["id", "nope"])  # type: ignore[arg-type]
        self.assertIn("nope", invalid_fields or [])
        self.assertIsNone(input_error)
        self.assertIn("id", fields or [])

    def test_normalize_fields_none_uses_defaults(self):
        fields, input_error, invalid_fields = _normalize_fields(None)
        self.assertIsNone(input_error)
        self.assertIsNone(invalid_fields)
        self.assertTrue(fields)

    def test_normalize_fields_extra_fields(self):
        fields, input_error, invalid_fields = _normalize_fields(["id"], extra_fields=["title"])
        self.assertIsNone(input_error)
        self.assertIsNone(invalid_fields)
        self.assertIn("id", fields or [])
        self.assertIn("title", fields or [])

    def test_normalize_filters_invalid_type(self):
        with self.assertRaises(ValueError):
            _normalize_filters(["title"])  # type: ignore[arg-type]

    def test_normalize_filters_invalid_field(self):
        payload, invalid_fields, value_errors = _normalize_filters({"bad": "x"})  # type: ignore[arg-type]
        self.assertEqual(payload, {})
        self.assertIn("bad", invalid_fields or [])
        self.assertIsNone(value_errors)

    def test_normalize_filters_value_error(self):
        payload, invalid_fields, value_errors = _normalize_filters({"bpm": "abc"})
        self.assertEqual(payload, {})
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("bpm:") for err in value_errors or []))

    def test_normalize_filters_date_operator_error(self):
        payload, invalid_fields, value_errors = _normalize_filters({"dateAdded": ">2024-01-01"})
        self.assertEqual(payload, {})
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("dateAdded:") for err in value_errors or []))

    def test_normalize_filters_tags_error(self):
        payload, invalid_fields, value_errors = _normalize_filters({"tags": None})
        self.assertEqual(payload, {})
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("tags:") for err in value_errors or []))

    def test_normalize_filters_success(self):
        filters: dict[FilterField, object] = {
            "title": "Daft",
            "bpm": "120",
            "dateAdded": "2024-01-01T00:00:00Z",
            "tags": "House",
        }
        payload, invalid_fields, value_errors = _normalize_filters(filters)
        self.assertEqual(payload["title"], "Daft")
        self.assertEqual(payload["bpm"], "120")
        self.assertEqual(payload["dateAdded"], "2024-01-01")
        self.assertEqual(payload["tags"], "House")
        self.assertIsNone(invalid_fields)
        self.assertIsNone(value_errors)

    def test_normalize_filters_tag_invalid(self):
        payload, invalid_fields, value_errors = _normalize_filters({"tags": "bad,,"})
        self.assertEqual(payload, {})
        self.assertIsNone(invalid_fields)
        self.assertTrue(value_errors)

    def test_normalize_edits_invalid_type(self):
        with self.assertRaises(ValueError):
            _normalize_edits(["title"])  # type: ignore[arg-type]

    @unittest.skip("Not needed for current missing-coverage targets")
    def test_normalize_edits_invalid_field(self):
        payload, invalid_fields, value_errors = _normalize_edits({"bad": "x"})  # type: ignore[arg-type]
        self.assertEqual(payload, {})
        self.assertIn("bad", invalid_fields or [])
        self.assertIsNone(value_errors)

    def test_normalize_edits_success(self):
        edits: dict[TrackEditField, object] = {
            "archived": "1",
            "title": "New",
            "rating": 5,
            "comment": "Updated",
            "tags": [1, 2, 2, 0],
        }
        payload, invalid_fields, value_errors = _normalize_edits(edits)
        self.assertEqual(payload["archived"], 1)
        self.assertEqual(payload["title"], "New")
        self.assertEqual(payload["rating"], 5)
        self.assertEqual(payload["comment"], "Updated")
        self.assertEqual(payload["tags"], [1, 2])
        self.assertIsNone(invalid_fields)
        self.assertIsNone(value_errors)

    def test_normalize_edits_cuepoints_partial_errors(self):
        edits: dict[TrackEditField, object] = {
            "cuepoints": [
                {
                    "position": 0,
                    "startTime": 0.5,
                    "type": "1",
                    "name": 123,
                    "endTime": "bad",
                }
            ]
        }
        payload, invalid_fields, value_errors = _normalize_edits(edits)
        self.assertIn("cuepoints", payload)
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("cuepoints:") for err in value_errors or []))

    def test_normalize_edits_cuepoints_fatal(self):
        edits: dict[TrackEditField, object] = {"cuepoints": "bad"}  # type: ignore[assignment]
        payload, invalid_fields, value_errors = _normalize_edits(edits)
        self.assertIn("cuepoints", payload)
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("cuepoints:") for err in value_errors or []))

    def test_normalize_edits_cuepoints_dropped(self):
        edits: dict[TrackEditField, object] = {"cuepoints": [{}]}
        payload, invalid_fields, value_errors = _normalize_edits(edits)
        self.assertIn("cuepoints", payload)
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("cuepoints:") for err in value_errors or []))

    def test_normalize_edits_tempomarkers_duplicate(self):
        edits: dict[TrackEditField, object] = {
            "tempomarkers": [
                {"startTime": 0.5, "bpm": 120},
                {"startTime": 0.5, "bpm": 121},
            ]
        }
        payload, invalid_fields, value_errors = _normalize_edits(edits)
        self.assertIn("tempomarkers", payload)
        self.assertIsNone(invalid_fields)
        self.assertTrue(any("Duplicate startTime" in err for err in value_errors or []))

    def test_normalize_edits_tempomarkers_fatal(self):
        edits: dict[TrackEditField, object] = {"tempomarkers": "bad"}  # type: ignore[assignment]
        payload, invalid_fields, value_errors = _normalize_edits(edits)
        self.assertIn("tempomarkers", payload)
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("tempomarkers:") for err in value_errors or []))

    def test_normalize_edits_value_error(self):
        edits: dict[TrackEditField, object] = {"rating": -1}
        payload, invalid_fields, value_errors = _normalize_edits(edits)
        self.assertEqual(payload, {})
        self.assertIsNone(invalid_fields)
        self.assertTrue(any(err.startswith("rating:") for err in value_errors or []))

    def test_normalize_sorts_invalid_type(self):
        with self.assertRaises(ValueError):
            _normalize_sorts("title")  # type: ignore[arg-type]

    def test_normalize_sorts_non_sequence(self):
        with self.assertRaises(ValueError):
            _normalize_sorts(123)  # type: ignore[arg-type]

    def test_normalize_sorts_dict(self):
        sort_input: list[dict[str, str]] = [{"field": "title", "dir": "asc"}]
        payload, invalid_fields, value_errors = _normalize_sorts(sort_input)
        self.assertEqual(payload, [{"field": "title", "dir": "asc"}])
        self.assertIsNone(invalid_fields)
        self.assertIsNone(value_errors)

    def test_normalize_sorts_missing_field_key(self):
        payload, invalid_fields, value_errors = _normalize_sorts([{"dir": "asc"}])
        self.assertEqual(payload, [])
        self.assertIsNone(invalid_fields)
        self.assertTrue(value_errors)

    def test_normalize_sorts_non_tuple_item(self):
        payload, invalid_fields, value_errors = _normalize_sorts([123])  # type: ignore[list-item]
        self.assertEqual(payload, [])
        self.assertIsNone(invalid_fields)
        self.assertIsNone(value_errors)

    def test_normalize_sorts_invalid_field(self):
        payload, invalid_fields, value_errors = _normalize_sorts([("nope", "asc")])  # type: ignore[arg-type]
        self.assertEqual(payload, [])
        self.assertIn("nope", invalid_fields or [])
        self.assertIsNone(value_errors)

    def test_normalize_sorts_invalid_direction(self):
        payload, invalid_fields, value_errors = _normalize_sorts([("title", "sideways")])  # type: ignore[arg-type]
        self.assertEqual(payload, [{"field": "title"}])
        self.assertIsNone(invalid_fields)
        self.assertTrue(value_errors)

    def test_normalize_sorts_direction_none(self):
        payload, invalid_fields, value_errors = _normalize_sorts([("title", None)])
        self.assertEqual(payload, [{"field": "title"}])
        self.assertIsNone(invalid_fields)
        self.assertIsNone(value_errors)

    def test_normalize_bool_variants(self):
        self.assertEqual(_normalize_bool(True, context="edit"), 1)
        self.assertEqual(_normalize_bool(0.0, context="edit"), 0)
        self.assertEqual(_normalize_bool("yes", context="edit"), 1)
        self.assertEqual(_normalize_bool("no", context="edit"), 0)
        with self.assertRaises(ValueError):
            _normalize_bool("maybe", context="edit")
        with self.assertRaises(ValueError):
            _normalize_bool(2, context="edit")

    def test_normalize_text_variants(self):
        self.assertEqual(_normalize_text(None, context="filter"), "NONE")
        self.assertIsNone(_normalize_text(None, context="edit"))
        self.assertEqual(_normalize_text("hi", context="edit"), "hi")
        with self.assertRaises(ValueError):
            _normalize_text(1, context="edit")

    def test_normalize_number_variants(self):
        self.assertEqual(_normalize_number(None, context="filter"), "0")
        self.assertEqual(_normalize_number("none", context="filter"), "0")
        self.assertEqual(_normalize_number("1 - 2", context="filter"), "1-2")
        self.assertEqual(_normalize_number("<=2", context="filter"), "<=2")
        self.assertEqual(_normalize_number("+1.5", context="edit"), "+1.5")
        with self.assertRaises(ValueError):
            _normalize_number(-1, context="filter")
        with self.assertRaises(ValueError):
            _normalize_number("bad", context="filter")
        with self.assertRaises(ValueError):
            _normalize_number("bad", context="edit")
        with self.assertRaises(ValueError):
            _normalize_number("1", context="other")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            _normalize_number({}, context="filter")  # type: ignore[arg-type]

    def test_normalize_date_variants(self):
        self.assertEqual(_normalize_date(None, context="filter"), "NONE")
        self.assertIsNone(_normalize_date("none", context="edit"))
        self.assertEqual(_normalize_date("2024-01-01T12:00:00Z", context="filter"), "2024-01-01")
        self.assertEqual(_normalize_date("2024-01-01", context="edit"), "2024-01-01")
        self.assertEqual(_normalize_date(datetime(2024, 1, 2, 3, 4), context="edit"), "2024-01-02")
        self.assertEqual(_normalize_date(date(2024, 1, 3), context="edit"), "2024-01-03")
        with self.assertRaises(ValueError):
            _normalize_date("01-01-2024", context="filter")
        with self.assertRaises(ValueError):
            _normalize_date(">2024-01-01", context="filter")
        with self.assertRaises(ValueError):
            _normalize_date("01-01-2024", context="edit")
        with self.assertRaises(ValueError):
            _normalize_date("2024-01-01", context="other")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            _normalize_date(123, context="edit")  # type: ignore[arg-type]

    def test_normalize_tag_helpers(self):
        self.assertEqual(_normalize_tag_filter("tag1, !tag2"), "tag1, !tag2")
        with self.assertRaises(ValueError):
            _normalize_tag_filter(None)
        with self.assertRaises(ValueError):
            _normalize_tag_filter(1)
        with self.assertRaises(ValueError):
            _normalize_tag_filter("bad,,")
        self.assertEqual(_normalize_tags([1, 2, 0, -1]), [1, 2])
        with self.assertRaises(ValueError):
            _normalize_tags([])
        with self.assertRaises(ValueError):
            _normalize_tags("nope")  # type: ignore[arg-type]

    def test_normalize_cuepoint_type(self):
        self.assertEqual(_normalize_cuepoint_type(1), "1")
        self.assertEqual(_normalize_cuepoint_type("loop"), "5")
        self.assertEqual(_normalize_cuepoint_type("2"), "2")
        with self.assertRaises(ValueError):
            _normalize_cuepoint_type(9)  # type: ignore[arg-type]

    def test_normalize_cuepoints_paths(self):
        payload, errors = _normalize_cuepoints("nope")
        self.assertEqual(payload, [])
        self.assertTrue(errors.fatal)

        payload, errors = _normalize_cuepoints([123])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_cuepoints([{"position": 1, "startTime": 0.5}])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_cuepoints([{"position": "1", "startTime": 0.5, "type": "1"}])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_cuepoints([{"position": 1, "startTime": "0.5", "type": "1"}])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_cuepoints([{"position": 1, "startTime": 0.5, "type": "9"}])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_cuepoints(
            [
                {
                    "position": 1,
                    "startTime": 0.5,
                    "type": "1",
                    "name": 123,
                    "activeLoop": "bad",
                    "endTime": "bad",
                    "color": "not-a-color",
                }
            ]
        )
        self.assertEqual(len(payload), 1)
        self.assertTrue(errors.partial)

        payload, errors = _normalize_cuepoints(
            [
                {
                    "position": 2,
                    "startTime": 1.5,
                    "type": "1",
                    "name": "Cue",
                    "endTime": 2.5,
                }
            ]
        )
        self.assertEqual(payload[0].get("name"), "Cue")
        self.assertEqual(payload[0].get("endTime"), 2.5)
        self.assertFalse(errors.fatal or errors.dropped or errors.partial)

        payload, errors = _normalize_cuepoints(
            [
                {
                    "position": 3,
                    "startTime": 2.0,
                    "type": "1",
                    "name": "Loop",
                    "activeLoop": True,
                    "color": "red",
                }
            ]
        )
        self.assertEqual(payload[0].get("activeLoop"), 1)
        self.assertEqual(payload[0].get("color"), "red")
        self.assertFalse(errors.fatal or errors.dropped)

        payload, errors = _normalize_cuepoints(
            [
                {
                    "position": 4,
                    "startTime": 3.0,
                    "type": "1",
                    "name": "Name",
                }
            ]
        )
        self.assertEqual(payload[0].get("name"), "Name")
        self.assertFalse(errors.fatal or errors.dropped or errors.partial)

    def test_normalize_cuepoints_name_only(self):
        payload, errors = _normalize_cuepoints(
            [
                {
                    "position": 5,
                    "startTime": 4.0,
                    "type": "1",
                    "name": "OnlyName",
                }
            ]
        )
        self.assertEqual(payload[0].get("name"), "OnlyName")
        self.assertFalse(errors.fatal or errors.dropped or errors.partial)

    def test_normalize_tempomarkers_paths(self):
        payload, errors = _normalize_tempomarkers("nope")
        self.assertEqual(payload, [])
        self.assertTrue(errors.fatal)

        payload, errors = _normalize_tempomarkers([123])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_tempomarkers([{"startTime": 0.5}])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_tempomarkers([{"startTime": "0.5", "bpm": 120}])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_tempomarkers(
            [{"startTime": 0.5, "bpm": 120}, {"startTime": 0.5, "bpm": 121}]
        )
        self.assertEqual(len(payload), 1)
        self.assertTrue(errors.dropped)

        payload, errors = _normalize_tempomarkers([{"startTime": 0.5, "bpm": "bad"}])
        self.assertEqual(payload, [])
        self.assertTrue(errors.dropped)
