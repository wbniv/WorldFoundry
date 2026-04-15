#!/usr/bin/env python3
"""
loc_report.py — WF codebase LOC and code-analysis report.

Usage:
    # Snapshot current working tree
    python3 scripts/loc_report.py [-o snapshot.json]

    # Snapshot a historic git ref (no checkout needed)
    python3 scripts/loc_report.py --ref 74d1a47 [-o baseline.json]

    # Compare current tree to a saved snapshot
    python3 scripts/loc_report.py --compare baseline.json [-o new.json]

    # Custom root directory
    python3 scripts/loc_report.py [--root wfsource/source]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# File extensions to count
SOURCE_EXTS = {'.cc', '.cpp', '.c', '.hp', '.h', '.hh', '.hpi', '.ht', '.inc'}

# Subsystem directories that are vendored third-party code — excluded from counts.
# audiofmt/ = vendored sox (removed in renderer-drop cleanup)
# regexp/   = Henry Spencer regex 1986
VENDOR_SUBSYSTEMS = {'audiofmt', 'regexp'}

# ---------------------------------------------------------------------------
# Line classification
# ---------------------------------------------------------------------------

def classify_lines(text: str) -> dict:
    """Return dict with blank/comment/code/total counts for a block of text."""
    blank = comment = code = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            blank += 1
        elif (stripped.startswith('//') or stripped.startswith('/*')
              or stripped.startswith('*') or stripped.startswith('#')):
            comment += 1
        else:
            code += 1
    total = blank + comment + code
    return {'blank': blank, 'comment': comment, 'code': code, 'total': total}


def add_counts(a: dict, b: dict) -> dict:
    return {k: a[k] + b[k] for k in ('blank', 'comment', 'code', 'total')}


def zero_counts() -> dict:
    return {'blank': 0, 'comment': 0, 'code': 0, 'total': 0}

# ---------------------------------------------------------------------------
# File discovery — working tree
# ---------------------------------------------------------------------------

def iter_source_files(root: Path):
    """Yield (subsystem, path) pairs for all source files under root."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden dirs and vendor subtrees inside wfsource
        dirnames[:] = [d for d in sorted(dirnames)
                       if not d.startswith('.') and d != 'vendor']
        dp = Path(dirpath)
        for fname in sorted(filenames):
            if Path(fname).suffix in SOURCE_EXTS:
                fpath = dp / fname
                # subsystem = first directory component below root
                try:
                    rel = fpath.relative_to(root)
                    subsystem = rel.parts[0] if len(rel.parts) > 1 else '_root'
                except ValueError:
                    subsystem = '_root'
                if subsystem in VENDOR_SUBSYSTEMS:
                    continue
                yield subsystem, fpath


def count_tree(root: Path) -> dict:
    """Count LOC for all source files under root. Returns subsystem dict."""
    subsystems: dict[str, dict] = {}
    file_counts: dict[str, int] = {}
    for subsystem, fpath in iter_source_files(root):
        try:
            text = fpath.read_text(errors='replace')
        except OSError:
            continue
        counts = classify_lines(text)
        if subsystem not in subsystems:
            subsystems[subsystem] = zero_counts()
            file_counts[subsystem] = 0
        subsystems[subsystem] = add_counts(subsystems[subsystem], counts)
        file_counts[subsystem] += 1

    # Merge file counts into subsystem dicts
    for s in subsystems:
        subsystems[s]['files'] = file_counts[s]
    return subsystems

# ---------------------------------------------------------------------------
# File discovery — git ref (no checkout)
# ---------------------------------------------------------------------------

