"""Regenerate src/lexicon/resources/control_types.py from the vendored API spec.

Run with `make update-control-actions` after refreshing docs/lexicon-api-docs.yaml. PyYAML is
needed only here, so the Makefile target supplies it and it stays out of the package dependencies.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "lexicon-api-docs.yaml"
OUTPUT = ROOT / "src" / "lexicon" / "resources" / "control_types.py"

TEMPLATE = '''"""Types for control actions."""

from __future__ import annotations

from typing import Literal, get_args

# Generated from the Control Actions enum in docs/lexicon-api-docs.yaml by
# scripts/update_control_actions.py, plus the DeckConnect_* names Lexicon 1.12 uses for the
# spec's Direct2Cdj_* actions. Do not edit by hand. The list covers several Lexicon versions,
# so a name here can be one the running Lexicon rejects; see docs/api-issues.md.
ControlAction = Literal[
{names}
]
CONTROL_ACTIONS: tuple[ControlAction, ...] = get_args(ControlAction)
'''


# Lexicon 1.12 renamed DIRECT2CDJ to DeckConnect, and its hotkey actions with it: 1.12.0
# answers Direct2Cdj_LoadDeck with "Unknown control action" and accepts DeckConnect_LoadDeck.
# The spec published 2026-11-09 still lists the old names. Both stay in the list so the
# type covers 1.11 and 1.12; the running Lexicon rejects the one it does not know.
RENAMED_PREFIXES = {"Direct2Cdj_": "DeckConnect_"}


def with_renames(names: list[str]) -> list[str]:
    """Insert each renamed action right after the spec name it replaces."""
    result: list[str] = []
    for name in names:
        result.append(name)
        for old, new in RENAMED_PREFIXES.items():
            if name.startswith(old):
                renamed = new + name[len(old) :]
                if renamed not in names:
                    result.append(renamed)
    return result


def main() -> None:
    spec = yaml.safe_load(SPEC.read_text())
    names = with_renames(spec["components"]["schemas"]["Control Actions"]["enum"])
    OUTPUT.write_text(TEMPLATE.format(names="\n".join(f'    "{n}",' for n in names)))
    print(f"Wrote {len(names)} actions to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
