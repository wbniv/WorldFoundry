#!/bin/sh
# PostToolUse hook: update wf-status.md LAST CHANGE section and push as README.md
# to GitHub master whenever a plan/investigation doc or wf-status.md itself is written.
INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

REPO="$(cd "$(dirname "$0")/.." && pwd)"
STATUS="$REPO/wf-status.md"

push_status() {
    SHA=$(gh api repos/wbniv/WorldFoundry/contents/README.md --jq '.sha' 2>/dev/null)
    if [ -n "$SHA" ]; then
        gh api repos/wbniv/WorldFoundry/contents/README.md \
            --method PUT \
            --field message="docs: update README.md [auto]" \
            --field "content=$(base64 -w0 < "$STATUS")" \
            --field sha="$SHA" \
            --field branch=master
    else
        gh api repos/wbniv/WorldFoundry/contents/README.md \
            --method PUT \
            --field message="docs: create README.md [auto]" \
            --field "content=$(base64 -w0 < "$STATUS")" \
            --field branch=master
    fi
}

if echo "$FILE" | grep -qE 'docs/(plans|investigations)/[^/]+\.md$'; then
    RELFILE=$(echo "$FILE" | sed 's|.*/WorldFoundry/||')
    TITLE=$(grep '^# ' "$FILE" 2>/dev/null | head -1 | sed 's/^# //')
    DATE=$(date '+%Y-%m-%d %H:%M')

    sed -i '/^## Last Change$/,$d' "$STATUS"
    printf '\n## Last Change\n\n**%s** — [`%s`](%s)' "$DATE" "$RELFILE" "$RELFILE" >> "$STATUS"
    if [ -n "$TITLE" ]; then
        printf ': %s' "$TITLE" >> "$STATUS"
    fi
    printf '\n' >> "$STATUS"

    push_status
fi

if echo "$FILE" | grep -qE 'wf-status\.md$'; then
    push_status
fi
