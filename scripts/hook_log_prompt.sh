#!/bin/sh
# UserPromptSubmit hook: log each user prompt to prompts/YYYY-MM-DD_HH-MM-SS.txt
INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty')
[ -z "$PROMPT" ] && exit 0

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DAY=$(date '+%Y-%m-%d')
TIME=$(date '+%H-%M-%S')
mkdir -p "$REPO/prompts/$DAY"
printf '%s\n' "$PROMPT" > "$REPO/prompts/$DAY/$TIME.txt"
