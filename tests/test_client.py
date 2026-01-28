import logging
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.client import Lexicon  # noqa: E402


logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stdout,
    force=True,
)


class FakeResponse:
    def __init__(self, *, content=b"{}", json_payload=None, json_error=False, status_error=None):
        self.content = content
        self._json_payload = json_payload
        self._json_error = json_error
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        if self._json_error:
            raise ValueError("bad json")
        return self._json_payload


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls = []

    def request(self, method, url, params=None, json=None, timeout=None):
        self.calls.append((method, url, params, json, timeout))
        return self.response


class ClientTests(unittest.TestCase):
    def test_request_path_normalization(self):
        response = FakeResponse(json_payload={"ok": True})
        session = FakeSession(response)
        client = Lexicon(host="example.com", port=1234, session=session)
        client.request("GET", "tracks")
        self.assertEqual(len(session.calls), 1)
        method, url, params, json, timeout = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "http://example.com:1234/v1/tracks")
        self.assertIsNone(params)
        self.assertIsNone(json)
        self.assertEqual(timeout, client.default_timeout)

    def test_request_keeps_v1_prefix(self):
        response = FakeResponse(json_payload={"ok": True})
        session = FakeSession(response)
        client = Lexicon(host="example.com", port=1234, session=session)
        client.request("GET", "/v1/tracks")
        self.assertEqual(session.calls[0][1], "http://example.com:1234/v1/tracks")

    def test_request_empty_body_returns_none(self):
        response = FakeResponse(content=b"")
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_non_json_returns_none(self):
        response = FakeResponse(content=b"not json", json_error=True)
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_json_dict_and_list(self):
        response = FakeResponse(json_payload={"data": 1})
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertEqual(client.request("GET", "/tracks"), {"data": 1})
        response._json_payload = [1, 2]
        self.assertEqual(client.request("GET", "/tracks"), [1, 2])
        response._json_payload = "not dict"
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_returns_none(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"message": "problem"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_uses_error_field(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"error": "nope"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_uses_detail_field(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"detail": "nope"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_with_unexpected_json(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"other": "nope"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_with_non_dict_json(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload=["nope"], status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_bad_json_body(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_error=True, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_raises_when_enabled(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(
            json_payload={"message": "problem"},
            status_error=error,
        )
        session = FakeSession(response)
        client = Lexicon(session=session, raise_on_error=True)
        with self.assertRaises(requests.HTTPError):
            client.request("GET", "/tracks")

    def test_request_other_exception_returns_none(self):
        client = Lexicon()
        with patch("lexicon.client.requests.request", side_effect=RuntimeError("boom")):
            self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_other_exception_raises_when_enabled(self):
        client = Lexicon(raise_on_error=True)
        with patch("lexicon.client.requests.request", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                client.request("GET", "/tracks")


if __name__ == "__main__":
    unittest.main()
