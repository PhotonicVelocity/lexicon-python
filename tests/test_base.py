import logging
import sys
import unittest
from pathlib import Path

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.resources.base import Resource  # noqa: E402


class DummyClient:
    def __init__(self) -> None:
        self._logger = logging.getLogger("lexicon.tests")
        self.calls: list[tuple[str, str, object, object, object]] = []

    def request(self, method, path, params=None, json=None, timeout=None):
        self.calls.append((method, path, params, json, timeout))
        return {"ok": True}


class BaseResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = DummyClient()
        self.resource = Resource(self.client)  # type: ignore[arg-type]

    def test_logger_property(self):
        self.assertIs(self.resource._logger, self.client._logger)

    def test_request_passthrough(self):
        result = self.resource._request("GET", "/x", params={"a": 1}, json={"b": 2}, timeout=5)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(self.client.calls[-1], ("GET", "/x", {"a": 1}, {"b": 2}, 5))

    def test_get(self):
        self.resource._get("/g", params={"q": 1}, timeout=2)
        self.assertEqual(self.client.calls[-1], ("GET", "/g", {"q": 1}, None, 2))

    def test_post(self):
        self.resource._post("/p", json={"x": 1}, timeout=3)
        self.assertEqual(self.client.calls[-1], ("POST", "/p", None, {"x": 1}, 3))

    def test_patch(self):
        self.resource._patch("/pt", json={"y": 2}, timeout=4)
        self.assertEqual(self.client.calls[-1], ("PATCH", "/pt", None, {"y": 2}, 4))

    def test_delete(self):
        self.resource._delete("/d", params={"id": 1}, json={"z": 3}, timeout=6)
        self.assertEqual(self.client.calls[-1], ("DELETE", "/d", {"id": 1}, {"z": 3}, 6))
