import logging
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

from lexicon.client import (  # noqa: E402
    APPROVAL_TIMEOUT,
    PAIR_TIMEOUT,
    Lexicon,
    LexiconAuthError,
    LexiconConnectionError,
)
from lexicon.resources.control_types import CONTROL_ACTIONS  # noqa: E402
from lexicon.resources.tracks import ANALYZE_ACTION  # noqa: E402


logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stdout,
    force=True,
)


class FakeResponse:
    def __init__(
        self,
        *,
        content=b"{}",
        json_payload=None,
        json_error=False,
        status_error=None,
        headers=None,
        status_code=200,
    ):
        self.content = content
        self._json_payload = json_payload
        self._json_error = json_error
        self._status_error = status_error
        self.headers = headers or {}
        self.status_code = status_code

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
        self.headers = []

    def request(self, method, url, params=None, json=None, timeout=None, headers=None):
        self.calls.append((method, url, params, json, timeout))
        self.headers.append(headers)
        return self.response


def make_client(response: FakeResponse) -> tuple[Lexicon, FakeSession]:
    session = FakeSession(response)
    client = Lexicon(
        host="example.com", port=1234, session=session, verify_connection=False
    )
    return client, session


class ControlTests(unittest.TestCase):
    def test_sends_action_without_parameters(self):
        client, session = make_client(FakeResponse(json_payload={}))

        self.assertTrue(client.control("MusicPlayer_Eject"))

        method, url, _, payload, _ = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://example.com:1234/v1/control")
        self.assertEqual(payload, {"action": "MusicPlayer_Eject"})

    def test_sends_parameters_under_their_api_names(self):
        client, session = make_client(FakeResponse(json_payload={}))

        self.assertTrue(client.control("MusicPlayer_Load", id=123))

        self.assertEqual(
            session.calls[0][3],
            {"action": "MusicPlayer_Load", "parameters": {"id": 123}},
        )

    def test_keeps_a_null_parameter(self):
        # Application_SetColor uses a null color to remove the color.
        client, session = make_client(FakeResponse(json_payload={}))

        client.control("Application_SetColor", color=None)

        self.assertEqual(session.calls[0][3]["parameters"], {"color": None})

    def test_timeout_is_not_sent_as_a_parameter(self):
        client, session = make_client(FakeResponse(json_payload={}))

        client.control("MusicPlayer_Eject", timeout=3)

        _, _, _, payload, timeout = session.calls[0]
        self.assertEqual(payload, {"action": "MusicPlayer_Eject"})
        self.assertEqual(timeout, 3)

    def test_rejected_action_returns_false(self):
        error = requests.HTTPError("400 Client Error")
        client, _ = make_client(
            FakeResponse(json_payload={"errorCode": 5}, status_error=error)
        )

        with self.assertLogs("lexicon.client", level="WARNING"):
            self.assertFalse(client.control("MusicPlayer_Eject"))

    def test_error_message_in_a_200_response_returns_false(self):
        # Lexicon 1.11.15 reports a handler error with no code this way.
        body = {"message": "h[r].trim is not a function"}
        client, _ = make_client(FakeResponse(json_payload=body))

        self.assertFalse(client.control("MusicPlayer_Eject"))

    def test_unknown_action_is_not_sent_in_warn_mode(self):
        client, session = make_client(FakeResponse(json_payload={}))

        with self.assertLogs("lexicon.client", level="WARNING"):
            self.assertFalse(client.control("Not_An_Action"))  # type: ignore[arg-type]

        self.assertEqual(session.calls, [])

    def test_unknown_action_raises_in_strict_mode(self):
        client, session = make_client(FakeResponse(json_payload={}))

        with self.assertRaises(ValueError):
            client.control("Not_An_Action", validation="strict")  # type: ignore[arg-type]

        self.assertEqual(session.calls, [])

    def test_validation_off_sends_a_plugin_action(self):
        client, session = make_client(FakeResponse(json_payload={}))
        action = "PluginRunAction_myplugin:myaction"

        self.assertTrue(client.control(action, validation="off"))  # type: ignore[arg-type]

        self.assertEqual(session.calls[0][3], {"action": action})

    def test_action_list_includes_analyze_action(self):
        # tracks.analyze() posts this action directly, so the name has to stay valid.
        self.assertIn(ANALYZE_ACTION, CONTROL_ACTIONS)


