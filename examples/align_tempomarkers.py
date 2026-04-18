"""Align a track's tempomarker BPMs so markers land on whole beats.

Lexicon's UI requires the user to set the BPM of each tempomarker such that
the next marker lands precisely on a beat boundary of the previous one —
otherwise the beats between markers can drift. Getting this right by ear or
manual math is tedious.

This example uses ``lex.tools.tracks.align_tempomarker_bpms`` to nudge each
marker's BPM so the next marker lands on the closest whole beat, as long as
it's already within the configured tolerance. Marker positions are never
moved — it trusts that the markers are well-placed on the waveform already.

Usage:
    uv run examples/align_tempomarkers.py            # dry run (default)
    uv run examples/align_tempomarkers.py --apply    # actually update tracks
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["lexicon-python"]
# ///

import argparse

from lexicon import Lexicon

# Max fractional-beat distance to snap. 0.2 means "snap if the next marker
# lands within 20% of a whole beat." Larger values catch more misalignment
# but risk nudging markers that were intentionally set to a non-integer
# beat count.
TOLERANCE = 0.2


def main(apply: bool) -> None:
    lex = Lexicon()

    # Pull all tracks with the fields we need. Lexicon's default source is
    # "non-archived" — archived tracks are skipped. We then filter out
    # "incoming" (unprocessed) tracks client-side: the API accepts an
    # "incoming" filter but silently ignores it, so local filtering is the
    # only way to exclude them.
    all_tracks = lex.tracks.list(
        fields=["id", "title", "artist", "incoming", "tempomarkers", "cuepoints"]
    )
    tracks = [
        t
        for t in (all_tracks or [])
        # Skip incoming tracks and tracks with fewer than 2 markers
        # (single-marker tracks have nothing to align to).
        if not t.get("incoming") and len(t.get("tempomarkers") or []) > 1
    ]

    mode = "APPLY" if apply else "DRY RUN"
    print(f"Found {len(tracks)} candidate tracks ({mode})")

    for t in tracks:
        print(f"  [{t['id']}] {t.get('artist', '?')} - {t.get('title', '?')}")
        before = t.get("tempomarkers") or []

        # Analyze each marker against the next. Returns per-marker info:
        # current_beats, target_beats (nearest whole), diff (fractional beats
        # off), and suggested_bpm (what would snap it exactly).
        analysis = lex.tools.tracks.analyze_tempomarker_alignment(before)

        has_snap = False
        for info in analysis:
            diff = info["diff"]
            suggested = info["suggested_bpm"]

            if diff is None or suggested is None:
                # Last marker — no next marker to align to.
                status = "— (last)"
            elif diff <= 1e-9:
                # Essentially zero — already on a whole beat within float precision.
                status = "aligned"
            elif diff <= TOLERANCE:
                # Close enough to snap. Show the proposed new BPM and % change.
                pct = (suggested - info["bpm"]) / info["bpm"] * 100
                status = f"{suggested:g} ({pct:+.3f}%)"
                has_snap = True
            else:
                # Too far off — likely an intentional non-whole-beat marker
                # or a misplaced one that needs manual attention.
                status = f"out of tolerance (diff={diff:.4f} beats)"

            print(f"    t={info['startTime']:10.4f}  {info['bpm']:10.6g} → {status}")

        # Only hit the API in --apply mode, and only if any marker actually
        # qualified for a snap (avoids no-op updates).
        if apply and has_snap:
            aligned = lex.tools.tracks.align_tempomarker_bpms(
                before, tolerance=TOLERANCE
            )
            # Strip to the editable fields — the API only accepts startTime and bpm
            # on tempomarker updates. Other fields (id, trackId) are read-only.
            payload = [
                {"startTime": tm["startTime"], "bpm": tm["bpm"]} for tm in aligned
            ]
            result = lex.tracks.update(t["id"], edits={"tempomarkers": payload})
            print("    ✓ updated" if result else "    ✗ update failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Align tempomarker BPMs so markers land on whole beats."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update tracks. Without this flag, the script only prints the planned changes.",
    )
    args = parser.parse_args()
    main(apply=args.apply)
