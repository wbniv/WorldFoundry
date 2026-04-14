---
name: audit-pdf
description: This skill should be used when the user wants to generate (or regenerate) a visual diff audit PDF of the current working tree against a baseline git revision — front matter lists fully-deleted files in columns, body shows every modified-but-still-live file with removed lines/tokens struck through. Use when the user says "generate audit pdf", "regenerate the audit", "audit pdf", or anything similar in the context of reviewing a large sweep of deletions.
---

# Audit PDF

Generate a 4-up landscape PDF the user can sight-review to validate a large code sweep.

## When to use

The user is auditing a branch that deletes or heavily edits many files (e.g. the drop-dead-renderers plan) and wants a paper-style review artifact: deletions listed in a front-matter index, then every modified file starting in its own column with strikethroughs on removed content.

## Pipeline

Three steps, in order. Do them all — the user wants the PDF open at the end.

1. **Regenerate HTML** from current working tree vs baseline:
   ```bash
   python3 scripts/audit-pdf.py [BASELINE_REV] [OUTPUT_HTML]
   ```
   Defaults: baseline `74d1a47`, output `~/tmp/audit.html`. If the user has specified a different baseline for this branch, pass it. The script prints counts of deleted/modified files.

2. **Render to PDF** with weasyprint (packaged as `weasyprint` on Ubuntu 24.04):
   ```bash
   weasyprint ~/tmp/audit.html ~/tmp/audit-4up.pdf
   ```
   Takes ~30–60s for large sweeps. Output is 16×10in landscape, 4 columns per sheet, 5pt monospace — user confirmed this size/density works for their wide-screen review.

3. **Open in browser** with `xdg-open` (backgrounded, disowned — don't block on it):
   ```bash
   xdg-open ~/tmp/audit-4up.pdf >/dev/null 2>&1 &
   disown
   ```

Report back: sheet count (from `pdfinfo … | grep Pages`), deleted-file count, modified-file count.

## Why these choices

- **`~/tmp/` not `/tmp/`**: Firefox is snap-confined and blocks `/tmp`. User already has this preference recorded.
- **4-up landscape 16×10**: what the user landed on after iterating from 2-up — they review on a wide screen.
- **5pt monospace**: small enough for density, large enough to read. Don't shrink further without asking.
- **weasyprint not Firefox headless**: Firefox headless timed out on the large HTML; weasyprint is deterministic and fast.

## Don't

- Don't regenerate the Python script — it's already at `scripts/audit-pdf.py`. Read it if you need to understand or tweak it, but treat it as the source of truth for layout.
- Don't switch page format, font size, or column count without the user asking. They've dialed this in.
- Don't write to `/tmp/` — snap-confined Firefox can't open it.
