"""Integration tests for track operations."""

import time

import pytest

pytestmark = pytest.mark.integration

ANALYZE_TIMEOUT_S = 90
ANALYZE_POLL_INTERVAL_S = 1


def test_add_track(lexicon, create_audio_file):
    """Adding a track by file path should return the track with an ID."""
    audio = create_audio_file("test_track.wav")
    result = lexicon.tracks.add([str(audio)])
    assert result is not None
    assert len(result) == 1
    track = result[0]
    assert "id" in track
    assert track["id"] >= 1


def test_list_tracks(lexicon):
    """After adding a track, listing should return at least one."""
    tracks = lexicon.tracks.list()
    assert tracks is not None
    assert len(tracks) >= 1


def test_get_track(lexicon):
    """Should be able to get a track by ID."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    track = lexicon.tracks.get(track_id)
    assert track is not None
    assert track["id"] == track_id
    assert "title" in track
    assert "artist" in track
    assert "location" in track


def test_update_text_fields(lexicon):
    """Updating all text fields should persist."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    edits = {
        "title": "IntTest Title",
        "artist": "IntTest Artist",
        "albumTitle": "IntTest Album",
        "label": "IntTest Label",
        "remixer": "IntTest Remixer",
        "mix": "IntTest Mix",
        "composer": "IntTest Composer",
        "producer": "IntTest Producer",
        "grouping": "IntTest Grouping",
        "lyricist": "IntTest Lyricist",
        "comment": "IntTest Comment",
        "key": "Am",
        "genre": "IntTest Genre",
        "extra1": "IntTest Extra1",
        "extra2": "IntTest Extra2",
    }
    result = lexicon.tracks.update(track_id, edits=edits)
    assert result is not None
    for field, expected in edits.items():
        assert result.get(field) == expected, (
            f"{field}: expected {expected!r}, got {result.get(field)!r}"
        )


def test_update_number_fields(lexicon):
    """Updating all number fields should persist."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    edits = {
        "rating": 5,
        "year": 2025,
        "playCount": 10,
        "trackNumber": 3,
        "energy": 8,
        "danceability": 7,
        "popularity": 6,
        "happiness": 5,
    }
    result = lexicon.tracks.update(track_id, edits=edits)
    assert result is not None
    for field, expected in edits.items():
        assert result.get(field) == expected, (
            f"{field}: expected {expected!r}, got {result.get(field)!r}"
        )


def test_update_color(lexicon):
    """Updating the color field should snap to nearest Lexicon swatch."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    result = lexicon.tracks.update(track_id, edits={"color": "red"})
    assert result is not None
    assert result.get("color") == "red"


def test_update_bool_fields(lexicon):
    """Updating bool fields (incoming, archived) should persist."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]

    # Set both to true
    result = lexicon.tracks.update(track_id, edits={"archived": True, "incoming": True})
    assert result is not None
    assert result.get("archived") in (1, True)
    assert result.get("incoming") in (1, True)

    # Set both back
    result = lexicon.tracks.update(
        track_id, edits={"archived": False, "incoming": False}
    )
    assert result is not None
    assert result.get("archived") in (0, False)
    assert result.get("incoming") in (0, False)


def test_update_cuepoints(lexicon):
    """Updating cuepoints should persist."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    cuepoints = [
        {
            "position": 0,
            "startTime": 0.5,
            "type": "normal",
            "name": "Intro",
            "color": "green",
        },
        {
            "position": 1,
            "startTime": 4.0,
            "type": "loop",
            "name": "Drop",
            "endTime": 7.0,
            "color": "red",
        },
    ]
    result = lexicon.tracks.update(track_id, edits={"cuepoints": cuepoints})
    assert result is not None
    result_cues = result.get("cuepoints")
    assert result_cues is not None
    assert len(result_cues) == 2

    assert result_cues[0]["position"] == 0
    assert result_cues[0]["startTime"] == 0.5
    assert str(result_cues[0]["type"]) == "1"  # normal
    assert result_cues[0]["name"] == "Intro"
    assert result_cues[0].get("color") == "green"

    assert result_cues[1]["position"] == 1
    assert result_cues[1]["startTime"] == 4.0
    assert str(result_cues[1]["type"]) == "5"  # loop
    assert result_cues[1]["name"] == "Drop"
    assert result_cues[1]["endTime"] == 7.0
    assert result_cues[1].get("color") == "red"


