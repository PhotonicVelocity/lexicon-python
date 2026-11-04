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

from lexicon import Lexicon  # noqa: E402
from lexicon.resources.player import Player  # noqa: E402
from lexicon.resources.tracks import Tracks  # noqa: E402


logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stdout,
    force=True,
)

# Captured from Lexicon 1.11.15: a Beatport track loaded from a library row. Loaded
# from the Beatport tab, the same payload has no "key" field.
BEATPORT_PLAYING = {
    "data": {
        "track": {
            "headers": None,
            "url": "https://geo-samples.beatport.com/track/c9364e24-8434-491b-903b-59b70c3e96e6.LOFI.mp3",
            "streamingService": "0",
            "title": "Essa Ta Quente",
            "artist": "Chase & Status, Skrillex",
            "id": 30520465,
            "imageUrl": "https://geo-media.beatport.com/image_size/1400x1400/d1d2cc49-7603-4bb2-9c2c-966de2b7ff43.jpg",
            "bpm": 88,
            "duration": 57.27,
            "key": "12M",
        },
        "progress": 0.345906516177953,
        "currentTime": 19.810066181511367,
    }
}

LIBRARY_PLAYING = {
    "data": {
        "track": {
            "id": 21128,
            "type": "0",
            "title": "Sell My Soul",
            "streamingService": None,
            "streamingId": None,
            "cuepoints": [{"id": 1, "type": "1", "startTime": 0.0}],
        },
        "progress": 0.5,
        "currentTime": 87.0,
    }
}


class DummyClient:
    def __init__(self, raw_enums: bool = True) -> None:
        self._logger = logging.getLogger("lexicon.tests")
        self.raw_enums = raw_enums
        self.request_calls: list[tuple[str, str, object, object, object]] = []

    def request(self, method, path, params=None, json=None, timeout=None):
        self.request_calls.append((method, path, params, json, timeout))
        return {}


def make_player(raw_enums: bool = True) -> Player:
    client = DummyClient(raw_enums=raw_enums)
    return Player(client, tracks=Tracks(client))  # type: ignore[arg-type]


class PlayerPlayingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.player = make_player()

    def test_streaming_track_is_returned_with_the_service_id(self):
        with patch.object(self.player, "_get", return_value=BEATPORT_PLAYING):
            playing = self.player.playing()

        self.assertEqual(playing, BEATPORT_PLAYING["data"])
        assert playing is not None
        self.assertEqual(playing["track"]["id"], 30520465)
        self.assertEqual(playing["track"]["streamingService"], "0")

    def test_library_track_is_returned(self):
        with patch.object(self.player, "_get", return_value=LIBRARY_PLAYING):
            playing = self.player.playing()

        self.assertEqual(playing, LIBRARY_PLAYING["data"])

    def test_empty_player_returns_none_without_logging(self):
        # Captured from Lexicon 1.11.15 after an eject; currentTime keeps its last value.
        empty = {"data": {"track": None, "progress": 0, "currentTime": 0.976}}
        with patch.object(self.player, "_get", return_value=empty):
            with self.assertNoLogs("lexicon.tests", level="WARNING"):
                self.assertIsNone(self.player.playing())

    def test_null_data_returns_none(self):
        # The shape the spec describes for an empty player.
        with patch.object(self.player, "_get", return_value={"data": None}):
            self.assertIsNone(self.player.playing())

    def test_failed_request_returns_none(self):
        with patch.object(self.player, "_get", return_value=None):
            self.assertIsNone(self.player.playing())

    def test_raw_enums_disabled_converts_library_cuepoints(self):
        player = make_player(raw_enums=False)
        with patch.object(player, "_get", return_value=LIBRARY_PLAYING):
            playing = player.playing()

        assert playing is not None
        self.assertEqual(playing["track"]["cuepoints"][0]["type"], "normal")

    def test_raw_enums_disabled_leaves_streaming_track_unchanged(self):
        player = make_player(raw_enums=False)
        with patch.object(player, "_get", return_value=BEATPORT_PLAYING):
            playing = player.playing()

        self.assertEqual(playing, BEATPORT_PLAYING["data"])

    def test_timeout_is_passed_to_the_request(self):
        client = DummyClient()
        Player(client, tracks=Tracks(client)).playing(timeout=3)  # type: ignore[arg-type]

        self.assertEqual(client.request_calls, [("GET", "/playing", None, None, 3)])

    def test_client_exposes_player(self):
        self.assertIsInstance(Lexicon(verify_connection=False).player, Player)


if __name__ == "__main__":
    unittest.main()
