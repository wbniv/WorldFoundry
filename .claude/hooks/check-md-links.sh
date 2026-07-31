#!/usr/bin/env bash
# PostToolUse hook: warn when .md files contain bare paths or URLs that should be links.
# Catches: bare relative .md paths, bare http/https URLs not already in [...](url).
# Fires after Edit/Write. Reads JSON from stdin.

set -euo pipefail

input=$(cat)
file=$(echo "$input" | jq -r '.tool_input.file_path // empty')

[[ "$file" == *.md ]] || exit 0
[[ -f "$file" ]] || exit 0

bare=$(python3 - "$file" <<'PYEOF'
import re, sys

raw = open(sys.argv[1]).read()

# Strip fenced code blocks and inline code spans so we don't flag examples.
# Replace their contents with spaces (preserving offsets isn't needed — we
# just need them absent from the search text).
text = re.sub(r'```.*?```', lambda m: ' ' * len(m.group()), raw, flags=re.DOTALL)
text = re.sub(r'`[^`\n]+`', lambda m: ' ' * len(m.group()), text)

# Strip complete markdown links [text](url) so neither half is mistaken for a
# bare path/URL. A perfectly-good [docs/foo.md](docs/foo.md) link carries the
# path in BOTH halves; only the URL half was being skipped below, so the text
# half ([docs/foo.md]) was false-flagged as bare. Runs after the code-span strip
# so backtick-wrapped link text like [`docs/foo.md`](url) is already blanked.
text = re.sub(r'\[[^\]\n]*\]\([^)\n]*\)', lambda m: ' ' * len(m.group()), text)

found = []

# --- 1. Bare relative .md paths ---
for m in re.finditer(
    r'((?:\.\.?/|docs/|wflevels/|wfsource/|engine/|tests/|wftools/)'
    r'[^\s`"<>()]+\.md)',
    text
):
    path = m.group(1)
    start = m.start(1)
    preceding = text[max(0, start - 30): start]
    if re.search(r'\]\([^)]*$', preceding):
        continue
    found.append(path)

# --- 2. Bare http/https URLs ---
for m in re.finditer(r'https?://\S+', text):
    url = m.group(0).rstrip('.,;)')
    start = m.start()
    preceding = text[max(0, start - 30): start]
    if re.search(r'\]\([^)]*$', preceding):
        continue
    if text[max(0, start-1):start] == '<':
        continue
    found.append(url)

if found:
    unique = sorted(set(found))
    lines = ["WARNING: bare links in " + sys.argv[1] + " — wrap in markdown [text](url):"]
    lines += ["  " + p for p in unique]
    print('\n'.join(lines))
PYEOF
)

if [[ -n "$bare" ]]; then
    python3 -c "
import json, sys
msg = sys.stdin.read().strip()
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': msg}}))
" <<< "$bare"
fi

exit 0
