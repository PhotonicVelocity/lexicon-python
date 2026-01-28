"""Playlist helper tools."""

from __future__ import annotations

from typing import Any, cast

from lexicon.resources.playlists_types import PlaylistResponse

def get_path_from_tree(tree: PlaylistResponse, playlist_id: int) -> list[str] | None:
    """Return the playlist path (names) for a given ID within a playlist tree."""
    if not isinstance(playlist_id, int) or playlist_id < 1:
        return None

    def _walk(node: dict[str, object], path: list[str]) -> list[str] | None:
        node_id = node.get("id")
        name = node.get("name")
        if isinstance(name, str):
            path = [*path, name]
        if node_id == playlist_id:
            return path
        children = node.get("playlists")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    found = _walk(cast(dict[str, object], child), path)
                    if found is not None:
                        return found
        return None

    result = _walk(cast(dict[str, object], tree), [])
    if not result:
        return result
    if len(result) > 1 and str(result[0]).upper() == "ROOT":
        return result[1:]
    return result

def choose_playlist(tree: PlaylistResponse) -> dict[str, Any] | None:
    """Interactively choose a playlist/tree item using InquirerPy.

    Parameters
    ----------
    tree
        Playlist tree root node.

    Returns
    -------
    dict | None
        Selected playlist payload, or None if the user cancels.
    """
    try:
        from InquirerPy.resolver import prompt
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("InquirerPy is required for choose_playlist.") from exc

    stack: list[dict[str, Any]] = [cast(dict[str, Any], tree)]

    def _format_selection(playlist: dict[str, Any]) -> str:  # pragma: no cover - unused for now
        playlist_type = str(playlist.get("type"))
        type_label = {
            "1": "Folder",
            "2": "Playlist",
            "3": "Smartlist",
        }.get(playlist_type, "Playlist")
        name = playlist.get("name", "(unnamed)")
        track_ids = playlist.get("trackIds") or []
        track_count = len(set(track_ids)) if isinstance(track_ids, list) else 0
        return f"[{type_label}] {name} ({track_count} tracks)"

    while stack:
        current = stack[-1]
        current_name = current.get("name", "(root)")
        children = current.get("playlists")

        if not isinstance(children, list) or not children:
            return current

        current_indent = "  " * (len(stack) - 1)
        choices: list[dict[str, Any]] = []
        choices.append({"name": " X Cancel", "value": ("cancel", None)})

        for depth, ancestor in enumerate(stack[:-1]):
            ancestor_name = ancestor.get("name", "(unnamed)")
            indent = "  " * depth
            choices.append(
                {
                    "name": f"{indent} V {ancestor_name}",
                    "value": ("jump", depth),
                }
            )

        if current.get("id") is not None:
            choices.append(
                {
                    "name": f"{current_indent}>> {current_name} [Select] <<",
                    "value": ("select", current),
                }
            )
        for child in children:
            if not isinstance(child, dict):
                continue
            child_name = child.get("name", "(unnamed)")
            child_type = str(child.get("type"))
            child_indent = "  " * len(stack)
            if child_type == "1":
                choices.append(
                    {
                        "name": f"{child_indent} > {child_name}",
                        "value": ("folder", child),
                    }
                )
            else:
                choices.append(
                    {
                        "name": f"{child_indent}   {child_name}",
                        "value": ("item", child),
                    }
                )

        result = prompt(
            [
                {
                    "type": "fuzzy",
                    "name": "selection",
                    "message": f"Select from {current_name}",
                    "choices": choices,
                }
            ],
        )
        if isinstance(result, dict):
            selection = result.get("selection")
            if not isinstance(selection, tuple) or len(selection) != 2:
                if len(stack) > 1:
                    stack.pop()
                    continue
                return None
            action, payload = selection
        else:
            action, payload = result, None

        if action == "cancel":
            return None
        if action == "jump":
            if isinstance(payload, int):
                stack[:] = stack[: payload + 1]
            continue
        if action == "select":
            if not isinstance(payload, dict):
                return None
            return payload
        if action == "folder":
            if isinstance(payload, dict):
                stack.append(payload)
            continue
        if action == "item":
            if not isinstance(payload, dict):
                return None
            return payload

    return None  # pragma: no cover - defensive fallback
