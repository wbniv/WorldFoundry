#!/usr/bin/env python3
"""Curses TUI for browsing git branches as a chronological waypoint pipeline.

Design: in repos like this one, most branches form a linear chain where each
branch is a strict superset of the prior. Rather than flatten every branch to
`diff vs master`, this tool detects each branch's nearest-ancestor branch
(its parent waypoint) and shows the incremental delta.

Diff modes:
  ENTER on file — diff vs parent waypoint (default)
  m     on file — diff vs master
  c     on branch — mark / compare two branches
"""

import curses
import math
import os
import select
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FileNode:
    name: str
    path: str
    status: str                     # A D M R
    added: Optional[int]            # None = binary
    deleted: Optional[int]
    rename_from: Optional[str] = None

    @property
    def annotation(self) -> str:
        if self.status == 'D':
            return '[D]'
        if self.status == 'A':
            return '[N]'
        if self.status == 'R':
            return '[R]'
        if self.added is None:
            return '[BIN]'
        return f'+{self.added}/-{self.deleted}'


@dataclass
class TreeNode:
    name: str
    full_path: str
    children: dict = field(default_factory=dict)
    expanded: bool = False


@dataclass
class BranchNode:
    display_name: str
    ref: str
    is_local: bool
    is_current: bool = False
    tip_sha: str = ''
    tip_date: str = ''              # ISO 8601 committer date

    # Topology (populated by detect_topology)
    parent: Optional['BranchNode'] = None
    is_sideways: bool = False
    commits_ahead: int = 0
    parent_base: Optional[str] = None   # merge-base(parent, self); diff base

    # Display state
    expanded: bool = False
    loaded: bool = False
    loading: bool = False
    file_tree: Optional[TreeNode] = None
    error: Optional[str] = None


@dataclass
class DisplayRow:
    kind: str    # 'branch' | 'dir' | 'file' | 'loading' | 'empty' | 'error'
    depth: int
    label: str
    annotation: str
    ref: Any
    branch: Any
    # Spine prefix cells: list of (char, attr_flags_without_base).
    # Rendered before indent/content; attr gets ORed with the cursor-highlight
    # base at draw time. Encodes the graph topology: nodes (●◉○◆), connectors
    # (├─) and vertical continuation (│).
    spine_cells: list = field(default_factory=list)


@dataclass
class AppState:
    repo_root: str
    branches: list
    rows: list
    cursor: int
    scroll_offset: int
    notify_pipe_r: int
    notify_pipe_w: int
    master_ref: Optional[str] = None    # resolved once at startup
    compare_mark: Optional[BranchNode] = None
    max_commits_ahead: int = 1
    needs_redraw: bool = True
    message: str = ''                   # transient status message


# ---------------------------------------------------------------------------
# Color pairs
# ---------------------------------------------------------------------------

CP_BRANCH_CURRENT = 1
CP_BRANCH_LOCAL   = 2
CP_BRANCH_REMOTE  = 3
CP_DIR            = 4
CP_FILE_NEW       = 5
CP_FILE_DEL       = 6
CP_FILE_MOD       = 7
CP_FILE_RENAME    = 8
CP_FILE_BINARY    = 9
CP_STATUS_BAR     = 10
CP_DIM            = 11
CP_ERROR          = 12
CP_DIFF_ADD       = 13
CP_DIFF_DEL       = 14
CP_DIFF_HUNK      = 15
CP_DIFF_HEADER    = 16
CP_NORMAL         = 17
CP_SIDEWAYS       = 18
CP_STRATA         = 19
CP_COMPARE_MARK   = 20

_STRIKE_ON  = b''
_STRIKE_OFF = b''


def init_colors():
    global _STRIKE_ON, _STRIKE_OFF
    curses.start_color()
    curses.use_default_colors()
    bg = -1
    curses.init_pair(CP_BRANCH_CURRENT, curses.COLOR_CYAN,    bg)
    curses.init_pair(CP_BRANCH_LOCAL,   curses.COLOR_YELLOW,  bg)
    curses.init_pair(CP_BRANCH_REMOTE,  curses.COLOR_CYAN,    bg)
    curses.init_pair(CP_DIR,            curses.COLOR_BLUE,    bg)
    curses.init_pair(CP_FILE_NEW,       curses.COLOR_GREEN,   bg)
    curses.init_pair(CP_FILE_DEL,       curses.COLOR_RED,     bg)
    curses.init_pair(CP_FILE_MOD,       curses.COLOR_WHITE,   bg)
    curses.init_pair(CP_FILE_RENAME,    curses.COLOR_YELLOW,  bg)
    curses.init_pair(CP_FILE_BINARY,    curses.COLOR_MAGENTA, bg)
    curses.init_pair(CP_STATUS_BAR,     curses.COLOR_BLACK,   curses.COLOR_WHITE)
    curses.init_pair(CP_DIM,            curses.COLOR_WHITE,   bg)
    curses.init_pair(CP_ERROR,          curses.COLOR_RED,     bg)
    curses.init_pair(CP_DIFF_ADD,       curses.COLOR_GREEN,   bg)
    curses.init_pair(CP_DIFF_DEL,       curses.COLOR_RED,     bg)
    curses.init_pair(CP_DIFF_HUNK,      curses.COLOR_CYAN,    bg)
    curses.init_pair(CP_DIFF_HEADER,    curses.COLOR_WHITE,   bg)
    curses.init_pair(CP_NORMAL,         curses.COLOR_WHITE,   bg)
    curses.init_pair(CP_SIDEWAYS,       curses.COLOR_MAGENTA, bg)
    curses.init_pair(CP_STRATA,         curses.COLOR_GREEN,   bg)
    curses.init_pair(CP_COMPARE_MARK,   curses.COLOR_BLACK,   curses.COLOR_YELLOW)
    try:
        _STRIKE_ON  = curses.tigetstr('smxx') or b''
        _STRIKE_OFF = curses.tigetstr('rmxx') or b''
    except Exception:
        pass


