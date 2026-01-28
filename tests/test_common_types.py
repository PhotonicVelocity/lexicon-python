import sys
import unittest
from pathlib import Path

# Ensure src/ is on sys.path so we can import the package without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.resources._common_types import (
    _normalize_color,
    _nearest_color,
    _normalize_id_sequence,
    COLORS,
)


class CommonTypesTests(unittest.TestCase):
    def test_normalize_color_none(self):
        self.assertIsNone(_normalize_color(None))
        self.assertIsNone(_normalize_color("None"))

    def test_normalize_color_named(self):
        self.assertEqual(_normalize_color("red"), "red")

    def test_normalize_color_hex_short(self):
        # #0f0 -> green-ish
        result = _normalize_color("#0f0")
        self.assertIn(result, COLORS)

    def test_normalize_color_hex_with_alpha(self):
        result = _normalize_color("#ff0000ff")
        self.assertIn(result, COLORS)

    def test_normalize_color_hex_invalid(self):
        with self.assertRaises(ValueError):
            _normalize_color("#ggg")

    def test_normalize_color_packed_int(self):
        self.assertIn(_normalize_color(0xFF0000), COLORS)

    def test_normalize_color_packed_int_with_alpha(self):
        self.assertIn(_normalize_color(0x1FF0000), COLORS)

    def test_normalize_color_packed_int_negative(self):
        with self.assertRaises(ValueError):
            _normalize_color(-1)

    def test_normalize_color_rgb_tuple_int(self):
        self.assertIn(_normalize_color((255, 0, 0)), COLORS)

    def test_normalize_color_rgb_tuple_float(self):
        self.assertIn(_normalize_color((1.0, 0.0, 0.0)), COLORS)

    def test_normalize_color_rgb_tuple_invalid(self):
        with self.assertRaises(ValueError):
            _normalize_color(("x", 0, 0))

    def test_normalize_color_invalid_type(self):
        with self.assertRaises(ValueError):
            _normalize_color({})

    def test_nearest_color(self):
        result = _nearest_color((255, 255, 255))
        self.assertEqual(result, "white")

    def test_normalize_id_sequence_single(self):
        self.assertEqual(_normalize_id_sequence(5), [5])

    def test_normalize_id_sequence_sequence(self):
        self.assertEqual(_normalize_id_sequence([1, 2, 2, 0, -1]), [1, 2])

    def test_normalize_id_sequence_invalid(self):
        self.assertIsNone(_normalize_id_sequence("nope"))
        self.assertIsNone(_normalize_id_sequence([0, -1]))
