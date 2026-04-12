"""Integration tests for tag and tag category operations."""

import pytest

pytestmark = pytest.mark.integration


# --- Tag Categories ---


def test_add_category(lexicon):
    """Creating a tag category should return the category with an ID."""
    result = lexicon.tags.categories.add("Integration Category")
    assert result is not None
    assert "id" in result
    assert result["label"] == "Integration Category"


def test_add_category_with_color(lexicon):
    """Creating a category with a color should persist the color."""
    result = lexicon.tags.categories.add("Integration Color Cat", color="blue")
    assert result is not None
    assert result["label"] == "Integration Color Cat"


def test_list_categories(lexicon):
    """Listing categories should include the ones we created."""
    categories = lexicon.tags.categories.list()
    assert categories is not None
    labels = [c["label"] for c in categories]
    assert "Integration Category" in labels
    assert "Integration Color Cat" in labels


def test_update_category_label(lexicon):
    """Updating a category label should persist."""
    categories = lexicon.tags.categories.list()
    category = next(c for c in categories if c["label"] == "Integration Category")
    result = lexicon.tags.categories.update(
        category["id"], label="Integration Cat Updated"
    )
    assert result is not None
    assert result["label"] == "Integration Cat Updated"


def test_update_category_color(lexicon):
    """Updating a category color should persist."""
    categories = lexicon.tags.categories.list()
    category = next(c for c in categories if c["label"] == "Integration Cat Updated")
    result = lexicon.tags.categories.update(category["id"], color="red")
    assert result is not None
    assert result.get("color") == "#e60f0d"


def test_delete_category(lexicon):
    """Deleting a category should remove it."""
    categories = lexicon.tags.categories.list()
    category = next(c for c in categories if c["label"] == "Integration Color Cat")
    assert lexicon.tags.categories.delete(category["id"]) is True
    remaining = lexicon.tags.categories.list()
    remaining_labels = [c["label"] for c in remaining]
    assert "Integration Color Cat" not in remaining_labels


# --- Tags ---


def test_add_tag(lexicon):
    """Creating a tag should return the tag with an ID."""
    categories = lexicon.tags.categories.list()
    category = next(c for c in categories if c["label"] == "Integration Cat Updated")
    result = lexicon.tags.add(category["id"], "IntTest Tag A")
    assert result is not None
    assert "id" in result
    assert result["label"] == "IntTest Tag A"


def test_add_second_tag(lexicon):
    """Adding another tag to the same category."""
    categories = lexicon.tags.categories.list()
    category = next(c for c in categories if c["label"] == "Integration Cat Updated")
    result = lexicon.tags.add(category["id"], "IntTest Tag B")
    assert result is not None
    assert result["label"] == "IntTest Tag B"


def test_list_tags(lexicon):
    """Listing tags should include the ones we created."""
    tags = lexicon.tags.list()
    assert tags is not None
    labels = [t["label"] for t in tags]
    assert "IntTest Tag A" in labels
    assert "IntTest Tag B" in labels


def test_update_tag_label(lexicon):
    """Updating a tag label should persist."""
    tags = lexicon.tags.list()
    tag = next(t for t in tags if t["label"] == "IntTest Tag B")
    result = lexicon.tags.update(tag["id"], label="IntTest Tag B Updated")
    assert result is not None
    assert result["label"] == "IntTest Tag B Updated"


def test_update_tag_position(lexicon):
    """Adding a third tag and moving it to position 0 should persist."""
    categories = lexicon.tags.categories.list()
    category = next(c for c in categories if c["label"] == "Integration Cat Updated")
    tag = lexicon.tags.add(category["id"], "IntTest Tag C")
    assert tag is not None

    # Position must not already be occupied by another tag in the category
    result = lexicon.tags.update(tag["id"], position=99)
    assert result is not None
    assert result.get("position") == 99


