"""Integration tests for track operations."""

import pytest

pytestmark = pytest.mark.integration


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
        assert result.get(field) == expected, f"{field}: expected {expected!r}, got {result.get(field)!r}"


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
        assert result.get(field) == expected, f"{field}: expected {expected!r}, got {result.get(field)!r}"


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
    result = lexicon.tracks.update(track_id, edits={"archived": False, "incoming": False})
    assert result is not None
    assert result.get("archived") in (0, False)
    assert result.get("incoming") in (0, False)


def test_update_cuepoints(lexicon):
    """Updating cuepoints should persist."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    cuepoints = [
        {"position": 0, "startTime": 0.5, "type": "normal", "name": "Intro", "color": "green"},
        {"position": 1, "startTime": 4.0, "type": "loop", "name": "Drop", "endTime": 7.0, "color": "red"},
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


def test_delete_track(lexicon):
    """Deleting all test tracks should leave the library empty."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    all_ids = [t["id"] for t in tracks]
    assert lexicon.tracks.delete(all_ids) is True
    remaining = lexicon.tracks.list()
    assert not remaining or len(remaining) == 0
