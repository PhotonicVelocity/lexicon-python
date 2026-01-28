import logging
import sys
import types
import unittest
from pathlib import Path

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.tools.playlists import choose_playlist, get_path_from_tree  # noqa: E402


logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stdout,
    force=True,
)


def _install_fake_inquirer(selections):
    module = types.ModuleType("InquirerPy")
    resolver = types.ModuleType("InquirerPy.resolver")
    calls = {"index": 0}

    def prompt(_questions):
        value = selections[calls["index"]]
        calls["index"] += 1
        return value

    resolver.prompt = prompt
    module.resolver = resolver
    sys.modules["InquirerPy"] = module
    sys.modules["InquirerPy.resolver"] = resolver
    return calls


class ToolsPlaylistsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = {
            "id": 1,
            "name": "ROOT",
            "type": "1",
            "playlists": [
                {
                    "id": 10,
                    "name": "Folder",
                    "type": "1",
                    "playlists": [
                        {"id": 11, "name": "Playlist A", "type": "2", "playlists": []},
                    ],
                },
                {"id": 20, "name": "Smart", "type": "3", "playlists": []},
            ],
        }

    def tearDown(self) -> None:
        sys.modules.pop("InquirerPy", None)
        sys.modules.pop("InquirerPy.resolver", None)

    def test_get_path_from_tree_invalid_id(self):
        self.assertIsNone(get_path_from_tree(self.tree, 0))
        self.assertIsNone(get_path_from_tree(self.tree, -1))
        self.assertIsNone(get_path_from_tree(self.tree, "nope"))  # type: ignore[arg-type]

    def test_get_path_from_tree_found(self):
        path = get_path_from_tree(self.tree, 11)
        self.assertEqual(path, ["Folder", "Playlist A"])

    def test_get_path_from_tree_not_found(self):
        self.assertIsNone(get_path_from_tree(self.tree, 999))

    def test_get_path_from_tree_name_not_str(self):
        tree = {
            "id": 1,
            "name": None,
            "type": "1",
            "playlists": [{"id": 2, "name": "Child", "type": "2", "playlists": []}],
        }
        self.assertEqual(get_path_from_tree(tree, 2), ["Child"])

    def test_get_path_from_tree_children_not_list(self):
        tree = {
            "id": 1,
            "name": "ROOT",
            "type": "1",
            "playlists": "nope",
        }
        self.assertIsNone(get_path_from_tree(tree, 2))

    def test_get_path_from_tree_child_not_dict(self):
        tree = {
            "id": 1,
            "name": "ROOT",
            "type": "1",
            "playlists": ["bad"],
        }
        self.assertIsNone(get_path_from_tree(tree, 2))

    def test_choose_playlist_cancel(self):
        _install_fake_inquirer([{"selection": ("cancel", None)}])
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_select_current(self):
        _install_fake_inquirer([{"selection": ("select", self.tree)}])
        self.assertEqual(choose_playlist(self.tree), self.tree)

    def test_choose_playlist_folder_then_item(self):
        _install_fake_inquirer(
            [
                {"selection": ("folder", self.tree["playlists"][0])},
                {"selection": ("item", self.tree["playlists"][0]["playlists"][0])},
            ]
        )
        result = choose_playlist(self.tree)
        self.assertEqual(result["id"], 11)

    def test_choose_playlist_invalid_selection_tuple(self):
        _install_fake_inquirer([{"selection": None}])
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_invalid_selection_pops_stack(self):
        _install_fake_inquirer(
            [
                {"selection": ("folder", self.tree["playlists"][0])},
                {"selection": None},
                {"selection": ("cancel", None)},
            ]
        )
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_non_dict_result(self):
        _install_fake_inquirer(["cancel"])
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_jump(self):
        _install_fake_inquirer(
            [
                {"selection": ("folder", self.tree["playlists"][0])},
                {"selection": ("jump", 0)},
                {"selection": ("item", self.tree["playlists"][1])},
            ]
        )
        result = choose_playlist(self.tree)
        self.assertEqual(result["id"], 20)

    def test_choose_playlist_select_invalid_payload(self):
        _install_fake_inquirer([{"selection": ("select", "nope")}])
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_item_invalid_payload(self):
        _install_fake_inquirer([{"selection": ("item", "nope")}])
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_jump_invalid_payload(self):
        _install_fake_inquirer(
            [
                {"selection": ("jump", "nope")},
                {"selection": ("cancel", None)},
            ]
        )
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_folder_invalid_payload(self):
        _install_fake_inquirer(
            [
                {"selection": ("folder", "nope")},
                {"selection": ("cancel", None)},
            ]
        )
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_current_without_id(self):
        tree = {
            "id": None,
            "name": "Root",
            "type": "1",
            "playlists": [{"id": 2, "name": "Child", "type": "2", "playlists": []}],
        }
        _install_fake_inquirer([{"selection": ("item", tree["playlists"][0])}])
        result = choose_playlist(tree)
        self.assertEqual(result["id"], 2)

    def test_choose_playlist_unknown_action_falls_through(self):
        _install_fake_inquirer(
            [
                {"selection": ("noop", None)},
                {"selection": ("cancel", None)},
            ]
        )
        self.assertIsNone(choose_playlist(self.tree))

    def test_choose_playlist_child_not_dict(self):
        tree = dict(self.tree)
        tree["playlists"] = ["bad-child"]
        _install_fake_inquirer([{"selection": ("cancel", None)}])
        self.assertIsNone(choose_playlist(tree))

    def test_choose_playlist_leaf_returns_current(self):
        tree = {"id": 99, "name": "Leaf", "type": "2", "playlists": []}
        _install_fake_inquirer([])
        self.assertEqual(choose_playlist(tree), tree)

    def test_get_path_from_tree_without_root(self):
        tree = {
            "id": 5,
            "name": "Library",
            "type": "1",
            "playlists": [{"id": 6, "name": "Child", "type": "2", "playlists": []}],
        }
        self.assertEqual(get_path_from_tree(tree, 6), ["Library", "Child"])


if __name__ == "__main__":
    unittest.main()
