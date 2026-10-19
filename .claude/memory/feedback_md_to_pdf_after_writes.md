---
name: Run md-to-pdf after writing/updating any .md file
description: After any Write/Edit to a markdown file in this repo, run `task md -- <path>` to render and open it; the user expects this every time
type: feedback
originSessionId: 449354b2-8998-486b-a7dd-99e580496376
---
After writing or updating any `.md` file in `/home/will/SRC/WorldFoundry-wbniv`, run `task md -- <path1> [<path2> ...]` (which calls `../python-tui-lib/scripts/md-to-pdf.sh`) without being asked. Multiple files in one invocation is fine and preferred.

**Why:** User expectation; they want to see the rendered output without having to ask each time. Confirmed 2026-04-28 after the user explicitly reminded me ("you're supposed to do this every time you write/update an .md file").

**How to apply:**
- Triggers on any `Write` or `Edit` to `*.md` files inside this repo (docs/, etc.). Includes the README updates.
- Batch multiple files into a single `task md --` invocation when several were written in the same session.
- The Taskfile resolves bare names by searching under `docs/`, so `task md -- omega-race.md` works as well as the full path.
- Output lands in `/home/will/tmp/*.html` and auto-opens in the existing browser.
- Skip only if the user has explicitly said "don't render" or the edit is trivial (e.g. fixing a typo I just made in the same turn before the first render).
- This applies to MEMORY.md and feedback memory files too — they're `.md` — but in practice rendering memory files has no value, so use judgment: only render content the user is going to *read* (docs, briefs, investigations).
