---
name: docs/game-ideas/ conversion-brief format
description: WF has an established sibling format for arcade-game design docs (boulder-dash, marble-madness, paperboy, joust). Match it for new briefs.
type: reference
originSessionId: 1bb8f4e2-9146-4504-8289-793c96be779b
---
`docs/game-ideas/<game>.md` is the home for arcade-game-conversion design briefs. Established sibling docs to match: `boulder-dash.md`, `marble-madness.md`, `paperboy.md`, `joust.md`. ~150-200 lines each.

**Required sections, in order:**

1. `# <Game> — World Foundry conversion brief`
2. Hero image: Wikipedia thumb URL (`https://upload.wikimedia.org/wikipedia/en/thumb/<hash>/<filename>/250px-<filename>`) with descriptive alt text and italicized caption.
3. **Bold metadata block:** Original (year, designer, genre), Genre fit (Tier 1/2/3), Closest existing WF level to fork, Scripting language.
4. `## Why this conversion fits` (or "is interesting" / "is the lead pick")
5. `## Level structure` (room graph, table of rooms)
6. `## Camera`
7. `## Movement & physics` (or game-specific equivalent like "Cell model")
8. `## Mailbox protocol` — table mapping symbolic mailbox names to direction (host→script / script→engine / both) and meaning.
9. `## Forth scripts` — 3-4 named subsections (typically Player, Director, plus 1-2 game-specific actors). Each has a `\ comment` block with stack effect comments `( -- f )`.
10. `## Engine work required`
11. `## Verification`
12. `## Risks`

**Conventions:**
- Forth scripts use `\` line comments and stack-effect comments `( -- f )`.
- Mailbox names are referenced by their `INDEXOF_*` constants (auto-loaded from `mailbox.def` as zForth `constant`s).
- Hero image uses `250px-` thumb width.
- Don't add "Phasing" or "Build & run" or "File layout" sections — those belong in implementation PRs, not design briefs.
