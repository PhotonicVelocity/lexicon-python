import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon import color_rgb  # noqa: E402


class ColorRgbTests(unittest.TestCase):
    def test_known_color_returns_rgb(self):
        self.assertEqual(color_rgb("red_dark"), (158, 15, 7))

    def test_white(self):
        self.assertEqual(color_rgb("white"), (255, 255, 255))

    def test_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            color_rgb("not_a_real_color")  # type: ignore[arg-type]
        self.assertIn("Unknown Lexicon color", str(ctx.exception))

    def test_returns_3_tuple_of_ints(self):
        rgb = color_rgb("blue")
        self.assertEqual(len(rgb), 3)
        for component in rgb:
            self.assertIsInstance(component, int)
            self.assertTrue(0 <= component <= 255)


if __name__ == "__main__":
    unittest.main()
