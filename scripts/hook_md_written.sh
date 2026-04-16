#!/bin/sh
# PostToolUse hook: when a plan/investigation doc is written, update wf-status.md
# (add body row + LAST CHANGE) and push as README.md to GitHub master.
# When wf-status.md itself is directly edited, just push it.
INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
REPO="$(cd "$(dirname "$0")/.." && pwd)"

if echo "$FILE" | grep -qE 'docs/(plans|investigations)/[^/]+\.md$'; then
    python3 "$REPO/scripts/update_wf_status.py" "$FILE"
fi

if echo "$FILE" | grep -qE 'wf-status\.md$'; then
    python3 "$REPO/scripts/update_wf_status.py" --push-only
fi
