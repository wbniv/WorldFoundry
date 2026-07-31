#!/usr/bin/env bash
# PostToolUse hook: warn when wf-status.md History entries aren't a single sentence.
# Convention (see the maintainer-note comment at the top of the History section):
# each entry is "**Title (date)** — one sentence." optionally followed by "See [plan](…)".
# Non-blocking: emits a warning back to the model, never fails the edit.
# Fires after Edit/Write. Reads JSON from stdin.

set -euo pipefail

input=$(cat)
file=$(echo "$input" | jq -r '.tool_input.file_path // empty')

[[ "$(basename "$file")" == "wf-status.md" ]] || exit 0
[[ -f "$file" ]] || exit 0

warn=$(python3 - "$file" <<'PYEOF'
import re, sys

lines = open(sys.argv[1], encoding="utf-8").read().split("\n")

# Locate the "## History" section (up to the next "## " header).
start = next((i for i, l in enumerate(lines) if l.strip() == "## History"), None)
if start is None:
    sys.exit(0)
end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))

offenders = []
for l in lines[start:end]:
    if not l.startswith("- "):
        continue
    entry = l[2:]

    s = re.sub(r'`[^`\n]+`', 'x', entry)          # inline code spans -> placeholder
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s) # [text](url) -> text (drops dotted URLs)
    s = s.replace('**', '')                        # bold markers
    s = re.sub(r'\b(?:e\.g|i\.e)\.', 'eg', s)      # neutralize abbreviations
    s = re.split(r'\bSee\s', s)[0]                 # drop the trailing "See [plan](…)" pointer

    # A second sentence = lowercase letter + terminator + space + opening capital.
    # Requiring a lowercase letter before the period skips version/decimal/path dots.
    if re.search(r'[a-z][.!?]\s+["“(]?[A-Z]', s):
        m = re.match(r'\*\*(.*?)\*\*\s*—', entry)
        offenders.append((m.group(1) if m else entry[:60]).strip())

if offenders:
    out = ["WARNING: wf-status.md History entries should be ONE sentence "
           "(see the maintainer note at the top of the section). Multiple sentences detected in:"]
    out += ["  - " + o for o in offenders]
    out.append('Condense each to a single sentence; keep the trailing "See [plan](…)" pointer.')
    print("\n".join(out))
PYEOF
)

if [[ -n "$warn" ]]; then
    python3 -c "
import json, sys
msg = sys.stdin.read().strip()
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': msg}}))
" <<< "$warn"
fi

exit 0
