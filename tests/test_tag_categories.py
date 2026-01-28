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

from lexicon.resources.tag_categories import TagCategories  # noqa: E402


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


class TagCategoriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.categories = TagCategories(DummyClient())  # type: ignore[arg-type]

    def test_list_response_not_dict(self):
        with patch.object(self.categories, "_get", return_value=[]):
            self.assertIsNone(self.categories.list())

    def test_list_missing_categories(self):
        with patch.object(self.categories, "_get", return_value={"data": {}}):
            self.assertIsNone(self.categories.list())

    def test_list_success(self):
        with patch.object(self.categories, "_get", return_value={"data": {"categories": [{"id": 1}]}}):
            self.assertEqual(self.categories.list(), [{"id": 1}])

    def test_add_invalid_label(self):
        self.assertIsNone(self.categories.add("", validation="warn"))

    def test_add_invalid_label_strict(self):
        with self.assertRaises(ValueError):
            self.categories.add("", validation="strict")

    def test_add_invalid_label_off(self):
        self.assertIsNone(self.categories.add("", validation="off"))

    def test_add_invalid_color_strict(self):
        with patch("lexicon.resources.tag_categories._normalize_color", side_effect=ValueError("bad")):
            with self.assertRaises(ValueError):
                self.categories.add("Label", color="nope", validation="strict")

    def test_add_invalid_color_warn(self):
        with patch("lexicon.resources.tag_categories._normalize_color", side_effect=ValueError("bad")):
            self.assertIsNone(self.categories.add("Label", color="nope", validation="warn"))

    def test_add_response_not_dict(self):
        with patch.object(self.categories, "_post", return_value=[]):
            self.assertIsNone(self.categories.add("Label"))

    def test_add_response_missing_data(self):
        with patch.object(self.categories, "_post", return_value={"data": None}):
            self.assertIsNone(self.categories.add("Label"))

    def test_add_success_data_shape(self):
        response = {"data": {"id": 1}}
        with patch.object(self.categories, "_post", return_value=response):
            result = self.categories.add("Label")
        self.assertEqual(result, {"id": 1})

    def test_add_success_with_color(self):
        response = {"data": {"id": 3}}
        with patch.object(self.categories, "_post", return_value=response) as mocked_post:
            result = self.categories.add("Label", color="red")
        self.assertEqual(result, {"id": 3})
        payload = mocked_post.call_args.kwargs.get("json")
        self.assertEqual(payload.get("color"), "red")

    def test_add_success_response_shape(self):
        response = {"id": 2}
        with patch.object(self.categories, "_post", return_value=response):
            result = self.categories.add("Label")
        self.assertEqual(result, {"id": 2})

    def test_update_invalid_id(self):
        self.assertIsNone(self.categories.update(0, label="x", validation="warn"))

    def test_update_invalid_id_strict(self):
        with self.assertRaises(ValueError):
            self.categories.update(0, label="x", validation="strict")

    def test_update_invalid_label(self):
        self.assertIsNone(self.categories.update(1, label="", validation="warn"))

    def test_update_invalid_label_strict(self):
        with self.assertRaises(ValueError):
            self.categories.update(1, label="", validation="strict")

    def test_update_invalid_label_off(self):
        self.assertIsNone(self.categories.update(1, label="", validation="off"))

    def test_update_invalid_color_warn(self):
        with patch("lexicon.resources.tag_categories._normalize_color", side_effect=ValueError("bad")):
            self.assertIsNone(self.categories.update(1, color="nope", validation="warn"))

    def test_update_invalid_color_strict(self):
        with patch("lexicon.resources.tag_categories._normalize_color", side_effect=ValueError("bad")):
            with self.assertRaises(ValueError):
                self.categories.update(1, color="nope", validation="strict")

    def test_update_invalid_tags_warn(self):
        self.assertIsNone(self.categories.update(1, tags=[0], validation="warn"))

    def test_update_invalid_tags_strict(self):
        with self.assertRaises(ValueError):
            self.categories.update(1, tags=[0], validation="strict")

    def test_update_no_updates(self):
        with patch.object(self.categories, "_patch") as mocked_patch:
            self.assertIsNone(self.categories.update(1, validation="warn"))
        mocked_patch.assert_not_called()

    def test_update_response_not_dict(self):
        with patch.object(self.categories, "_patch", return_value=[]):
            self.assertIsNone(self.categories.update(1, label="New"))

    def test_update_success(self):
        response = {"data": {"id": 1}}
        with patch.object(self.categories, "_patch", return_value=response):
            result = self.categories.update(1, label="New")
        self.assertEqual(result, {"id": 1})

    def test_update_with_color_and_tags(self):
        response = {"id": 2}
        with patch.object(self.categories, "_patch", return_value=response) as mocked_patch:
            result = self.categories.update(1, color="red", tags=[1, 2])
        self.assertEqual(result, {"id": 2})
        payload = mocked_patch.call_args.kwargs.get("json")
        self.assertEqual(payload.get("color"), "red")
        self.assertEqual(payload.get("tags"), [1, 2])

    def test_update_response_missing_data(self):
        with patch.object(self.categories, "_patch", return_value={"data": None}):
            self.assertIsNone(self.categories.update(1, label="New"))

    def test_delete_invalid_ids_warn(self):
        self.assertFalse(self.categories.delete([0], validation="warn"))

    def test_delete_invalid_ids_strict(self):
        with self.assertRaises(ValueError):
            self.categories.delete([0], validation="strict")

    def test_delete_failure_in_loop(self):
        with patch.object(self.categories, "_delete", return_value=None):
            self.assertFalse(self.categories.delete([1, 2], validation="warn"))

    def test_delete_failure(self):
        with patch.object(self.categories, "_delete", return_value=None):
            self.assertFalse(self.categories.delete([1], validation="off"))

    def test_delete_success(self):
        with patch.object(self.categories, "_delete", return_value={}):
            self.assertTrue(self.categories.delete([1, 2], validation="off"))