def test_update_tag_category(lexicon):
    """Moving a tag to a different category should persist."""
    categories = lexicon.tags.categories.list()
    tags = lexicon.tags.list()
    tag = next(t for t in tags if t["label"] == "IntTest Tag B Updated")
    original_category = tag["categoryId"]

    # Move to a default category (Genre always exists in a fresh library)
    target = next(c for c in categories if c["label"] == "Genre")
    result = lexicon.tags.update(tag["id"], category_id=target["id"])
    assert result is not None
    assert result["categoryId"] == target["id"]
    assert result["categoryId"] != original_category

    # Move it back
    result = lexicon.tags.update(tag["id"], category_id=original_category)
    assert result is not None
    assert result["categoryId"] == original_category


def test_tag_track(lexicon, create_audio_file):
    """Tagging a track should persist the tag IDs on the track."""
    # Add a track
    audio = create_audio_file("tag_test_track.wav")
    added = lexicon.tracks.add([str(audio)])
    assert added is not None
    track_id = added[0]["id"]

    # Get tag ID
    tags = lexicon.tags.list()
    tag = next(t for t in tags if t["label"] == "IntTest Tag A")

    # Tag the track
    result = lexicon.tracks.update(track_id, edits={"tags": [tag["id"]]})
    assert result is not None
    assert tag["id"] in result.get("tags", [])


def test_add_tags_helper(lexicon):
    """add_tags should append without removing existing tags."""
    tracks = lexicon.tracks.list(fields=["id", "tags"])
    tagged = next(t for t in tracks if t.get("tags"))
    existing_tag = tagged["tags"][0]

    tags = lexicon.tags.list()
    other_tag = next(
        t for t in tags if t["id"] != existing_tag and t["label"].startswith("IntTest")
    )
    result = lexicon.tracks.add_tags(tagged["id"], other_tag["id"])
    assert result is not None
    assert existing_tag in result.get("tags", [])
    assert other_tag["id"] in result.get("tags", [])


def test_remove_tags_helper(lexicon):
    """remove_tags should remove one tag without affecting others."""
    tracks = lexicon.tracks.list(fields=["id", "tags"])
    tagged = next(t for t in tracks if len(t.get("tags", [])) >= 2)
    tag_to_remove = tagged["tags"][0]
    tag_to_keep = tagged["tags"][1]

    result = lexicon.tracks.remove_tags(tagged["id"], tag_to_remove)
    assert result is not None
    assert tag_to_remove not in result.get("tags", [])
    assert tag_to_keep in result.get("tags", [])


def test_untag_track(lexicon):
    """Removing all tags from a track should clear them."""
    tracks = lexicon.tracks.list(fields=["id", "tags"])
    tagged = next(t for t in tracks if t.get("tags"))
    result = lexicon.tracks.update(tagged["id"], edits={"tags": []})
    assert result is not None
    assert result.get("tags") == []


def test_delete_tag(lexicon):
    """Deleting a tag should remove it."""
    tags = lexicon.tags.list()
    tag = next(t for t in tags if t["label"] == "IntTest Tag B Updated")
    assert lexicon.tags.delete(tag["id"]) is True
    remaining = lexicon.tags.list()
    remaining_labels = [t["label"] for t in remaining]
    assert "IntTest Tag B Updated" not in remaining_labels


def test_cleanup_tags(lexicon):
    """Delete all IntTest tags, categories, and tracks created by tag tests."""
    # Delete test tags
    tags = lexicon.tags.list()
    if tags:
        test_tags = [t for t in tags if t["label"].startswith("IntTest")]
        if test_tags:
            assert lexicon.tags.delete([t["id"] for t in test_tags]) is True

    # Delete test categories
    categories = lexicon.tags.categories.list()
    if categories:
        test_cats = [c for c in categories if c["label"].startswith("Integration")]
        for cat in test_cats:
            assert lexicon.tags.categories.delete(cat["id"]) is True

    # Delete test tracks
    tracks = lexicon.tracks.list(fields=["id"])
    if tracks:
        assert lexicon.tracks.delete([t["id"] for t in tracks]) is True
