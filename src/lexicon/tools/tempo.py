"""Tempo grid math — convert between seconds and beats given a list of tempomarkers.

Lexicon convention: each tempomarker's BPM applies forward from its ``startTime``
until the next tempomarker (or indefinitely past the last one). The first
tempomarker's ``startTime`` corresponds to beat 0 in this coordinate system.
The choice of beat origin is internal — the round-trip
``beats_to_seconds(seconds_to_beats(t)) == t`` is what callers rely on.
"""

from __future__ import annotations

from typing import Mapping, Sequence

__all__ = ["seconds_to_beats", "beats_to_seconds"]


def _sorted_markers(
    tempomarkers: Sequence[Mapping[str, object]],
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for m in tempomarkers:
        out.append((float(m["startTime"]), float(m["bpm"])))  # type: ignore[arg-type]
    out.sort(key=lambda p: p[0])
    return out


def seconds_to_beats(
    seconds: float, tempomarkers: Sequence[Mapping[str, object]]
) -> float:
    """Convert audio time (seconds) to beats given a tempo grid.

    Beat 0 is at the first tempomarker's ``startTime``. Each tempomarker's BPM
    applies forward to the next tempomarker (or indefinitely past the last).
    Times before the first tempomarker extrapolate using the first BPM.
    """
    markers = _sorted_markers(tempomarkers)
    if not markers:
        raise ValueError("Cannot convert with no tempomarkers")

    if seconds <= markers[0][0]:
        bpm = markers[0][1]
        return (seconds - markers[0][0]) * bpm / 60.0

    beats = 0.0
    for (seg_start, bpm), (seg_end, _) in zip(markers, markers[1:]):
        if seconds <= seg_end:
            return beats + (seconds - seg_start) * bpm / 60.0
        beats += (seg_end - seg_start) * bpm / 60.0

    last_start, last_bpm = markers[-1]
    return beats + (seconds - last_start) * last_bpm / 60.0


def beats_to_seconds(
    beats: float, tempomarkers: Sequence[Mapping[str, object]]
) -> float:
    """Inverse of :func:`seconds_to_beats`. Raises ``ValueError`` if no tempomarkers."""
    markers = _sorted_markers(tempomarkers)
    if not markers:
        raise ValueError("Cannot convert with no tempomarkers")

    if beats <= 0:
        first_start, first_bpm = markers[0]
        return first_start + beats * 60.0 / first_bpm

    cum_beats = 0.0
    for (seg_start, bpm), (seg_end, _) in zip(markers, markers[1:]):
        seg_beats = (seg_end - seg_start) * bpm / 60.0
        if beats <= cum_beats + seg_beats:
            return seg_start + (beats - cum_beats) * 60.0 / bpm
        cum_beats += seg_beats

    last_start, last_bpm = markers[-1]
    return last_start + (beats - cum_beats) * 60.0 / last_bpm
