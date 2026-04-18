import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lexicon.tools.tracks import align_tempomarker_bpms  # noqa: E402


class AlignTempomarkerBpmsTests(unittest.TestCase):
    def test_snaps_bpm_to_whole_beat(self):
        # 30 seconds at 120.1 bpm = 60.05 beats — well within 0.1 tolerance.
        markers = [
            {"startTime": 0.0, "bpm": 120.1},
            {"startTime": 30.0, "bpm": 130.0},
        ]
        result = align_tempomarker_bpms(markers)
        # new bpm = 60 beats * 60 / 30 sec = 120
        self.assertEqual(result[0]["bpm"], 120.0)
        # last marker untouched
        self.assertEqual(result[1]["bpm"], 130.0)

    def test_does_not_snap_outside_tolerance(self):
        # 30 seconds at 121 bpm = 60.5 beats. Diff = 0.5, outside default 0.1 tolerance.
        markers = [
            {"startTime": 0.0, "bpm": 121.0},
            {"startTime": 30.0, "bpm": 130.0},
        ]
        result = align_tempomarker_bpms(markers)
        self.assertEqual(result[0]["bpm"], 121.0)

    def test_does_not_move_markers(self):
        markers = [
            {"startTime": 0.0, "bpm": 120.2},
            {"startTime": 30.0, "bpm": 130.0},
        ]
        result = align_tempomarker_bpms(markers)
        self.assertEqual(result[0]["startTime"], 0.0)
        self.assertEqual(result[1]["startTime"], 30.0)

    def test_sorts_by_start_time(self):
        markers = [
            {"startTime": 30.0, "bpm": 130.0},
            {"startTime": 0.0, "bpm": 120.0},
        ]
        result = align_tempomarker_bpms(markers)
        self.assertEqual(result[0]["startTime"], 0.0)
        self.assertEqual(result[1]["startTime"], 30.0)

    def test_does_not_mutate_input(self):
        markers = [
            {"startTime": 0.0, "bpm": 120.2},
            {"startTime": 30.0, "bpm": 130.0},
        ]
        align_tempomarker_bpms(markers)
        self.assertEqual(markers[0]["bpm"], 120.2)

    def test_multiple_markers_chain(self):
        # 0-30s @ ~120bpm (60 beats), 30-60s @ ~100bpm (50 beats)
        markers = [
            {"startTime": 0.0, "bpm": 120.1},
            {"startTime": 30.0, "bpm": 100.05},
            {"startTime": 60.0, "bpm": 90.0},
        ]
        result = align_tempomarker_bpms(markers)
        self.assertEqual(result[0]["bpm"], 120.0)
        self.assertEqual(result[1]["bpm"], 100.0)
        self.assertEqual(result[2]["bpm"], 90.0)  # last unchanged

    def test_custom_tolerance(self):
        # 30s at 121 bpm = 60.5 beats. diff = 0.5, outside default tolerance.
        markers = [
            {"startTime": 0.0, "bpm": 121.0},
            {"startTime": 30.0, "bpm": 130.0},
        ]
        # With tolerance 0.5, 0.5 is within tolerance (<=), should snap to 60 beats.
        result = align_tempomarker_bpms(markers, tolerance=0.5)
        self.assertEqual(result[0]["bpm"], 120.0)

    def test_empty_list(self):
        self.assertEqual(align_tempomarker_bpms([]), [])

    def test_single_marker(self):
        markers = [{"startTime": 0.0, "bpm": 120.0}]
        result = align_tempomarker_bpms(markers)
        self.assertEqual(result, [{"startTime": 0.0, "bpm": 120.0}])

    def test_zero_duration_segment_skipped(self):
        # Two markers at the same time — skip without modifying.
        markers = [
            {"startTime": 0.0, "bpm": 120.0},
            {"startTime": 0.0, "bpm": 130.0},
        ]
        result = align_tempomarker_bpms(markers)
        self.assertEqual(result[0]["bpm"], 120.0)
        self.assertEqual(result[1]["bpm"], 130.0)


if __name__ == "__main__":
    unittest.main()
