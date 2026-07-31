---
name: Always link commits in docs
description: When referencing git commits in documentation, always include GitHub links
type: feedback
originSessionId: 31a73a85-ba20-4adc-954e-f320e0df9ce8
---
When a doc references a commit by hash, always include the full GitHub link.

**Why:** User always wants clickable links to referenced commits; bare hashes require manual lookup.

**How to apply:** Format as `[short description](https://github.com/wbniv/WorldFoundry/commit/<hash>)` whenever a commit hash appears in any `.md` file.
