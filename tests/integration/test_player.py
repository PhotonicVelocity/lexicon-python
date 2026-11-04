"""Integration tests for the music player and control actions."""

import time

import pytest

pytestmark = pytest.mark.integration

PLAYER_TIMEOUT_S = 30
PLAYER_POLL_INTERVAL_S = 0.5


def _wait_for_player(lexicon, ready, what):
    """Poll player.playing() until ready() accepts it. Control actions have no completion signal."""
    deadline = time.monotonic() + PLAYER_TIMEOUT_S
    while time.monotonic() < deadline:
        playing = lexicon.player.playing()
        if ready(playing):
            return playing
        time.sleep(PLAYER_POLL_INTERVAL_S)
    pytest.fail(f"Timed out after {PLAYER_TIMEOUT_S}s waiting for {what}")


def test_control_loads_and_ejects_a_library_track(lexicon, create_audio_file):
    """MusicPlayer_Load should put a track in the player and MusicPlayer_Eject take it out."""
    audio = create_audio_file("test_player.wav")
    track = lexicon.tracks.add([str(audio)])[0]
    try:
        assert lexicon.control("MusicPlayer_Load", id=track["id"]) is True
        playing = _wait_for_player(
            lexicon,
            lambda p: p is not None and p["track"]["id"] == track["id"],
            "the track to load",
        )
        assert playing["track"]["type"] == "0"
        assert "cuepoints" in playing["track"]

        assert lexicon.control("MusicPlayer_Eject") is True
        _wait_for_player(lexicon, lambda p: p is None, "the player to empty")
    finally:
        lexicon.tracks.delete([track["id"]])


def test_queue_returns_a_list(lexicon):
    """The queue is a list even when nothing is queued."""
    assert isinstance(lexicon.player.queue(), list)


def test_control_rejects_an_unknown_action(lexicon):
    """Lexicon refuses an action it does not know, so control() reports False."""
    assert lexicon.control("Not_An_Action", validation="off") is False
