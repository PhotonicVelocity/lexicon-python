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
# scripts/update_control_actions.py. Do not edit by hand. The spec can be ahead of the released
# app, so a name here can be one the running Lexicon rejects; see docs/api-issues.md.
ControlAction = Literal[
{names}
]
CONTROL_ACTIONS: tuple[ControlAction, ...] = get_args(ControlAction)
'''


def main() -> None:
    spec = yaml.safe_load(SPEC.read_text())
    names = spec["components"]["schemas"]["Control Actions"]["enum"]
    OUTPUT.write_text(TEMPLATE.format(names="\n".join(f'    "{n}",' for n in names)))
    print(f"Wrote {len(names)} actions to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
