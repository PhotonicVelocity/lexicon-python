#!/bin/bash
# PostToolUse hook: run `ruff format` on Python files Claude just edited.
# Silent on success; surfaces stderr on actual ruff errors.

FILE_PATH=$(jq -r '.tool_input.file_path // empty' < /dev/stdin)

# No-op if no path or not a .py file.
if [[ -z "$FILE_PATH" || ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

# No-op if the file isn't inside this project (Claude may edit files in
# sibling repos in the same session — don't run lex-py's ruff on them).
case "$FILE_PATH" in
  "$CLAUDE_PROJECT_DIR"/*) ;;
  *) exit 0 ;;
esac

cd "$CLAUDE_PROJECT_DIR" || exit 0

# `uv run --quiet` suppresses uv's resolver/sync chatter; ruff format
# only prints output on errors, so a clean run is silent.
output=$(uv run --quiet ruff format "$FILE_PATH" 2>&1)
status=$?
if [ $status -ne 0 ]; then
  echo "$output" >&2
fi
exit $status
