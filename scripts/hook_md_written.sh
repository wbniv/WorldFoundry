#!/bin/sh
# PostToolUse hook: update wf-status.md LAST CHANGE section when a plan/investigation doc changes.
INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

if echo "$FILE" | grep -qE 'docs/(plans|investigations)/[^/]+\.md$'; then
    STATUS="/home/will/WorldFoundry/wf-status.md"
    RELFILE=$(echo "$FILE" | sed 's|.*/WorldFoundry/||')
    TITLE=$(grep '^# ' "$FILE" 2>/dev/null | head -1 | sed 's/^# //')
    DATE=$(date '+%Y-%m-%d %H:%M')

    # Remove existing LAST CHANGE section and everything after it
    sed -i '/^## Last Change$/,$d' "$STATUS"

    # Append new LAST CHANGE section
    printf '\n## Last Change\n\n**%s** — [`%s`](%s)' "$DATE" "$RELFILE" "$RELFILE" >> "$STATUS"
    if [ -n "$TITLE" ]; then
        printf ': %s' "$TITLE" >> "$STATUS"
    fi
    printf '\n' >> "$STATUS"
fi
