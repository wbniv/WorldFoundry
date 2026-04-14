#!/usr/bin/env python3
"""
Generate an audit PDF for the drop-dead-renderers branch.

Output:
  - Front matter: multi-column list of fully-deleted files
  - Body: each modified-but-still-live file, starting on a new logical page,
          with removed lines shown as strikethrough and partial-edit lines
          showing inline (per-token) strikethrough for removed tokens.

Layout: landscape letter, 2 columns per sheet (2-up).  Each "logical page"
        is one column.

Usage: audit-pdf.py [BASELINE_REV] [OUTPUT_HTML]
"""

import difflib
import html
import os
import subprocess
import sys
from pathlib import Path

BASELINE = sys.argv[1] if len(sys.argv) > 1 else "74d1a47"
OUT_HTML = Path(sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/tmp/audit.html"))

REPO = Path(__file__).resolve().parent.parent

# Files to exclude from body even if modified (not code)
EXCLUDE_FROM_BODY = {
    "docs/drop-dead-renderers-plan.md",
}


def git(*args):
    r = subprocess.run(["git", "-C", str(REPO), *args],
                       capture_output=True, check=False)
    return r.stdout.decode("utf-8", errors="replace")


def show(rev, path):
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{path}"],
                       capture_output=True, check=False)
    return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None


def classify():
    """Return (deleted, modified) file lists.  Uses working tree vs BASELINE."""
    deleted, modified = [], []
    for line in git("diff", "--numstat", BASELINE).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add, rem, path = parts
        if path in EXCLUDE_FROM_BODY:
            continue
        full = REPO / path
        if not full.is_file():
            deleted.append(path)
        else:
            try:
                sz = full.stat().st_size
            except OSError:
                continue
            if sz == 0:
                # became empty → exclude from body per user rule
                continue
            base = show(BASELINE, path)
            if base is None or base == "":
                # added file (didn't exist at baseline) → skip
                continue
            modified.append(path)
    deleted.sort()
    modified.sort()
    return deleted, modified


def render_file_body(path):
    """Render one file as a sequence of <div class='line'> elements.

    Kept lines: plain
    Fully-removed baseline lines: full-line strikethrough
    Inline-changed baseline lines: tokens that vanished get <s> wrappers
    """
    base = show(BASELINE, path) or ""
    try:
        cur = (REPO / path).read_text(errors="replace")
    except OSError:
        cur = ""
    base_lines = base.splitlines()
    cur_lines = cur.splitlines()

    out = []
    matcher = difflib.SequenceMatcher(a=base_lines, b=cur_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for ln in base_lines[i1:i2]:
                out.append(f'<div class="line">{html.escape(ln) or "&nbsp;"}</div>')
        elif tag == "delete":
            for ln in base_lines[i1:i2]:
                safe = html.escape(ln) if ln else "&nbsp;"
                out.append(f'<div class="line del-line">{safe}</div>')
        elif tag == "replace":
            b_slice = base_lines[i1:i2]
            c_slice = cur_lines[j1:j2]
            # pair up 1:1; extra baseline lines become pure removals
            n = min(len(b_slice), len(c_slice))
            for k in range(n):
                out.append(render_inline_diff(b_slice[k], c_slice[k]))
            for k in range(n, len(b_slice)):
                ln = b_slice[k]
                safe = html.escape(ln) if ln else "&nbsp;"
                out.append(f'<div class="line del-line">{safe}</div>')
        # "insert" → not in baseline, skip
    return "".join(out)


def render_inline_diff(baseline_line, current_line):
    """Character-level diff: removed tokens get <s>, kept chars plain."""
    cm = difflib.SequenceMatcher(a=baseline_line, b=current_line, autojunk=False)
    parts = []
    for t, bi1, bi2, ci1, ci2 in cm.get_opcodes():
        if t == "equal":
            parts.append(html.escape(baseline_line[bi1:bi2]))
        elif t in ("delete", "replace"):
            gone = baseline_line[bi1:bi2]
            if gone:
                parts.append(f'<span class="del-tok">{html.escape(gone)}</span>')
        # "insert" → new chars not in baseline, skip
    body = "".join(parts) or "&nbsp;"
    return f'<div class="line inline-changed">{body}</div>'


CSS = r"""
@page { size: 16in 10in; margin: 0.25in; }
html, body { margin: 0; padding: 0; }
body {
  font-family: 'Courier New', Courier, monospace;
  font-size: 5pt;
  line-height: 1.12;
  color: #111;
  column-count: 4;
  column-gap: 0.2in;
  column-rule: 1px dashed #999;
}
.col-break { break-before: column; }
.file-header {
  font-weight: 700;
  font-size: 6.5pt;
  margin: 0 0 2pt 0;
  padding: 1.5pt 2.5pt;
  background: #e8e8e8;
  border: 1px solid #888;
  break-after: avoid;
  word-break: break-all;
}
.section-title {
  font-weight: 700;
  font-size: 9pt;
  margin: 0 0 4pt 0;
  padding: 2pt 3pt;
  background: #222;
  color: #fff;
  break-after: avoid;
}
.line { white-space: pre; margin: 0; }
.del-line { color: #888; text-decoration: line-through; background: #fdd; }
.del-tok { text-decoration: line-through; color: #a00; background: #fdd; }
.inline-changed { background: #ffc; }
.deletion-list {
  columns: 2;
  column-gap: 12pt;
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 6pt;
  line-height: 1.2;
}
.deletion-list li { break-inside: avoid; margin: 0; padding: 0 0 0 1pt; }
.legend { font-size: 6pt; margin: 4pt 0; padding: 3pt; border: 1px solid #888; background: #fafafa; }
.legend .del-line, .legend .del-tok { padding: 0 2pt; }
"""


def build_html():
    deleted, modified = classify()
    html_parts = []
    html_parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    html_parts.append(f"<style>{CSS}</style></head><body>")

    # Front matter: deletion list (occupies the first logical page/column)
    html_parts.append(
        f'<div class="section-title">Fully-Deleted Files &mdash; {len(deleted)} files</div>'
    )
    html_parts.append(
        '<div class="legend">'
        'Legend: '
        '<span class="del-line">&nbsp;full-line removal&nbsp;</span> &middot; '
        '<span class="del-tok">&nbsp;token removal&nbsp;</span> '
        'on baseline (commit ' + BASELINE + ') vs current working tree.'
        '</div>'
    )
    html_parts.append('<ul class="deletion-list">')
    for p in deleted:
        html_parts.append(f"<li>{html.escape(p)}</li>")
    html_parts.append("</ul>")

    # Body: each modified file starts in a new column (= new logical page)
    for path in modified:
        html_parts.append('<div class="col-break"></div>')
        html_parts.append(f'<div class="file-header">{html.escape(path)}</div>')
        html_parts.append(render_file_body(path))

    html_parts.append("</body></html>")

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text("\n".join(html_parts))

    return deleted, modified


if __name__ == "__main__":
    d, m = build_html()
    size_kb = OUT_HTML.stat().st_size // 1024
    print(f"Wrote {OUT_HTML} ({size_kb} KB)")
    print(f"  deleted files listed in front matter: {len(d)}")
    print(f"  modified files in body: {len(m)}")