def test_update_tempomarkers(lexicon):
    """Updating tempomarkers should persist."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    tempomarkers = [
        {"startTime": 0.0, "bpm": 174},
        {"startTime": 4.0, "bpm": 180},
    ]
    result = lexicon.tracks.update(track_id, edits={"tempomarkers": tempomarkers})
    assert result is not None
    result_tempos = result.get("tempomarkers")
    assert result_tempos is not None
    assert len(result_tempos) == 2
    assert result_tempos[0]["bpm"] == 174
    assert result_tempos[1]["bpm"] == 180


def test_search_tracks(lexicon):
    """Searching by title should find the updated track."""
    results = lexicon.tracks.search(
        filter={"title": "IntTest Title"},
        sort=[{"field": "dateAdded", "dir": "asc"}],
    )
    assert results is not None
    assert len(results) >= 1
    assert results[0].get("title") == "IntTest Title"


SENTINEL_BPM = 77.0


def _wait_for_track(lexicon, track_id, ready, timeout_s, what):
    """Poll tracks.get() until ready(track) holds; fail with the last payload."""
    deadline = time.time() + timeout_s
    track = None
    while time.time() < deadline:
        track = lexicon.tracks.get(track_id)
        if track and ready(track):
            return track
        time.sleep(ANALYZE_POLL_INTERVAL_S)
    pytest.fail(f"{what} did not happen within {timeout_s}s; last response was {track}")


def test_analyze_track(lexicon, create_beat_file):
    """An explicit analyze call should replace a planted beatgrid."""
    audio = create_beat_file("test_analyze_track.wav", bpm=128)
    added = lexicon.tracks.add([str(audio)])
    assert added
    track_id = added[0]["id"]

    # A fresh library auto-analyzes new tracks. Let that pass finish first so it
    # cannot be the thing that replaces the sentinel planted below.
    _wait_for_track(
        lexicon,
        track_id,
        lambda track: bool(track.get("tempomarkers")),
        ANALYZE_TIMEOUT_S,
        "automatic analysis after add",
    )

    planted = lexicon.tracks.update(
        track_id, {"tempomarkers": [{"startTime": 0.0, "bpm": SENTINEL_BPM}]}
    )
    assert planted is not None
    assert planted["tempomarkers"][0]["bpm"] == SENTINEL_BPM

    assert (
        lexicon.tracks.analyze(
            [track_id],
            analyze_beatgrid=True,
            analyze_key=False,
            analyze_waveform=False,
            analyze_energy=False,
            do_not_overwrite=False,
        )
        is True
    )

    # The call returns once Lexicon accepts it and there is no completion
    # signal, so poll until the sentinel beatgrid has been replaced.
    track = _wait_for_track(
        lexicon,
        track_id,
        lambda track: (
            bool(track.get("tempomarkers"))
            and track["tempomarkers"][0]["bpm"] != SENTINEL_BPM
        ),
        ANALYZE_TIMEOUT_S,
        "explicit analysis replacing the sentinel beatgrid",
    )
    bpm = track["bpm"]
    assert isinstance(bpm, (int, float)), f"bpm was {bpm!r}"
    assert bpm > 0


def test_update_returns_the_stored_track(lexicon):
    """Lexicon 1.12 answers PATCH /track with the stored track, relative edits applied."""
    tracks = lexicon.tracks.list(fields=["id", "playCount"])
    assert tracks
    track = tracks[0]
    result = lexicon.tracks.update(track["id"], edits={"playCount": "+2"})
    assert result is not None
    assert result["id"] == track["id"]
    assert result["playCount"] == (track.get("playCount") or 0) + 2


def test_cuepoint_data_and_active_loop_round_trip(lexicon, create_audio_file):
    """Cue data sent back through the SDK is kept, and activeLoop goes out as a boolean."""
    audio = create_audio_file("test_cue_data.wav")
    added = lexicon.tracks.add([str(audio)])
    assert added
    track_id = added[0]["id"]
    data = {"traktor": {"displayOrder": 0, "originalType": "1", "repeats": -1}}
    cues = [
        {
            "position": 0,
            "startTime": 1,
            "type": "normal",
            "activeLoop": 0,
            "data": data,
        },
        {
            "position": 1,
            "startTime": 2.0,
            "endTime": 3.0,
            "type": "loop",
            "activeLoop": 1,
        },
    ]
    result = lexicon.tracks.update(
        track_id, edits={"cuepoints": cues}, validation="strict"
    )
    assert result is not None
    stored = sorted(result["cuepoints"], key=lambda cue: cue["position"])
    assert [cue["activeLoop"] for cue in stored] == [False, True]
    assert stored[0]["data"] == data

    # Send the cues back as GET /track returns them, with one change: the data stays.
    current = lexicon.tracks.get(track_id)
    assert current is not None
    resent = [dict(cue) for cue in current["cuepoints"]]
    resent[1]["name"] = "Renamed"
    result = lexicon.tracks.update(
        track_id, edits={"cuepoints": resent}, validation="strict"
    )
    assert result is not None
    stored = sorted(result["cuepoints"], key=lambda cue: cue["position"])
    assert stored[0]["data"] == data
    assert stored[1]["name"] == "Renamed"

    # Tempo markers and cue points together in one edit.
    result = lexicon.tracks.update(
        track_id,
        edits={"tempomarkers": [{"startTime": 0.25, "bpm": 128}], "cuepoints": resent},
        validation="strict",
    )
    assert result is not None
    assert [m["bpm"] for m in result["tempomarkers"]] == [128]
    assert len(result["cuepoints"]) == 2


def test_update_location(lexicon, create_audio_file):
    """update_location points a track at another file and refuses a missing one."""
    original = create_audio_file("test_location_a.wav")
    moved = create_audio_file("test_location_b.wav")
    added = lexicon.tracks.add([str(original)])
    assert added
    track_id = added[0]["id"]

    result = lexicon.tracks.update_location(track_id, str(moved))
    assert result is not None
    assert result["location"].endswith("test_location_b.wav")

    missing = moved.with_name("test_location_missing.wav")
    assert lexicon.tracks.update_location(track_id, str(missing)) is None
    result = lexicon.tracks.update_location(
        track_id, str(missing), check_file_exists=False
    )
    assert result is not None
    assert result["location"].endswith("test_location_missing.wav")

    result = lexicon.tracks.update_location(track_id, str(original))
    assert result is not None
    assert result["location"].endswith("test_location_a.wav")


def test_search_by_id_and_file_type(lexicon):
    """The 1.12 id and fileType filters narrow the search."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks and len(tracks) >= 2
    ids = [t["id"] for t in tracks[:2]]
    results = lexicon.tracks.search({"id": ids}, fields=["id"])
    assert results is not None
    assert sorted(t["id"] for t in results) == sorted(ids)

    wavs = lexicon.tracks.search({"fileType": "wav"}, fields=["id"])
    assert wavs is not None
    assert len(wavs) == len(tracks)
    assert lexicon.tracks.search({"fileType": "flac"}, fields=["id"]) == []


def test_search_untagged_and_limit(lexicon):
    """tags=None finds untagged tracks, and limit caps the result."""
    untagged = lexicon.tracks.search({"tags": None}, fields=["id", "tags"])
    assert untagged is not None
    assert untagged
    assert all(not t.get("tags") for t in untagged)
    limited = lexicon.tracks.search({"tags": None}, fields=["id"], limit=1)
    assert limited is not None
    assert len(limited) == 1


def test_selected_tracks(lexicon):
    """selected() answers with a list of IDs, empty when nothing is selected."""
    selected = lexicon.tracks.selected()
    assert isinstance(selected, list)


def test_delete_track(lexicon):
    """Deleting all test tracks should leave the library empty."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    all_ids = [t["id"] for t in tracks]
    assert lexicon.tracks.delete(all_ids) is True
    remaining = lexicon.tracks.list()
    assert not remaining or len(remaining) == 0