def annotation_color(status: str) -> int:
    return {
        'A': curses.color_pair(CP_FILE_NEW),
        'D': curses.color_pair(CP_FILE_DEL),
        'R': curses.color_pair(CP_FILE_RENAME),
        'M': curses.color_pair(CP_FILE_MOD),
    }.get(status, curses.color_pair(CP_FILE_BINARY))


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def get_repo_root() -> str:
    r = _run(['git', 'rev-parse', '--show-toplevel'])
    if r.returncode != 0:
        sys.exit('Not inside a git repository.')
    return r.stdout.strip()


def get_current_branch(root: str) -> Optional[str]:
    r = _run(['git', '-C', root, 'symbolic-ref', '--short', 'HEAD'])
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def resolve_master_ref(root: str) -> Optional[str]:
    for ref in ('master', 'origin/master', 'main', 'origin/main'):
        r = _run(['git', '-C', root, 'rev-parse', '--verify', '--quiet', ref])
        if r.returncode == 0:
            return ref
    return None


def get_all_branches(root: str) -> list:
    r = _run(['git', '-C', root, 'branch', '-a'])
    if r.returncode != 0:
        return []

    seen_short = set()
    branches = []

    lines = r.stdout.splitlines()
    for line in lines:
        stripped = line.strip().lstrip('* ')
        if stripped.startswith('remotes/') or '->' in stripped:
            continue
        if stripped not in seen_short:
            seen_short.add(stripped)
            branches.append(BranchNode(display_name=stripped, ref=stripped, is_local=True))

    for line in lines:
        stripped = line.strip().lstrip('* ')
        if not stripped.startswith('remotes/') or '->' in stripped:
            continue
        short = stripped[len('remotes/'):]
        parts = short.split('/', 1)
        dedup_key = parts[1] if len(parts) == 2 else short
        if dedup_key in seen_short:
            continue
        seen_short.add(dedup_key)
        branches.append(BranchNode(display_name=short, ref=stripped, is_local=False))

    return branches


def _resolve(root: str, ref: str) -> str:
    r = _run(['git', '-C', root, 'rev-parse', ref])
    return r.stdout.strip() if r.returncode == 0 else ''


def _commit_date(root: str, ref: str) -> str:
    r = _run(['git', '-C', root, 'log', '-1', '--format=%cI', ref])
    return r.stdout.strip() if r.returncode == 0 else ''


def _merge_base(root: str, a: str, b: str) -> str:
    r = _run(['git', '-C', root, 'merge-base', a, b])
    return r.stdout.strip() if r.returncode == 0 else ''


def _rev_count(root: str, rng: str) -> int:
    r = _run(['git', '-C', root, 'rev-list', '--count', rng])
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def _is_ancestor(root: str, a: str, b: str) -> bool:
    r = _run(['git', '-C', root, 'merge-base', '--is-ancestor', a, b])
    return r.returncode == 0


# ---------------------------------------------------------------------------
# Topology detection
# ---------------------------------------------------------------------------

def detect_topology(root: str, branches: list) -> int:
    """Populate parent/parent_base/commits_ahead/is_sideways on each branch.
    Returns max commits_ahead (for strata-bar scaling)."""
    for b in branches:
        b.tip_sha  = _resolve(root, b.ref)
        b.tip_date = _commit_date(root, b.ref)

    # Cache pairwise merge-bases to avoid recomputation.
    mb_cache: dict[tuple[str, str], str] = {}

    def mb(a: BranchNode, c: BranchNode) -> str:
        key = (a.tip_sha, c.tip_sha)
        if key not in mb_cache:
            mb_cache[key] = _merge_base(root, a.ref, c.ref)
            mb_cache[(c.tip_sha, a.tip_sha)] = mb_cache[key]
        return mb_cache[key]

    max_ahead = 1
    for b in branches:
        # A candidate parent is a *strict* ancestor of b.
        candidates = []
        for p in branches:
            if p is b or not p.tip_sha or not b.tip_sha:
                continue
            base = mb(p, b)
            if base == p.tip_sha and base != b.tip_sha:
                candidates.append(p)

        if not candidates:
            b.parent = None
            b.parent_base = None
            b.commits_ahead = _rev_count(root, b.tip_sha) if b.tip_sha else 0
            b.is_sideways = False
        else:
            # Nearest ancestor = latest commit date.
            candidates.sort(key=lambda p: p.tip_date, reverse=True)
            parent = candidates[0]
            b.parent = parent
            b.parent_base = parent.tip_sha
            b.commits_ahead = _rev_count(root, f'{parent.tip_sha}..{b.tip_sha}')
            # Sideways: b diverges from some other branch c that also
            # descends from parent (i.e. neither is an ancestor of the other).
            # Linear chain descendants (c is ancestor of b or b is ancestor of c)
            # don't count — that's just the chain continuing.
            b.is_sideways = False
            for c in branches:
                if c is b or c is parent or not c.tip_sha:
                    continue
                if mb(parent, c) != parent.tip_sha:
                    continue
                bc = mb(b, c)
                if bc == b.tip_sha or bc == c.tip_sha:
                    continue
                b.is_sideways = True
                break

        if b.commits_ahead > max_ahead:
            max_ahead = b.commits_ahead

    return max_ahead


