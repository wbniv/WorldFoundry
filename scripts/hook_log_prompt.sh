#!/bin/sh
# UserPromptSubmit hook: log each user prompt to prompts/YYYY-MM-DD_HH-MM-SS.txt
INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty')
[ -z "$PROMPT" ] && exit 0

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
printf '%s\n' "$PROMPT" > "$REPO/prompts/$TIMESTAMP.txt"