def git_ls_tree(ref: str, root_rel: str) -> list[str]:
    """Return list of blob paths under root_rel at the given git ref."""
    result = subprocess.run(
        ['git', 'ls-tree', '-r', '--name-only', f'{ref}:{root_rel}'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Try without the subpath (full tree)
        result = subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', ref],
            capture_output=True, text=True
        )
        lines = [l for l in result.stdout.splitlines()
                 if l.startswith(root_rel + '/')]
        return [l[len(root_rel) + 1:] for l in lines]
    return result.stdout.splitlines()


def git_show_file(ref: str, root_rel: str, rel_path: str) -> str | None:
    result = subprocess.run(
        ['git', 'show', f'{ref}:{root_rel}/{rel_path}'],
        capture_output=True, text=True, errors='replace'
    )
    return result.stdout if result.returncode == 0 else None


def count_ref(ref: str, root_rel: str) -> dict:
    """Count LOC for all source files at a git ref. Returns subsystem dict."""
    paths = git_ls_tree(ref, root_rel)
    subsystems: dict[str, dict] = {}
    file_counts: dict[str, int] = {}

    for rel_path in paths:
        parts = Path(rel_path).parts
        if Path(rel_path).suffix not in SOURCE_EXTS:
            continue
        subsystem = parts[0] if len(parts) > 1 else '_root'
        if subsystem in VENDOR_SUBSYSTEMS:
            continue
        text = git_show_file(ref, root_rel, rel_path)
        if text is None:
            continue
        counts = classify_lines(text)
        if subsystem not in subsystems:
            subsystems[subsystem] = zero_counts()
            file_counts[subsystem] = 0
        subsystems[subsystem] = add_counts(subsystems[subsystem], counts)
        file_counts[subsystem] += 1

    for s in subsystems:
        subsystems[s]['files'] = file_counts[s]
    return subsystems

# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------

def compute_total(subsystems: dict) -> dict:
    total = zero_counts()
    total['files'] = 0
    for counts in subsystems.values():
        for k in ('blank', 'comment', 'code', 'total'):
            total[k] += counts[k]
        total['files'] += counts['files']
    return total

# ---------------------------------------------------------------------------
# Current git ref
# ---------------------------------------------------------------------------

def current_git_ref() -> str:
    result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else 'unknown'

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def fmt(n: int) -> str:
    return f'{n:,}'


def fmt_delta(n: int) -> str:
    if n > 0:
        return f'+{n:,}'
    elif n < 0:
        return f'{n:,}'
    return '0'


def print_table(subsystems: dict, total: dict, compare: dict | None = None):
    # Sort subsystems by code LOC descending
    rows = sorted(subsystems.items(), key=lambda x: x[1]['code'], reverse=True)

    compare_total = None
    if compare:
        compare_total = compute_total(compare['subsystems'])

    col_sub  = max(14, max((len(s) for s, _ in rows), default=0) + 2)
    has_delta = compare is not None

    header = (f"{'Subsystem':<{col_sub}} {'Files':>6}  {'Blank':>7}  "
              f"{'Comment':>8}  {'Code':>9}  {'Total':>9}")
    if has_delta:
        header += f"  {'Δ Code':>9}"
    print(header)
    print('-' * len(header))

    for subsystem, counts in rows:
        delta_str = ''
        if has_delta:
            old_code = compare['subsystems'].get(subsystem, {}).get('code', 0)
            delta = counts['code'] - old_code
            delta_str = f'  {fmt_delta(delta):>9}'
        print(f"{subsystem:<{col_sub}} {fmt(counts['files']):>6}  "
              f"{fmt(counts['blank']):>7}  {fmt(counts['comment']):>8}  "
              f"{fmt(counts['code']):>9}  {fmt(counts['total']):>9}{delta_str}")

    print('-' * len(header))
    delta_str = ''
    if has_delta and compare_total:
        delta = total['code'] - compare_total['code']
        delta_str = f'  {fmt_delta(delta):>9}'
    print(f"{'TOTAL':<{col_sub}} {fmt(total['files']):>6}  "
          f"{fmt(total['blank']):>7}  {fmt(total['comment']):>8}  "
          f"{fmt(total['code']):>9}  {fmt(total['total']):>9}{delta_str}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='WF LOC report')
    parser.add_argument('--root', default='wfsource/source',
                        help='Source root relative to repo (default: wfsource/source)')
    parser.add_argument('--ref', default=None,
                        help='Git ref to count (no checkout needed)')
    parser.add_argument('-o', '--output', default=None, metavar='FILE',
                        help='Write JSON snapshot to FILE')
    parser.add_argument('--compare', default=None, metavar='FILE',
                        help='Compare against a prior JSON snapshot')
    args = parser.parse_args()

    root_rel = args.root.rstrip('/')

    # Load comparison snapshot
    compare_snapshot = None
    if args.compare:
        with open(args.compare) as f:
            compare_snapshot = json.load(f)
        print(f"Comparing against: {args.compare}  "
              f"(ref={compare_snapshot.get('ref','?')}, "
              f"date={compare_snapshot.get('date','?')})")
        print()

    # Count
    if args.ref:
        ref = args.ref
        print(f"Counting ref {ref}:{root_rel} ...", file=sys.stderr)
        subsystems = count_ref(ref, root_rel)
    else:
        ref = current_git_ref()
        repo_root = Path(subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True).stdout.strip())
        root_path = repo_root / root_rel
        print(f"Counting {root_path} (HEAD={ref}) ...", file=sys.stderr)
        subsystems = count_tree(root_path)

    total = compute_total(subsystems)

    # Header info
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    print(f"WF LOC report  ref={ref}  root={root_rel}  date={now}")
    print()

    print_table(subsystems, total, compare_snapshot)
    print()

    # Write snapshot
    snapshot = {
        'ref': ref,
        'date': now,
        'root': root_rel,
        'subsystems': subsystems,
        'total': total,
    }

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(snapshot, indent=2))
        print(f"Snapshot written to {out}", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main())
