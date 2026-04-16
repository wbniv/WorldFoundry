#!/bin/sh
# PostToolUse hook: remind to update wf-status.md when a plan/investigation doc changes.
FILE=$(jq -r '.tool_input.file_path // empty')
if echo "$FILE" | grep -qE 'docs/(plans|investigations)/[^/]+\.md$'; then
    echo "Reminder: update wf-status.md to reflect $FILE" >&2
fi
