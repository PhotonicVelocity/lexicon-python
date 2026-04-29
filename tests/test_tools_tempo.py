import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.tools.tempo import beats_to_seconds, seconds_to_beats  # noqa: E402


class SecondsToBeatsTests(unittest.TestCase):
    def test_first_marker_is_beat_zero(self):
        markers = [{"startTime": 2.5, "bpm": 120.0}]
        self.assertEqual(seconds_to_beats(2.5, markers), 0.0)

    def test_constant_tempo_segment(self):
        markers = [{"startTime": 0.0, "bpm": 120.0}]
        # 1 second at 120 BPM = 2 beats
        self.assertAlmostEqual(seconds_to_beats(1.0, markers), 2.0)

    def test_multi_segment(self):
        # 2s @ 120 BPM (= 4 beats), then jumps to 60 BPM
        markers = [
            {"startTime": 0.0, "bpm": 120.0},
            {"startTime": 2.0, "bpm": 60.0},
        ]
        # at t=4s: 4 beats from segment 1 + 2 seconds @ 60 BPM = 4 + 2 = 6 beats
        self.assertAlmostEqual(seconds_to_beats(4.0, markers), 6.0)

    def test_past_last_marker_uses_last_bpm(self):
        markers = [
            {"startTime": 0.0, "bpm": 120.0},
            {"startTime": 2.0, "bpm": 60.0},
        ]
        # at t=10s: 4 + 8 seconds @ 60 BPM = 4 + 8 = 12 beats
        self.assertAlmostEqual(seconds_to_beats(10.0, markers), 12.0)

    def test_before_first_marker_extrapolates(self):
        # First marker at t=2s with 120 BPM. At t=0s: -2 seconds × 120/60 = -4 beats
        markers = [{"startTime": 2.0, "bpm": 120.0}]
        self.assertAlmostEqual(seconds_to_beats(0.0, markers), -4.0)

    def test_unsorted_markers_get_sorted(self):
        markers = [
            {"startTime": 2.0, "bpm": 60.0},
            {"startTime": 0.0, "bpm": 120.0},
        ]
        self.assertAlmostEqual(seconds_to_beats(4.0, markers), 6.0)

    def test_no_markers_raises(self):
        with self.assertRaises(ValueError):
            seconds_to_beats(1.0, [])


class BeatsToSecondsTests(unittest.TestCase):
    def test_round_trip(self):
        markers = [
            {"startTime": 2.5, "bpm": 100.0},
            {"startTime": 50.0, "bpm": 120.5},
            {"startTime": 90.0, "bpm": 90.0},
        ]
        for s in (2.5, 10.0, 50.0, 60.0, 100.0, 200.0):
            beats = seconds_to_beats(s, markers)
            self.assertAlmostEqual(beats_to_seconds(beats, markers), s, places=8)

    def test_negative_beats_extrapolates_back(self):
        markers = [{"startTime": 2.0, "bpm": 120.0}]
        # -4 beats at 120 BPM = -2 seconds back from 2.0 = 0.0
        self.assertAlmostEqual(beats_to_seconds(-4.0, markers), 0.0)

    def test_no_markers_raises(self):
        with self.assertRaises(ValueError):
            beats_to_seconds(0.0, [])


if __name__ == "__main__":
    unittest.main()
