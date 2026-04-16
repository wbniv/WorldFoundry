#!/usr/bin/env python3
"""
Update wf-status.md when a plan or investigation doc is written:
  1. Add a row to the correct table body (if not already present)
  2. Replace the LAST CHANGE section
  3. Push wf-status.md to GitHub master as README.md
"""

import re
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def extract_title(text):
    for line in text.splitlines():
        if line.startswith('# '):
            return line[2:].strip()
    return None


def extract_status(text):
    for line in text.splitlines():
        m = re.match(r'\*\*Status:\*\*\s*(.+)', line)
        if m:
            return m.group(1).strip()
    return None


def extract_summary(text, max_chars=200):
    """Return the first substantive paragraph (not a heading, not metadata)."""
    skip = re.compile(
        r'^(#|---|\*\*(Date|Status|Scope|Sources):|```|\||\s*$)'
    )
    paragraphs = []
    buf = []
    for line in text.splitlines():
        if skip.match(line):
            if buf:
                paragraphs.append(' '.join(buf))
                buf = []
        else:
            buf.append(line.strip())
    if buf:
        paragraphs.append(' '.join(buf))

    for p in paragraphs:
        p = p.strip()
        if len(p) > 20:
            # Collapse markdown links to display text, strip pipes (break tables)
            p = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', p)
            p = p.replace('|', '–')
            if len(p) > max_chars:
                p = textwrap.shorten(p, width=max_chars, placeholder=' …')
            return p
    return ''


def default_status(kind):
    return '**Planned**' if kind == 'plans' else '**In progress**'


def make_row(date, title, rel_path, status, summary):
    return f'| {date} | [{title}]({rel_path}) | {status} | {summary} |'


def push_to_github(status_path):
    import base64
    content = base64.b64encode(status_path.read_bytes()).decode()
    sha_result = subprocess.run(
        ['gh', 'api', 'repos/wbniv/WorldFoundry/contents/README.md', '--jq', '.sha'],
        capture_output=True, text=True
    )
    sha = sha_result.stdout.strip()
    cmd = [
        'gh', 'api', 'repos/wbniv/WorldFoundry/contents/README.md',
        '--method', 'PUT',
        '--field', 'message=docs: update README.md [auto]',
        '--field', f'content={content}',
        '--field', 'branch=master',
    ]
    if sha:
        cmd += ['--field', f'sha={sha}']
    subprocess.run(cmd, check=True, capture_output=True)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    repo = Path(__file__).resolve().parent.parent
    status_path = repo / 'wf-status.md'

    # --push-only: just push wf-status.md, no body update
    if sys.argv[1] == '--push-only':
        try:
            push_to_github(status_path)
        except Exception as e:
            print(f'warning: GitHub push failed: {e}', file=sys.stderr)
        return

    doc_path = Path(sys.argv[1]).resolve()

    # Determine kind and relative path
    try:
        rel = doc_path.relative_to(repo)
    except ValueError:
        sys.exit(0)

    parts = rel.parts
    if len(parts) < 2 or parts[0] != 'docs' or parts[1] not in ('plans', 'investigations', 'reference'):
        sys.exit(0)

    kind = parts[1]   # 'plans', 'investigations', or 'reference'
    rel_path = str(rel)

    # Read the doc
    try:
        doc_text = doc_path.read_text()
    except FileNotFoundError:
        sys.exit(0)

    title = extract_title(doc_text) or doc_path.stem
    raw_status = extract_status(doc_text)
    status = f'**{raw_status}**' if raw_status else default_status(kind)
    summary = extract_summary(doc_text)

    # Extract date from filename (YYYY-MM-DD-slug.md)
    m = re.match(r'(\d{4}-\d{2}-\d{2})', doc_path.stem)
    date = m.group(1) if m else datetime.now().strftime('%Y-%m-%d')

    # ── update body ──────────────────────────────────────────────────────────
    content = status_path.read_text()

    if kind == 'plans':
        section_header = '## Plans'
        col_header = 'Plan'
    elif kind == 'investigations':
        section_header = '## Investigations'
        col_header = 'Investigation'
    else:
        section_header = '## Reference'
        col_header = 'Document'

    # Only add if not already present
    if rel_path not in content:
        if kind == 'reference':
            # Reference table has no Status column
            new_row = f'| {date} | [{title}]({rel_path}) | {summary} |'
            pattern = (
                r'(' + re.escape(section_header) + r'\n\n'
                r'\| Date \| ' + re.escape(col_header) + r' \| Summary \|\n'
                r'\|[-| ]+\|\n'
                r')'
            )
        else:
            new_row = make_row(date, title, rel_path, status, summary)
            pattern = (
                r'(' + re.escape(section_header) + r'\n\n'
                r'\| Date \| ' + re.escape(col_header) + r' \| Status \| Summary \|\n'
                r'\|[-| ]+\|\n'
                r')'
            )

        def insert_row(m):
            return m.group(1) + new_row + '\n'

        new_content = re.sub(pattern, insert_row, content)
        if new_content == content:
            # Fallback: couldn't find table header — just leave body alone
            pass
        else:
            content = new_content

    # ── update LAST CHANGE ───────────────────────────────────────────────────
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    last_change = (
        f'\n## Last Change\n\n'
        f'**{now}** — [`{rel_path}`]({rel_path}): {title}\n'
    )
    # Remove existing LAST CHANGE section and everything after
    content = re.sub(r'\n## Last Change\b.*', '', content, flags=re.DOTALL)
    content = content.rstrip() + '\n' + last_change

    status_path.write_text(content)

    # ── push to GitHub ───────────────────────────────────────────────────────
    try:
        push_to_github(status_path)
    except Exception as e:
        print(f'warning: GitHub push failed: {e}', file=sys.stderr)


if __name__ == '__main__':
    main()