class ClientTests(unittest.TestCase):
    def test_request_path_normalization(self):
        response = FakeResponse(json_payload={"ok": True})
        session = FakeSession(response)
        client = Lexicon(
            host="example.com",
            port=1234,
            session=session,
            verify_connection=False,
        )
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
        client = Lexicon(
            host="example.com",
            port=1234,
            session=session,
            verify_connection=False,
        )
        client.request("GET", "/v1/tracks")
        self.assertEqual(session.calls[0][1], "http://example.com:1234/v1/tracks")

    def test_request_empty_body_returns_none(self):
        response = FakeResponse(content=b"")
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_non_json_returns_none(self):
        response = FakeResponse(content=b"not json", json_error=True)
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_json_dict_and_list(self):
        response = FakeResponse(json_payload={"data": 1})
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertEqual(client.request("GET", "/tracks"), {"data": 1})
        response._json_payload = [1, 2]
        self.assertEqual(client.request("GET", "/tracks"), [1, 2])
        response._json_payload = "not dict"
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_returns_none(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"message": "problem"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_uses_error_field(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"error": "nope"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_uses_detail_field(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"detail": "nope"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_with_unexpected_json(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload={"other": "nope"}, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_with_non_dict_json(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_payload=["nope"], status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_bad_json_body(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(json_error=True, status_error=error)
        session = FakeSession(response)
        client = Lexicon(session=session, verify_connection=False)
        self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_http_error_raises_when_enabled(self):
        error = requests.HTTPError("bad")
        response = FakeResponse(
            json_payload={"message": "problem"},
            status_error=error,
        )
        session = FakeSession(response)
        client = Lexicon(session=session, raise_on_error=True, verify_connection=False)
        with self.assertRaises(requests.HTTPError):
            client.request("GET", "/tracks")

    def test_request_other_exception_returns_none(self):
        client = Lexicon(verify_connection=False)
        with patch("lexicon.client.requests.request", side_effect=RuntimeError("boom")):
            self.assertIsNone(client.request("GET", "/tracks"))

    def test_request_other_exception_raises_when_enabled(self):
        client = Lexicon(raise_on_error=True, verify_connection=False)
        with patch("lexicon.client.requests.request", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                client.request("GET", "/tracks")

    def test_verify_connection_success_logs_info(self):
        response = FakeResponse(json_payload={"data": None})
        session = FakeSession(response)
        with self.assertLogs("lexicon.client", level="INFO") as ctx:
            client = Lexicon(host="example.com", port=1234, session=session)
        self.assertEqual(len(session.calls), 1)
        method, url, _, _, _ = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "http://example.com:1234/v1/playing")
        self.assertTrue(
            any("Connected to Lexicon" in message for message in ctx.output),
            ctx.output,
        )
        # Sanity: still a working client after the probe.
        self.assertEqual(client.host, "example.com")

    def test_verify_connection_connection_error_raises(self):
        session = FakeSession(FakeResponse())
        session.request = lambda *a, **kw: (_ for _ in ()).throw(  # type: ignore[assignment]
            requests.ConnectionError("refused")
        )
        with self.assertRaises(LexiconConnectionError) as ctx:
            Lexicon(host="example.com", port=1234, session=session)
        self.assertIn("example.com:1234", str(ctx.exception))
        self.assertIn("Local API", str(ctx.exception))

    def test_verify_connection_http_error_raises(self):
        error = requests.HTTPError("500")
        response = FakeResponse(status_error=error)
        session = FakeSession(response)
        with self.assertRaises(LexiconConnectionError):
            Lexicon(session=session)


def http_error(status: int, body: dict) -> FakeResponse:
    """A FakeResponse that raises like requests does for an HTTP error status."""
    response = FakeResponse(json_payload=body, status_code=status)
    error = requests.HTTPError(f"{status} Error")
    error.response = response  # type: ignore[assignment]
    response._status_error = error
    return response


class AuthTests(unittest.TestCase):
    def test_every_request_names_the_app(self):
        client, session = make_client(FakeResponse(json_payload={}))
        client.request("GET", "/tags")
        self.assertEqual(session.headers[0], {"X-Lexicon-App": "lexicon-python"})

    def test_custom_app_name_and_token(self):
        session = FakeSession(FakeResponse(json_payload={}))
        client = Lexicon(
            session=session, verify_connection=False, app_name="My Tool", token="t0k"
        )
        client.request("GET", "/tags")
        self.assertEqual(
            session.headers[0],
            {"X-Lexicon-App": "My Tool", "Authorization": "Bearer t0k"},
        )

    def test_environment_supplies_app_name_and_token(self):
        session = FakeSession(FakeResponse(json_payload={}))
        with (
            patch.dict("os.environ", {"LEXICON_TOKEN": "env-token"}),
            patch("lexicon.client.DEFAULT_APP_NAME", "env-app"),
        ):
            client = Lexicon(session=session, verify_connection=False)
        self.assertEqual(client.app_name, "env-app")
        self.assertEqual(client.token, "env-token")

    def test_token_from_response_header_is_kept(self):
        response = FakeResponse(json_payload={}, headers={"X-Lexicon-Token": "new"})
        client, session = make_client(response)
        with self.assertLogs("lexicon.client", level="INFO") as logs:
            client.request("GET", "/tags")
        self.assertEqual(client.token, "new")
        self.assertFalse(any("new" in line for line in logs.output), logs.output)
        client.request("GET", "/tags")
        self.assertEqual(session.headers[1]["Authorization"], "Bearer new")

    def test_request_logs_auth_hint(self):
        client, _ = make_client(http_error(403, {"message": "blocked", "errorCode": 6}))
        with self.assertLogs("lexicon.client", level="WARNING") as logs:
            self.assertIsNone(client.request("GET", "/tags"))
        self.assertTrue(any("blocked app" in line for line in logs.output))

    def test_verify_waits_for_the_approval_popup(self):
        session = FakeSession(FakeResponse(json_payload={"data": None}))
        Lexicon(session=session)
        self.assertEqual(session.calls[0][4], APPROVAL_TIMEOUT)
        self.assertEqual(session.headers[0], {"X-Lexicon-App": "lexicon-python"})

    def test_verify_raises_auth_error_for_each_refusal(self):
        for status, code in ((401, 10), (403, 6), (409, 11), (401, 9)):
            with self.subTest(code=code):
                session = FakeSession(
                    http_error(status, {"message": "no", "errorCode": code})
                )
                with self.assertRaises(LexiconAuthError) as ctx:
                    Lexicon(session=session, app_name="Tool")
                self.assertEqual(ctx.exception.error_code, code)
                self.assertEqual(ctx.exception.status_code, status)
                self.assertIsInstance(ctx.exception, LexiconConnectionError)

    def test_verify_other_http_error_is_connection_error(self):
        session = FakeSession(http_error(500, {"message": "x", "errorCode": 8}))
        with self.assertRaises(LexiconConnectionError) as ctx:
            Lexicon(session=session)
        self.assertNotIsInstance(ctx.exception, LexiconAuthError)

    def test_verify_keeps_issued_token(self):
        session = FakeSession(
            FakeResponse(json_payload={"data": None}, headers={"X-Lexicon-Token": "t"})
        )
        client = Lexicon(session=session)
        self.assertEqual(client.token, "t")

    def test_pair_returns_and_keeps_token(self):
        session = FakeSession(FakeResponse(json_payload={"data": {"token": "abc"}}))
        client = Lexicon(session=session, verify_connection=False)
        self.assertEqual(client.pair("My Tool"), "abc")
        self.assertEqual((client.token, client.app_name), ("abc", "My Tool"))
        method, url, _, body, timeout = session.calls[0]
        self.assertEqual((method, url), ("POST", "http://localhost:48624/v1/auth/pair"))
        self.assertEqual(body, {"name": "My Tool"})
        self.assertEqual(timeout, PAIR_TIMEOUT)
        self.assertNotIn("Authorization", session.headers[0])

    def test_pair_falls_back_to_header_token(self):
        session = FakeSession(
            FakeResponse(json_payload={}, headers={"X-Lexicon-Token": "hdr"})
        )
        client = Lexicon(session=session, verify_connection=False)
        self.assertEqual(client.pair(), "hdr")

    def test_pair_without_token_raises(self):
        session = FakeSession(FakeResponse(json_payload={"data": {}}))
        client = Lexicon(session=session, verify_connection=False)
        with self.assertRaises(LexiconConnectionError):
            client.pair()

    def test_pair_refused(self):
        session = FakeSession(http_error(409, {"message": "x", "errorCode": 11}))
        client = Lexicon(session=session, verify_connection=False)
        with self.assertRaises(LexiconAuthError) as ctx:
            client.pair("Other")
        self.assertIn("'Other'", str(ctx.exception))
        self.assertEqual(client.app_name, "lexicon-python")
        self.assertIsNone(client.token)

    def test_pair_on_old_lexicon(self):
        session = FakeSession(
            http_error(400, {"message": "Endpoint does not exist", "errorCode": 4})
        )
        client = Lexicon(session=session, verify_connection=False)
        with self.assertRaises(LexiconConnectionError) as ctx:
            client.pair()
        self.assertIn("v1.11", str(ctx.exception))

    def test_pair_unreachable(self):
        session = FakeSession(FakeResponse())
        session.request = lambda *a, **kw: (_ for _ in ()).throw(  # type: ignore[assignment]
            requests.ConnectionError("refused")
        )
        client = Lexicon(session=session, verify_connection=False)
        with self.assertRaises(LexiconConnectionError):
            client.pair()

    def test_deckconnect_names_are_control_actions(self):
        # Lexicon 1.12 renamed the Direct2Cdj_* actions; both stay valid names.
        self.assertIn("DeckConnect_LoadDeck", CONTROL_ACTIONS)
        self.assertIn("DeckConnect_LoadDeck8", CONTROL_ACTIONS)
        self.assertIn("Direct2Cdj_LoadDeck", CONTROL_ACTIONS)
        self.assertEqual(len(CONTROL_ACTIONS), len(set(CONTROL_ACTIONS)))


if __name__ == "__main__":
    unittest.main()
