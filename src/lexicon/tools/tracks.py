"""Track helper tools."""

from __future__ import annotations

import sys
from typing import Sequence, TypedDict

from lexicon.resources.tracks_types import TempoMarkerResponse

if sys.version_info >= (3, 13):
    from typing import ReadOnly
else:
    from typing_extensions import ReadOnly

__all__ = [
    "TempomarkerAlignment",
    "analyze_tempomarker_alignment",
    "align_tempomarker_bpms",
]


class TempomarkerAlignment(TypedDict):
    """Alignment analysis for a single tempomarker segment.

    Describes how the current marker's BPM relates to the beat position of the
    next marker. Fields are ``None`` on the last marker (nothing to align to).
    """

    startTime: ReadOnly[float]
    bpm: ReadOnly[float]
    current_beats: ReadOnly[float | None]
    target_beats: ReadOnly[int | None]
    diff: ReadOnly[float | None]
    suggested_bpm: ReadOnly[float | None]


def analyze_tempomarker_alignment(
    tempomarkers: Sequence[TempoMarkerResponse],
) -> list[TempomarkerAlignment]:
    """Analyze how well each tempomarker aligns to whole beats.

    For each marker, computes the fractional number of beats between this
    marker and the next using the current marker's BPM, the nearest whole
    beat count, how far off it is (``diff``), and what BPM would snap it
    exactly to that beat boundary.

    Parameters
    ----------
    tempomarkers
        Tempomarkers to analyze.

    Returns
    -------
    list[TempomarkerAlignment]
        One entry per marker, sorted by ``startTime``. The last entry has
        ``None`` for all analysis fields since there is no following marker
        to align to.
    """
    sorted_markers = sorted(tempomarkers, key=lambda tm: tm["startTime"])
    results: list[TempomarkerAlignment] = []

    for i, marker in enumerate(sorted_markers):
        current_beats: float | None = None
        target_beats: int | None = None
        diff: float | None = None
        suggested_bpm: float | None = None

        if i + 1 < len(sorted_markers):
            next_marker = sorted_markers[i + 1]
            dt = next_marker["startTime"] - marker["startTime"]
            if dt > 0:
                current_beats = dt * marker["bpm"] / 60
                target_beats = round(current_beats)
                diff = abs(current_beats - target_beats)
                if target_beats > 0:
                    suggested_bpm = target_beats * 60 / dt

        results.append(
            {
                "startTime": marker["startTime"],
                "bpm": marker["bpm"],
                "current_beats": current_beats,
                "target_beats": target_beats,
                "diff": diff,
                "suggested_bpm": suggested_bpm,
            }
        )

    return results


def align_tempomarker_bpms(
    tempomarkers: Sequence[TempoMarkerResponse],
    tolerance: float = 0.1,
) -> list[dict]:
    """Adjust tempomarker BPMs so consecutive markers land on whole beats.

    Applies ``analyze_tempomarker_alignment`` and snaps a marker's BPM to the
    suggested value when its ``diff`` is within ``tolerance``. No-op snaps
    caused by floating-point noise (``diff`` under ``1e-9``) are skipped.
    Marker positions (``startTime``) are not modified.

    Parameters
    ----------
    tempomarkers
        List of tempomarkers to align.
    tolerance
        Max fractional-beat distance to snap (e.g. ``0.1`` means snap when
        within 10% of a whole beat).

    Returns
    -------
    list[dict]
        New list of tempomarkers with adjusted BPMs, sorted by ``startTime``.
        The last marker is unchanged since there is no following marker to
        align to.
    """
    sorted_markers = sorted(tempomarkers, key=lambda tm: tm["startTime"])
    adjusted: list[dict] = [dict(tm) for tm in sorted_markers]
    analysis = analyze_tempomarker_alignment(sorted_markers)

    for marker, info in zip(adjusted, analysis):
        diff = info["diff"]
        suggested = info["suggested_bpm"]
        if diff is None or suggested is None:
            continue
        if 1e-9 < diff <= tolerance:
            marker["bpm"] = suggested

    return adjusted
