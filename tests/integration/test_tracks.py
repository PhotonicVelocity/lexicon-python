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


def test_update_track(lexicon):
    """Updating a track's title should persist."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    result = lexicon.tracks.update(track_id, edits={"title": "Integration Test"})
    assert result is not None
    assert result.get("title") == "Integration Test"


def test_search_tracks(lexicon):
    """Searching by title should find the updated track."""
    results = lexicon.tracks.search(
        filter={"title": "Integration Test"},
        sort=[{"field": "dateAdded", "dir": "asc"}],
    )
    assert results is not None
    assert len(results) >= 1
    assert results[0].get("title") == "Integration Test"


def test_delete_track(lexicon):
    """Deleting a track should remove it from the library."""
    tracks = lexicon.tracks.list(fields=["id"])
    assert tracks
    track_id = tracks[0]["id"]
    assert lexicon.tracks.delete(track_id) is True
    # Verify it's gone
    remaining = lexicon.tracks.list()
    if remaining:
        assert all(t.get("id") != track_id for t in remaining)