def sort_waypoints(branches: list) -> list:
    """Chronological, newest first. Sideways forks grouped immediately under
    their parent (which comes first in the date order)."""
    mainline = [b for b in branches if not b.is_sideways]
    sideways = [b for b in branches if b.is_sideways]
    mainline.sort(key=lambda b: b.tip_date, reverse=True)

    result = []
    sideways_by_parent: dict[str, list] = {}
    for s in sideways:
        key = s.parent.ref if s.parent else ''
        sideways_by_parent.setdefault(key, []).append(s)
    for lst in sideways_by_parent.values():
        lst.sort(key=lambda b: b.tip_date, reverse=True)

    for b in mainline:
        result.append(b)
        result.extend(sideways_by_parent.pop(b.ref, []))
    # Orphan sideways (parent not in mainline): append at end
    for lst in sideways_by_parent.values():
        result.extend(lst)
    return result


# ---------------------------------------------------------------------------
# Branch diff loading
# ---------------------------------------------------------------------------

def parse_name_status(text: str) -> list:
    results = []
    for line in text.splitlines():
        if not line or line.startswith('warning:'):
            continue
        parts = line.split('\t')
        code = parts[0]
        if code.startswith('R') or code.startswith('C'):
            if len(parts) >= 3:
                results.append(('R', parts[2], parts[1]))
        elif len(parts) >= 2:
            results.append((code, parts[1]))
    return results


