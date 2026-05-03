# AGENTS

This file captures standing repo-level instructions for work in `lexicon-python`.

## Git Safety

- Do not run destructive git commands unless explicitly requested.
- Do not amend commits unless explicitly requested.
- If unexpected modifications appear, stop and ask before proceeding.

## Branch + Merge Convention

Match the merge style to the commit count on the branch — `--no-ff` everywhere
creates noisy single-commit merge bubbles that clutter `git log`.

- **Single-commit work**: commit directly to `main`, OR use `git merge --ff-only`
  to fast-forward a single-commit branch (no merge commit). The branch existed for
  isolation during work; it doesn't need to be visible in history afterward.
- **Multi-commit work** (e.g. milestones, multi-step refactors): keep the
  `git merge --no-ff` so the branch's commits group under one merge commit.
  The merge bubble carries useful "this work was done as a unit" semantics.

Rule of thumb: if the branch has ≥3 commits, the bubble is worth keeping. 1-2
commits, fast-forward.
