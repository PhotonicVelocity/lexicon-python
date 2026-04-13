"""Integration tests for playlist and playlist track operations."""

import pytest

pytestmark = pytest.mark.integration


# --- Playlists ---


def test_add_folder(lexicon):
    """Creating a folder should return an ID."""
    result = lexicon.playlists.add("IntTest Folder", playlist_type="folder")
    assert result is not None
    assert isinstance(result, int)


def test_add_playlist(lexicon):
    """Creating a playlist should return an ID."""
    result = lexicon.playlists.add("IntTest Playlist", playlist_type="playlist")
    assert result is not None
    assert isinstance(result, int)


def test_add_smartlist(lexicon):
    """Creating a smartlist with rules should return an ID and persist rules."""
    smartlist = {
        "matchAll": True,
        "rules": [
            {
                "field": "bpm",
                "operator": "NumberBetween",
                "values": [120, 130],
                "or": False,
            }
        ],
    }
    result = lexicon.playlists.add(
        "IntTest Smartlist", playlist_type="smartlist", smartlist=smartlist
    )
    assert result is not None
    assert isinstance(result, int)

    # Verify the smartlist rules persisted
    playlist = lexicon.playlists.get(result)
    assert playlist is not None
    assert playlist.get("type") == "3"
    saved_rules = playlist.get("smartlist", {})
    assert saved_rules.get("matchAll") is True
    assert len(saved_rules.get("rules", [])) == 1
    rule = saved_rules["rules"][0]
    assert rule["field"] == "bpm"
    assert rule["operator"] == "NumberBetween"
    assert rule["values"] == [120, 130]


def test_add_playlist_in_folder(lexicon):
    """Creating a playlist inside a folder should work."""
    tree = lexicon.playlists.list()
    assert tree is not None
    children = tree.get("playlists", [])
    folder = next(c for c in children if c.get("name") == "IntTest Folder")
    result = lexicon.playlists.add(
        "IntTest Nested", playlist_type="playlist", parent_id=folder["id"]
    )
    assert result is not None


def test_list_playlists(lexicon):
    """Listing should return a tree containing our playlists."""
    tree = lexicon.playlists.list()
    assert tree is not None
    children = tree.get("playlists", [])
    names = [c.get("name") for c in children]
    assert "IntTest Folder" in names
    assert "IntTest Playlist" in names


def test_get_playlist(lexicon):
    """Getting a playlist by ID should return its data."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist")
    result = lexicon.playlists.get(playlist["id"])
    assert result is not None
    assert result["name"] == "IntTest Playlist"


def test_update_playlist_name(lexicon):
    """Updating a playlist name should persist."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist")
    result = lexicon.playlists.update(playlist["id"], name="IntTest Playlist Updated")
    assert result is not None
    assert result["name"] == "IntTest Playlist Updated"


def test_update_playlist_position(lexicon):
    """Updating a playlist position should persist."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist Updated")
    result = lexicon.playlists.update(playlist["id"], position=0)
    assert result is not None
    assert result.get("position") == 0


def test_update_playlist_parent(lexicon):
    """Moving a playlist into a folder should persist."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist Updated")
    folder = next(c for c in children if c.get("name") == "IntTest Folder")

    # Move into folder
    result = lexicon.playlists.update(playlist["id"], parent_id=folder["id"])
    assert result is not None
    assert result.get("parentId") == folder["id"]

    # Move back to root
    root = tree["id"]
    result = lexicon.playlists.update(playlist["id"], parent_id=root)
    assert result is not None
    assert result.get("parentId") == root


def test_get_by_path(lexicon):
    """Getting a nested playlist by path should work."""
    result = lexicon.playlists.get_by_path(
        ["IntTest Folder", "IntTest Nested"], playlist_type="playlist"
    )
    assert result is not None
    assert result["name"] == "IntTest Nested"


def test_get_path(lexicon):
    """Getting the path for a nested playlist should return folder names."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    folder = next(c for c in children if c.get("name") == "IntTest Folder")
    nested = next(
        c for c in folder.get("playlists", []) if c.get("name") == "IntTest Nested"
    )
    path = lexicon.playlists.get_path(nested["id"])
    assert path is not None
    assert "IntTest Folder" in path
    assert "IntTest Nested" in path


# --- Playlist Tracks ---


def test_playlist_tracks_add(lexicon, create_audio_file):
    """Adding tracks to a playlist should succeed."""
    # Create some tracks first
    audio1 = create_audio_file("playlist_track1.wav")
    audio2 = create_audio_file("playlist_track2.wav")
    added = lexicon.tracks.add([str(audio1), str(audio2)])
    assert added is not None
    track_ids = [t["id"] for t in added]

    # Get the playlist
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist Updated")

    # Add tracks to playlist
    assert lexicon.playlists.tracks.add(playlist["id"], track_ids) is True


def test_playlist_tracks_list(lexicon):
    """Listing playlist tracks should return the track IDs we added."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist Updated")
    track_ids = lexicon.playlists.tracks.list(playlist["id"])
    assert track_ids is not None
    assert len(track_ids) == 2


def test_playlist_tracks_get(lexicon):
    """Getting playlist tracks should return full track data."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist Updated")
    tracks = lexicon.playlists.tracks.get(playlist["id"])
    assert tracks is not None
    assert len(tracks) == 2
    assert all("id" in t for t in tracks)


def test_playlist_tracks_remove(lexicon):
    """Removing a track from a playlist should reduce the count."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    playlist = next(c for c in children if c.get("name") == "IntTest Playlist Updated")
    track_ids = lexicon.playlists.tracks.list(playlist["id"])
    assert track_ids and len(track_ids) >= 1
    assert lexicon.playlists.tracks.remove(playlist["id"], track_ids[0]) is True
    remaining = lexicon.playlists.tracks.list(playlist["id"])
    assert remaining is not None
    assert len(remaining) == len(track_ids) - 1


# --- Cleanup ---


def test_delete_playlist_tracks(lexicon):
    """Deleting tracks created by playlist tests."""
    tracks = lexicon.tracks.list(fields=["id"])
    if tracks:
        assert lexicon.tracks.delete([t["id"] for t in tracks]) is True


def test_delete_playlists(lexicon):
    """Deleting playlists should remove them."""
    tree = lexicon.playlists.list()
    children = tree.get("playlists", [])
    ids_to_delete = [
        c["id"]
        for c in children
        if c.get("name")
        in ("IntTest Folder", "IntTest Playlist Updated", "IntTest Smartlist")
    ]
    assert lexicon.playlists.delete(ids_to_delete) is True
    remaining = lexicon.playlists.list()
    remaining_names = [c.get("name") for c in remaining.get("playlists", [])]
    assert "IntTest Folder" not in remaining_names
    assert "IntTest Playlist Updated" not in remaining_names
    assert "IntTest Smartlist" not in remaining_names
