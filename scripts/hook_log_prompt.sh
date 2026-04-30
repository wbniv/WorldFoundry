#!/bin/sh
# UserPromptSubmit hook: append each prompt to docs/transcripts/YYYY-MM-DD.md
INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty')
[ -z "$PROMPT" ] && exit 0

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DAY=$(date '+%Y-%m-%d')
TIME=$(date '+%H:%M:%S')
OUT="$REPO/docs/transcripts/$DAY.md"

mkdir -p "$REPO/docs/transcripts"

# Create file with header if it doesn't exist yet
if [ ! -f "$OUT" ]; then
    printf '# Transcript: %s\n' "$DAY" > "$OUT"
fi

printf '\n## %s\n\n%s\n' "$TIME" "$PROMPT" >> "$OUT"