def parse_numstat(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts[0], parts[1], parts[2]
        if added_s == '-' or deleted_s == '-':
            result[path] = (None, None)
        else:
            try:
                result[path] = (int(added_s), int(deleted_s))
            except ValueError:
                result[path] = (None, None)
    return result


def build_file_tree(entries: list, numstat: dict) -> TreeNode:
    root = TreeNode(name='', full_path='')
    for entry in entries:
        status = entry[0]
        path = entry[1]
        old_path = entry[2] if len(entry) > 2 else None
        added, deleted = numstat.get(path, (None, None))
        file_node = FileNode(
            name=path.split('/')[-1],
            path=path,
            status=status,
            added=added,
            deleted=deleted,
            rename_from=old_path,
        )
        _insert_path(root, path.split('/'), file_node)
    return root


def _insert_path(root: TreeNode, parts: list, file_node: FileNode):
    node = root
    for part in parts[:-1]:
        if part not in node.children:
            parent = node.full_path
            child_path = (parent + '/' + part).lstrip('/')
            node.children[part] = TreeNode(name=part, full_path=child_path)
        child = node.children[part]
        if isinstance(child, FileNode):
            return
        node = child
    node.children[parts[-1]] = file_node


def load_diff_tree(root: str, base: Optional[str], ref: str) -> tuple[Optional[TreeNode], Optional[str]]:
    """Return (tree, error). base=None means 'diff against the empty tree'
    (root waypoint — every file appears as [N])."""
    if base is None:
        r = _run(['git', '-C', root, 'ls-tree', '-r', '--name-only', ref])
        if r.returncode != 0:
            return None, 'ls-tree failed'
        entries = [('A', p) for p in r.stdout.splitlines() if p]
        return build_file_tree(entries, {}), None

    if base == _resolve(root, ref):
        return TreeNode(name='', full_path=''), None

    r = _run(['git', '-C', root, 'diff', '--name-status', base, ref])
    if r.returncode != 0:
        return None, f'diff failed: {r.stderr.strip()[:60]}'
    entries = parse_name_status(r.stdout)
    numstat = {}
    if entries:
        r2 = _run(['git', '-C', root, 'diff', '--numstat',
                   '--diff-filter=M', base, ref])
        numstat = parse_numstat(r2.stdout)
    return build_file_tree(entries, numstat), None


def load_branch_data(branch: BranchNode, root: str, pipe_w: int):
    """Background thread: load branch's delta vs parent waypoint."""
    branch.loading = True
    try:
        tree, err = load_diff_tree(root, branch.parent_base, branch.ref)
        if err:
            branch.error = err
            return
        branch.file_tree = tree
        branch.loaded = True
    except Exception as e:
        branch.error = str(e)
    finally:
        branch.loading = False
        try:
            os.write(pipe_w, b'r')
        except OSError:
            pass


def fetch_diff(root: str, base: str, ref: str, path: str) -> list:
    r = _run(['git', '-C', root, 'diff', base, ref, '--', path])
    return r.stdout.splitlines()


# ---------------------------------------------------------------------------
# Display list
# ---------------------------------------------------------------------------

def _node_glyph_and_attr(b: BranchNode) -> tuple[str, int]:
    if b.is_current:
        return '◉', curses.color_pair(CP_BRANCH_CURRENT) | curses.A_BOLD
    if b.is_sideways:
        return '◆', curses.color_pair(CP_SIDEWAYS) | curses.A_BOLD
    if b.is_local:
        return '●', curses.color_pair(CP_BRANCH_LOCAL) | curses.A_BOLD
    return '○', curses.color_pair(CP_BRANCH_REMOTE)


def _spine_for_branch(b: BranchNode) -> list:
    # Sideways forks keep the tree-art so the off-chain shape is visible.
    if b.is_sideways:
        dim = curses.color_pair(CP_DIM) | curses.A_DIM
        side = curses.color_pair(CP_SIDEWAYS)
        glyph, gattr = _node_glyph_and_attr(b)
        return [('│', dim), (' ', dim), ('├', side), ('─', side),
                (glyph, gattr), (' ', 0)]
    # Mainline rows: no status glyph — just `*` on the current branch.
    if b.is_current:
        return [('*', curses.color_pair(CP_BRANCH_CURRENT) | curses.A_BOLD), (' ', 0)]
    return [(' ', 0), (' ', 0)]


def _spine_for_subrow(b: BranchNode) -> list:
    if b.is_sideways:
        dim = curses.color_pair(CP_DIM) | curses.A_DIM
        side = curses.color_pair(CP_SIDEWAYS) | curses.A_DIM
        return [('│', dim), (' ', dim), ('│', side), (' ', dim), (' ', 0), (' ', 0)]
    return [(' ', 0), (' ', 0)]


def flatten_all(branches: list) -> list:
    rows = []
    for b in branches:
        rows.extend(_flatten_branch(b))
    return rows


def _flatten_branch(branch: BranchNode) -> list:
    spine = _spine_for_branch(branch)
    sub_spine = _spine_for_subrow(branch)
    rows = [DisplayRow(
        kind='branch',
        depth=0,
        label=branch.display_name,
        annotation='',
        ref=branch,
        branch=branch,
        spine_cells=spine,
    )]
    if not branch.expanded:
        return rows
    if branch.loading:
        rows.append(DisplayRow('loading', 1, '(loading…)', '', None, branch, spine_cells=sub_spine))
    elif branch.error:
        rows.append(DisplayRow('error', 1, f'Error: {branch.error}', '', None, branch, spine_cells=sub_spine))
    elif branch.file_tree is None or not branch.file_tree.children:
        parent_label = branch.parent.display_name if branch.parent else 'root'
        rows.append(DisplayRow('empty', 1, f'(no changes vs {parent_label})', '', None, branch, spine_cells=sub_spine))
    else:
        rows.extend(_flatten_tree(branch.file_tree, depth=1, branch=branch, sub_spine=sub_spine))
    return rows


def _flatten_tree(tree: TreeNode, depth: int, branch: BranchNode, sub_spine: list) -> list:
    rows = []
    dirs  = {k: v for k, v in tree.children.items() if isinstance(v, TreeNode)}
    files = {k: v for k, v in tree.children.items() if isinstance(v, FileNode)}

    for name in sorted(dirs):
        child = dirs[name]
        marker = 'v' if child.expanded else '>'
        rows.append(DisplayRow('dir', depth, f'{marker} {name}/', '', child, branch, spine_cells=sub_spine))
        if child.expanded:
            rows.extend(_flatten_tree(child, depth + 1, branch, sub_spine))

    for name in sorted(files):
        f = files[name]
        rows.append(DisplayRow('file', depth, name, f.annotation, f, branch, spine_cells=sub_spine))

    return rows


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _truncate(s: str, max_len: int) -> str:
    if max_len <= 0:
        return ''
    if len(s) <= max_len:
        return s
    if max_len <= 3:
        return s[:max_len]
    # Right-truncate so date prefixes (`2026-…`) stay visible.
    return s[:max_len - 1] + '…'


def _compute_scroll(cursor: int, offset: int, visible: int, total: int) -> int:
    if cursor < offset:
        return cursor
    if cursor >= offset + visible:
        return cursor - visible + 1
    return offset


_STRATA_EIGHTHS = ' ▏▎▍▌▋▊▉▇'


def _strata_bar(commits: int, max_commits: int, width: int) -> str:
    if width <= 0 or max_commits <= 0 or commits <= 0:
        return ' ' * max(width, 0)
    total_eighths = max(1, round((commits / max_commits) * width * 8))
    total_eighths = min(total_eighths, width * 8)
    full = total_eighths // 8
    rem  = total_eighths % 8
    s = '▇' * full
    if rem:
        s += _STRATA_EIGHTHS[rem]
    return s.ljust(width)


def render_main(stdscr, state: AppState):
    h, w = stdscr.getmaxyx()
    visible = h - 2  # status + compare banner

    state.scroll_offset = _compute_scroll(
        state.cursor, state.scroll_offset, visible, len(state.rows)
    )

    # Header line: title or compare banner
    try:
        stdscr.move(0, 0)
        stdscr.clrtoeol()
    except curses.error:
        pass
    _render_header(stdscr, state, w)

    for sy in range(visible):
        idx = state.scroll_offset + sy
        y = sy + 1  # leave row 0 for header
        try:
            stdscr.move(y, 0)
            stdscr.clrtoeol()
        except curses.error:
            pass
        if idx >= len(state.rows):
            continue
        row = state.rows[idx]
        _render_row(stdscr, y, row, idx == state.cursor, w, state)

    _render_status_bar(stdscr, state, h, w)
    stdscr.refresh()
    # Strikethrough writes happen after refresh but rows are offset by 1 (header)
    _apply_strikethrough_offset(state, h, w, y_offset=1)


def _apply_strikethrough_offset(state: AppState, h: int, w: int, y_offset: int):
    if not _STRIKE_ON:
        return
    smxx = _STRIKE_ON
    rmxx = _STRIKE_OFF or b'\x1b[29m'
    visible = h - 2
    out = bytearray()
    for sy in range(visible):
        idx = state.scroll_offset + sy
        if idx >= len(state.rows):
            break
        row = state.rows[idx]
        if row.kind != 'file':
            continue
        f = row.ref
        if not isinstance(f, FileNode) or f.status != 'D':
            continue
        x0 = len(row.spine_cells)
        indent = '  ' * min(row.depth, 12)
        ann = row.annotation
        avail = w - x0 - len(indent) - len(ann) - 1
        name = _truncate(row.label, max(avail, 1))
        col = x0 + len(indent)
        out += f'\033[{sy + 1 + y_offset};{col + 1}H'.encode()
        out += smxx
        out += name.encode(errors='replace')
        out += rmxx
    if out:
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()


def _render_header(stdscr, state: AppState, w: int):
    if state.compare_mark:
        text = f' Cmp: {state.compare_mark.display_name} ↔ ?   (press c on second branch, ESC to cancel)'
        attr = curses.color_pair(CP_COMPARE_MARK)
    elif state.message:
        text = f' {state.message}'
        attr = curses.color_pair(CP_STATUS_BAR)
    else:
        text = ' git-branch-browser   waypoint pipeline view'
        attr = curses.color_pair(CP_STATUS_BAR) | curses.A_DIM
    text = text[:w - 1].ljust(w - 1)
    try:
        stdscr.addstr(0, 0, text, attr)
    except curses.error:
        pass


def _draw_spine(win, y: int, cells: list, base_attr: int, max_w: int) -> int:
    """Draw row.spine_cells at x=0. Returns x-column where content starts."""
    x = 0
    for ch, attr in cells:
        if x >= max_w:
            break
        try:
            win.addstr(y, x, ch, attr | base_attr)
        except curses.error:
            pass
        x += 1
    return x


def _render_row(win, y: int, row: DisplayRow, is_cursor: bool, max_w: int, state: AppState):
    base = curses.A_REVERSE if is_cursor else curses.A_NORMAL

    def safe_addstr(win, y, x, s, attr):
        if x >= max_w or not s:
            return
        s = s[:max_w - x]
        try:
            win.addstr(y, x, s, attr)
        except curses.error:
            pass

    if row.kind == 'branch':
        _render_branch_row(win, y, row, base, max_w, state, safe_addstr)
        return

    x0 = _draw_spine(win, y, row.spine_cells, base, max_w)
    indent = '  ' * min(row.depth, 12)

    if row.kind == 'dir':
        label = _truncate(row.label, max_w - x0 - len(indent))
        safe_addstr(win, y, x0, indent + label,
                    curses.color_pair(CP_DIR) | curses.A_BOLD | base)

    elif row.kind == 'file':
        f = row.ref
        ann = row.annotation
        avail = max_w - x0 - len(indent) - len(ann) - 1
        name = _truncate(row.label, max(avail, 1))
        file_color = annotation_color(f.status) if f.status == 'D' else curses.color_pair(CP_NORMAL)
        safe_addstr(win, y, x0, indent + name + ' ', file_color | base)
        x = x0 + len(indent) + len(name) + 1
        if ann and x < max_w:
            safe_addstr(win, y, x, ann, annotation_color(f.status) | base)

    elif row.kind in ('loading', 'empty'):
        safe_addstr(win, y, x0, indent + row.label,
                    curses.color_pair(CP_DIM) | curses.A_DIM | base)

    elif row.kind == 'error':
        safe_addstr(win, y, x0, indent + row.label,
                    curses.color_pair(CP_ERROR) | base)


def _render_branch_row(win, y: int, row: DisplayRow, base_attr: int,
                       max_w: int, state: AppState, safe_addstr):
    b: BranchNode = row.ref

    x0 = _draw_spine(win, y, row.spine_cells, base_attr, max_w)
    marker = 'v ' if b.expanded else '> '

    if b.is_current:
        name_attr = curses.color_pair(CP_BRANCH_CURRENT) | curses.A_BOLD
    elif b.is_sideways:
        name_attr = curses.color_pair(CP_SIDEWAYS) | curses.A_BOLD
    elif b.is_local:
        name_attr = curses.color_pair(CP_BRANCH_LOCAL) | curses.A_BOLD
    else:
        name_attr = curses.color_pair(CP_BRANCH_REMOTE)

    if state.compare_mark is b:
        name_attr |= curses.A_UNDERLINE

    short_sha = b.tip_sha[:7] if b.tip_sha else '       '
    ahead = (f'+{b.commits_ahead}' if b.commits_ahead else '+0').rjust(5)
    if b.parent is None:
        arrow = '(root)'
    elif b.is_sideways:
        arrow = f'↗{b.parent.display_name}'
    else:
        arrow = f'←{b.parent.display_name}'

    strata_w = max(6, min(16, max_w // 6))
    date_str = b.tip_date[5:10] if len(b.tip_date) >= 10 else ''

    # Column layout (left → right):
    #   spine | marker | name(fixed) | sha(7) | ahead(5) | arrow(natural) | strata | date
    # Name column is fixed-width so left edges align. Arrow is natural-width
    # so the strata bar sits right after the arrow text, not in a distant column.
    gap = 2
    avail = max_w - x0 - len(marker) - 1
    fixed_tail = 7 + 5 + strata_w + (len(date_str) if date_str else 0)
    fixed_gaps = 4 * gap + (gap if date_str else 0)
    name_w = 32
    if avail < name_w + fixed_tail + fixed_gaps + 4:
        # Very narrow terminal — shrink name column first.
        name_w = max(12, avail - fixed_tail - fixed_gaps - 4)
    arrow_budget = max(0, avail - name_w - fixed_tail - fixed_gaps)
    arrow_w = min(len(arrow), arrow_budget) if arrow_budget > 0 else 0

    name_txt = _truncate(b.display_name, name_w).ljust(name_w)
    arrow_txt = _truncate(arrow, arrow_w) if arrow_w > 0 else ''

    dim_attr = curses.color_pair(CP_DIM) | curses.A_DIM | base_attr
    arrow_attr = (curses.color_pair(CP_SIDEWAYS) if b.is_sideways
                  else curses.color_pair(CP_DIM)) | base_attr
    ahead_attr = curses.color_pair(CP_FILE_NEW) | base_attr

    x = x0
    safe_addstr(win, y, x, marker, dim_attr)
    x += len(marker)
    safe_addstr(win, y, x, name_txt, name_attr | base_attr)
    x += len(name_txt)
    safe_addstr(win, y, x, '  ' + short_sha, dim_attr)
    x += gap + 7
    safe_addstr(win, y, x, '  ' + ahead, ahead_attr)
    x += gap + 5
    if arrow_txt:
        safe_addstr(win, y, x, '  ' + arrow_txt, arrow_attr)
        x += gap + len(arrow_txt)
    if strata_w > 0:
        strata_txt = _strata_bar(b.commits_ahead, state.max_commits_ahead, strata_w)
        safe_addstr(win, y, x, '  ' + strata_txt, curses.color_pair(CP_STRATA) | base_attr)
        x += gap + len(strata_txt)
    if date_str:
        safe_addstr(win, y, x, '  ' + date_str, dim_attr)


def _render_status_bar(stdscr, state: AppState, h: int, w: int):
    total = len(state.rows)
    pos = f'{state.cursor + 1}/{total}' if total else '0/0'
    hint = '  ENTER=expand/diff  m=vs-master  c=compare  -/←=collapse  q=quit'
    bar = f' {pos}{hint}'
    bar = bar[:w - 1].ljust(w - 1)
    try:
        stdscr.addstr(h - 1, 0, bar, curses.color_pair(CP_STATUS_BAR))
    except curses.error:
        pass


# ---------------------------------------------------------------------------
# Diff pager
# ---------------------------------------------------------------------------

def _diff_line_color(line: str) -> int:
    if line.startswith('+++ ') or line.startswith('--- '):
        return curses.color_pair(CP_DIFF_HEADER) | curses.A_BOLD
    if line.startswith('+'):
        return curses.color_pair(CP_DIFF_ADD)
    if line.startswith('-'):
        return curses.color_pair(CP_DIFF_DEL)
    if line.startswith('@@'):
        return curses.color_pair(CP_DIFF_HUNK)
    if line.startswith('diff ') or line.startswith('index '):
        return curses.color_pair(CP_DIFF_HEADER) | curses.A_DIM
    return curses.color_pair(CP_NORMAL)


def show_diff_pager(stdscr, diff_lines: list, title: str):
    scroll = 0
    stdscr.nodelay(False)

    while True:
        h, w = stdscr.getmaxyx()
        visible = h - 2

        try:
            stdscr.move(0, 0)
            stdscr.clrtoeol()
            title_bar = f' {title}'[:w - 1].ljust(w - 1)
            stdscr.addstr(0, 0, title_bar, curses.color_pair(CP_STATUS_BAR))
        except curses.error:
            pass

        for i in range(visible):
            li = scroll + i
            try:
                stdscr.move(i + 1, 0)
                stdscr.clrtoeol()
            except curses.error:
                pass
            if li >= len(diff_lines):
                continue
            line = diff_lines[li]
            color = _diff_line_color(line)
            try:
                stdscr.addstr(i + 1, 0, line[:w - 1], color)
            except curses.error:
                pass

        total = len(diff_lines)
        end = min(scroll + visible, total)
        pct = int(100 * end / total) if total else 100
        status = f' Lines {scroll + 1}–{end} of {total} ({pct}%)  ↑↓/PgUp/PgDn/Home/End  q/ESC=back'
        try:
            stdscr.addstr(h - 1, 0, status[:w - 1].ljust(w - 1),
                          curses.color_pair(CP_STATUS_BAR))
        except curses.error:
            pass

        stdscr.refresh()
        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            break

        if key in (ord('q'), 27, 3):  # 3 = Ctrl+C if raw mode ever swallows SIGINT
            break
        elif key == curses.KEY_DOWN:
            scroll = min(scroll + 1, max(0, total - visible))
        elif key == curses.KEY_UP:
            scroll = max(scroll - 1, 0)
        elif key == curses.KEY_NPAGE:
            scroll = min(scroll + visible, max(0, total - visible))
        elif key == curses.KEY_PPAGE:
            scroll = max(scroll - visible, 0)
        elif key == curses.KEY_HOME:
            scroll = 0
        elif key == curses.KEY_END:
            scroll = max(0, total - visible)
        elif key == curses.KEY_RESIZE:
            curses.resizeterm(*stdscr.getmaxyx())

    stdscr.nodelay(True)


# ---------------------------------------------------------------------------
# Compare view (two branches picked via `c`)
# ---------------------------------------------------------------------------

def open_compare_view(stdscr, state: AppState, a: BranchNode, b: BranchNode):
    """Modal: load file-tree delta a..b, let user ENTER on files to diff."""
    root = state.repo_root
    base_sha = _merge_base(root, a.ref, b.ref)
    if not base_sha:
        state.message = f'No common ancestor between {a.display_name} and {b.display_name}'
        return
    tree, err = load_diff_tree(root, base_sha, b.ref)
    if err:
        state.message = f'Compare failed: {err}'
        return

    # Wrap in a synthetic branch so we can reuse the same flatten/render code.
    synthetic = BranchNode(
        display_name=f'Compare: {a.display_name} → {b.display_name}',
        ref=b.ref,
        is_local=b.is_local,
        tip_sha=b.tip_sha,
        tip_date=b.tip_date,
        parent=a,
        parent_base=base_sha,
        commits_ahead=_rev_count(root, f'{base_sha}..{b.tip_sha}'),
        file_tree=tree,
        loaded=True,
        expanded=True,
    )

    # Dedicated navigation loop over the compare tree only.
    rows = _flatten_branch(synthetic)
    cursor = 0
    scroll = 0
    stdscr.nodelay(False)
    while True:
        h, w = stdscr.getmaxyx()
        visible = h - 2
        scroll = _compute_scroll(cursor, scroll, visible, len(rows))

        try:
            stdscr.move(0, 0)
            stdscr.clrtoeol()
            n_files = sum(1 for r in rows if r.kind == 'file')
            title = f' Compare  {a.display_name} ↔ {b.display_name}   {n_files} files   (+{synthetic.commits_ahead} commits)'
            stdscr.addstr(0, 0, title[:w - 1].ljust(w - 1),
                          curses.color_pair(CP_COMPARE_MARK))
        except curses.error:
            pass

        for sy in range(visible):
            idx = scroll + sy
            y = sy + 1
            try:
                stdscr.move(y, 0)
                stdscr.clrtoeol()
            except curses.error:
                pass
            if idx >= len(rows):
                continue
            row = rows[idx]
            _render_row(stdscr, y, row, idx == cursor, w, state)

        try:
            hint = f' {cursor + 1}/{len(rows)}   ENTER=diff  q/ESC=back'
            stdscr.addstr(h - 1, 0, hint[:w - 1].ljust(w - 1),
                          curses.color_pair(CP_STATUS_BAR))
        except curses.error:
            pass

        stdscr.refresh()
        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            break
        if key in (ord('q'), 27, 3):
            break
        elif key in (curses.KEY_DOWN, ord('j')):
            cursor = min(cursor + 1, len(rows) - 1)
        elif key in (curses.KEY_UP, ord('k')):
            cursor = max(cursor - 1, 0)
        elif key == curses.KEY_NPAGE:
            cursor = min(cursor + visible, len(rows) - 1)
        elif key == curses.KEY_PPAGE:
            cursor = max(cursor - visible, 0)
        elif key == curses.KEY_HOME:
            cursor = 0
        elif key == curses.KEY_END:
            cursor = max(len(rows) - 1, 0)
        elif key == curses.KEY_RESIZE:
            curses.resizeterm(*stdscr.getmaxyx())
        elif key in (10, 13):
            row = rows[cursor]
            if row.kind == 'branch':
                pass  # synthetic header — no-op
            elif row.kind == 'dir':
                row.ref.expanded = not row.ref.expanded
                rows = _flatten_branch(synthetic)
            elif row.kind == 'file':
                f = row.ref
                lines = fetch_diff(root, base_sha, b.ref, f.path)
                show_diff_pager(stdscr, lines, title=f'{a.display_name}..{b.display_name}  {f.path}')

    stdscr.nodelay(True)


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

def _page_size(state: AppState, stdscr) -> int:
    h, _ = stdscr.getmaxyx()
    return max(h - 3, 1)


def handle_key_main(key: int, state: AppState, stdscr) -> Optional[str]:
    rows = state.rows
    row = rows[state.cursor] if rows else None

    if key == ord('q'):
        return 'quit'

    elif key == 27:  # ESC clears compare mark or message
        state.compare_mark = None
        state.message = ''

    elif key in (curses.KEY_DOWN, ord('j')):
        state.cursor = min(state.cursor + 1, len(rows) - 1)

    elif key in (curses.KEY_UP, ord('k')):
        state.cursor = max(state.cursor - 1, 0)

    elif key == curses.KEY_NPAGE:
        state.cursor = min(state.cursor + _page_size(state, stdscr), len(rows) - 1)

    elif key == curses.KEY_PPAGE:
        state.cursor = max(state.cursor - _page_size(state, stdscr), 0)

    elif key == curses.KEY_HOME:
        state.cursor = 0

    elif key == curses.KEY_END:
        state.cursor = max(len(rows) - 1, 0)

    elif key == curses.KEY_RESIZE:
        curses.resizeterm(*stdscr.getmaxyx())

    elif key in (10, 13):  # ENTER
        if row is None:
            pass
        elif row.kind == 'branch':
            b = row.ref
            b.expanded = not b.expanded
            if b.expanded and not b.loaded and not b.loading:
                threading.Thread(
                    target=load_branch_data,
                    args=(b, state.repo_root, state.notify_pipe_w),
                    daemon=True,
                ).start()
        elif row.kind == 'dir':
            row.ref.expanded = not row.ref.expanded
        elif row.kind == 'file':
            return 'show_diff_parent'

    elif key == ord('m'):
        if row and row.kind == 'file':
            return 'show_diff_master'
        else:
            state.message = 'Move cursor to a file first (m = diff vs master)'

    elif key == ord('c'):
        if row is None or row.kind != 'branch':
            state.message = 'Compare: move cursor to a branch row'
        elif state.compare_mark is None:
            state.compare_mark = row.ref
            state.message = ''
        elif state.compare_mark is row.ref:
            state.compare_mark = None
            state.message = 'Compare mark cleared'
        else:
            return 'open_compare'

    elif key in (ord('+'), curses.KEY_RIGHT):
        if row is None:
            pass
        elif row.kind == 'branch':
            b = row.ref
            if not b.expanded:
                b.expanded = True
                if not b.loaded and not b.loading:
                    threading.Thread(
                        target=load_branch_data,
                        args=(b, state.repo_root, state.notify_pipe_w),
                        daemon=True,
                    ).start()
        elif row.kind == 'dir':
            row.ref.expanded = True

    elif key in (ord('-'), curses.KEY_LEFT):
        if row is None:
            pass
        elif row.kind == 'branch':
            row.ref.expanded = False
        elif row.kind == 'dir':
            row.ref.expanded = False
        elif row.kind == 'file':
            for i in range(state.cursor - 1, -1, -1):
                r = rows[i]
                if r.kind == 'dir' and r.depth == row.depth - 1:
                    r.ref.expanded = False
                    state.cursor = i
                    break
                if r.kind == 'branch' and row.depth == 1:
                    r.ref.expanded = False
                    state.cursor = i
                    break

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    init_colors()

    repo_root = get_repo_root()
    current = get_current_branch(repo_root)
    master_ref = resolve_master_ref(repo_root)
    branches = get_all_branches(repo_root)
    for b in branches:
        b.is_current = (b.ref == current or b.display_name == current)

    # Startup: topology detection (O(N²) merge-base — ~100 calls at N=10)
    max_ahead = detect_topology(repo_root, branches)
    branches = sort_waypoints(branches)

    pipe_r, pipe_w = os.pipe()
    state = AppState(
        repo_root=repo_root,
        branches=branches,
        rows=[],
        cursor=0,
        scroll_offset=0,
        notify_pipe_r=pipe_r,
        notify_pipe_w=pipe_w,
        master_ref=master_ref,
        max_commits_ahead=max_ahead,
    )
    state.rows = flatten_all(branches)

    try:
        _run_main_loop(stdscr, state, pipe_r, repo_root, branches)
    finally:
        try:
            os.close(pipe_r)
        except OSError:
            pass
        try:
            os.close(pipe_w)
        except OSError:
            pass


def _run_main_loop(stdscr, state, pipe_r, repo_root, branches):
    while True:
        if state.needs_redraw:
            render_main(stdscr, state)
            state.needs_redraw = False

        try:
            rlist, _, _ = select.select([pipe_r], [], [], 0.05)
        except (select.error, ValueError, InterruptedError):
            # SIGINT during select → EINTR; treat as quit
            return
        except KeyboardInterrupt:
            return

        if pipe_r in rlist:
            try:
                os.read(pipe_r, 64)
            except OSError:
                pass
            state.rows = flatten_all(branches)
            state.needs_redraw = True
            continue

        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            return
        if key == -1:
            continue
        if key == 3:  # Ctrl+C as a key code
            return

        try:
            action = handle_key_main(key, state, stdscr)
        except KeyboardInterrupt:
            return

        if action == 'quit':
            return

        elif action in ('show_diff_parent', 'show_diff_master'):
            row = state.rows[state.cursor]
            f = row.ref
            b = row.branch
            if not b:
                pass
            elif action == 'show_diff_parent':
                base = b.parent_base
                if base is None:
                    # Root waypoint — diff against empty tree
                    base = _run(['git', '-C', repo_root, 'hash-object', '-t', 'tree', '/dev/null']).stdout.strip() \
                        or '4b825dc642cb6eb9a060e54bf8d69288fbee4904'  # git empty tree SHA
                diff_lines = fetch_diff(repo_root, base, b.ref, f.path)
                title = f'{f.path}   (vs {b.parent.display_name if b.parent else "∅"})'
                show_diff_pager(stdscr, diff_lines, title=title)
                state.needs_redraw = True
            else:  # show_diff_master
                if not state.master_ref:
                    state.message = 'No master/main branch found'
                else:
                    mb = _merge_base(repo_root, state.master_ref, b.ref)
                    if not mb:
                        state.message = f'No common ancestor with {state.master_ref}'
                    else:
                        diff_lines = fetch_diff(repo_root, mb, b.ref, f.path)
                        title = f'{f.path}   (vs {state.master_ref})'
                        show_diff_pager(stdscr, diff_lines, title=title)
                        state.needs_redraw = True

        elif action == 'open_compare':
            other = state.rows[state.cursor].ref
            a = state.compare_mark
            state.compare_mark = None
            open_compare_view(stdscr, state, a, other)
            state.needs_redraw = True

        state.rows = flatten_all(branches)
        state.needs_redraw = True


if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        # Curses already torn down by wrapper; exit quietly.
        sys.exit(130)
