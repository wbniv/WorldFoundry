#!/usr/bin/env python3
"""Curses TUI for browsing git branches and their diffs."""

import curses
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
    children: dict = field(default_factory=dict)  # str -> TreeNode | FileNode
    expanded: bool = False


@dataclass
class BranchNode:
    display_name: str
    ref: str
    is_local: bool
    is_current: bool
    expanded: bool = False
    loaded: bool = False
    loading: bool = False
    file_tree: Optional[TreeNode] = None
    merge_base: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DisplayRow:
    kind: str    # 'branch' | 'dir' | 'file' | 'loading' | 'empty' | 'error'
    depth: int
    label: str
    annotation: str
    ref: Any
    branch: Any  # owning BranchNode


@dataclass
class AppState:
    repo_root: str
    branches: list
    rows: list
    cursor: int
    scroll_offset: int
    notify_pipe_r: int
    notify_pipe_w: int
    needs_redraw: bool = True


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

# Terminfo strikethrough (may be None on some terminals)
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
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True
    )


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


def get_all_branches(root: str) -> list:
    r = _run(['git', '-C', root, 'branch', '-a'])
    if r.returncode != 0:
        return []

    seen_short = set()
    branches = []

    lines = r.stdout.splitlines()
    # Local branches first
    for line in lines:
        stripped = line.strip().lstrip('* ')
        if stripped.startswith('remotes/'):
            continue
        if '->' in stripped:
            continue
        if stripped not in seen_short:
            seen_short.add(stripped)
            branches.append(BranchNode(
                display_name=stripped,
                ref=stripped,
                is_local=True,
                is_current=False,
            ))

    # Remote branches (deduplicate against locals)
    for line in lines:
        stripped = line.strip().lstrip('* ')
        if not stripped.startswith('remotes/'):
            continue
        if '->' in stripped:
            continue
        short = stripped[len('remotes/'):]        # e.g. origin/master
        # strip origin/ prefix for dedup key
        parts = short.split('/', 1)
        dedup_key = parts[1] if len(parts) == 2 else short
        if dedup_key in seen_short:
            continue
        seen_short.add(dedup_key)
        branches.append(BranchNode(
            display_name=short,
            ref=stripped,
            is_local=False,
            is_current=False,
        ))

    return branches


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
            # path collision (shouldn't happen in practice)
            return
        node = child
    node.children[parts[-1]] = file_node


def load_branch_data(branch: BranchNode, root: str, pipe_w: int):
    """Run in a background thread. Signals main loop via pipe_w when done."""
    branch.loading = True
    try:
        # Find merge-base with master (try local then remote)
        mb = None
        for master_ref in ('master', 'origin/master', 'main', 'origin/main'):
            r = _run(['git', '-C', root, 'merge-base', branch.ref, master_ref])
            if r.returncode == 0:
                mb = r.stdout.strip()
                break
        if mb is None:
            branch.error = 'No common ancestor with master/main'
            return

        branch.merge_base = mb

        # Changed files
        r = _run(['git', '-C', root, 'diff', '--name-status', mb, branch.ref])
        entries = parse_name_status(r.stdout)

        # Line counts for modified files
        numstat = {}
        if entries:
            r2 = _run(['git', '-C', root, 'diff', '--numstat',
                       '--diff-filter=M', mb, branch.ref])
            numstat = parse_numstat(r2.stdout)

        branch.file_tree = build_file_tree(entries, numstat)
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

def flatten_all(branches: list) -> list:
    rows = []
    for b in branches:
        rows.extend(_flatten_branch(b))
    return rows


def _flatten_branch(branch: BranchNode) -> list:
    marker = 'v' if branch.expanded else '>'
    prefix = '*' if branch.is_current else ' '
    rows = [DisplayRow(
        kind='branch',
        depth=0,
        label=f'{prefix} {marker} {branch.display_name}',
        annotation='',
        ref=branch,
        branch=branch,
    )]
    if not branch.expanded:
        return rows
    if branch.loading:
        rows.append(DisplayRow('loading', 1, '  (loading…)', '', None, branch))
    elif branch.error:
        rows.append(DisplayRow('error', 1, f'  Error: {branch.error}', '', None, branch))
    elif branch.file_tree is None or not branch.file_tree.children:
        rows.append(DisplayRow('empty', 1, '  (no changes vs master)', '', None, branch))
    else:
        rows.extend(_flatten_tree(branch.file_tree, depth=1, branch=branch))
    return rows


def _flatten_tree(tree: TreeNode, depth: int, branch: BranchNode) -> list:
    rows = []
    dirs  = {k: v for k, v in tree.children.items() if isinstance(v, TreeNode)}
    files = {k: v for k, v in tree.children.items() if isinstance(v, FileNode)}

    for name in sorted(dirs):
        child = dirs[name]
        marker = 'v' if child.expanded else '>'
        rows.append(DisplayRow('dir', depth, f'{marker} {name}/', '', child, branch))
        if child.expanded:
            rows.extend(_flatten_tree(child, depth + 1, branch))

    for name in sorted(files):
        f = files[name]
        rows.append(DisplayRow('file', depth, name, f.annotation, f, branch))

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
    return '…' + s[-(max_len - 1):]


def _compute_scroll(cursor: int, offset: int, visible: int, total: int) -> int:
    if cursor < offset:
        return cursor
    if cursor >= offset + visible:
        return cursor - visible + 1
    return offset


def _apply_strikethrough(state: AppState, h: int, w: int):
    """After stdscr.refresh(), write raw ANSI strikethrough over deleted file rows.
    curses.putp() fights curses' own buffer; writing to sys.stdout.buffer after
    refresh() is in sync with the terminal and works reliably."""
    if not _STRIKE_ON:
        return
    smxx = _STRIKE_ON        # e.g. b'\x1b[9m'
    rmxx = _STRIKE_OFF or b'\x1b[29m'
    visible = h - 1
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
        indent = '  ' * min(row.depth, 12)
        ann = row.annotation
        avail = w - len(indent) - len(ann) - 1
        name = _truncate(row.label, max(avail, 1))
        col = len(indent)
        # ANSI cursor position: \033[row;colH  (1-indexed)
        out += f'\033[{sy + 1};{col + 1}H'.encode()
        out += smxx
        out += name.encode(errors='replace')
        out += rmxx
    if out:
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()


def render_main(stdscr, state: AppState):
    h, w = stdscr.getmaxyx()
    visible = h - 1

    state.scroll_offset = _compute_scroll(
        state.cursor, state.scroll_offset, visible, len(state.rows)
    )

    for sy in range(visible):
        idx = state.scroll_offset + sy
        try:
            stdscr.move(sy, 0)
            stdscr.clrtoeol()
        except curses.error:
            pass
        if idx >= len(state.rows):
            continue
        row = state.rows[idx]
        _render_row(stdscr, sy, row, idx == state.cursor, w)

    _render_status_bar(stdscr, state, h, w)
    stdscr.refresh()
    _apply_strikethrough(state, h, w)


def _render_row(win, y: int, row: DisplayRow, is_cursor: bool, max_w: int):
    indent = '  ' * min(row.depth, 12)
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
        b = row.ref
        if b.is_current:
            attr = curses.color_pair(CP_BRANCH_CURRENT) | curses.A_BOLD | base
        elif b.is_local:
            attr = curses.color_pair(CP_BRANCH_LOCAL) | curses.A_BOLD | base
        else:
            attr = curses.color_pair(CP_BRANCH_REMOTE) | base
        label = _truncate(row.label, max_w - len(indent))
        safe_addstr(win, y, 0, indent + label, attr)

    elif row.kind == 'dir':
        label = _truncate(row.label, max_w - len(indent))
        safe_addstr(win, y, 0, indent + label,
                    curses.color_pair(CP_DIR) | curses.A_BOLD | base)

    elif row.kind == 'file':
        f = row.ref
        ann = row.annotation
        avail = max_w - len(indent) - len(ann) - 1
        name = _truncate(row.label, max(avail, 1))
        file_color = annotation_color(f.status) if f.status == 'D' else curses.color_pair(CP_NORMAL)
        safe_addstr(win, y, 0, indent + name + ' ', file_color | base)
        x = len(indent) + len(name) + 1
        if ann and x < max_w:
            safe_addstr(win, y, x, ann, annotation_color(f.status) | base)

    elif row.kind in ('loading', 'empty'):
        safe_addstr(win, y, 0, indent + row.label,
                    curses.color_pair(CP_DIM) | curses.A_DIM | base)

    elif row.kind == 'error':
        safe_addstr(win, y, 0, indent + row.label,
                    curses.color_pair(CP_ERROR) | base)


def _render_status_bar(stdscr, state: AppState, h: int, w: int):
    total = len(state.rows)
    pos = f'{state.cursor + 1}/{total}' if total else '0/0'
    hint = '  ENTER=expand/diff  -/←=collapse  +/→=expand  q=quit'
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
    stdscr.nodelay(False)  # blocking input in pager

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

        # status bar
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
        key = stdscr.getch()

        if key in (ord('q'), 27):
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
# Input handling
# ---------------------------------------------------------------------------

def _page_size(state: AppState, stdscr) -> int:
    h, _ = stdscr.getmaxyx()
    return max(h - 2, 1)


def handle_key_main(key: int, state: AppState, stdscr) -> Optional[str]:
    rows = state.rows
    row = rows[state.cursor] if rows else None

    if key == ord('q'):
        return 'quit'

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
            return 'show_diff'

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
            # collapse nearest dir ancestor
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
    branches = get_all_branches(repo_root)
    for b in branches:
        b.is_current = (b.ref == current or b.display_name == current)

    pipe_r, pipe_w = os.pipe()
    state = AppState(
        repo_root=repo_root,
        branches=branches,
        rows=[],
        cursor=0,
        scroll_offset=0,
        notify_pipe_r=pipe_r,
        notify_pipe_w=pipe_w,
    )
    state.rows = flatten_all(branches)

    while True:
        if state.needs_redraw:
            render_main(stdscr, state)
            state.needs_redraw = False

        try:
            rlist, _, _ = select.select([pipe_r], [], [], 0.05)
        except (select.error, ValueError):
            break

        if pipe_r in rlist:
            try:
                os.read(pipe_r, 64)
            except OSError:
                pass
            state.rows = flatten_all(branches)
            state.needs_redraw = True
            continue

        key = stdscr.getch()
        if key == -1:
            continue

        action = handle_key_main(key, state, stdscr)

        if action == 'quit':
            break
        elif action == 'show_diff':
            row = state.rows[state.cursor]
            f = row.ref
            b = row.branch
            if b and b.merge_base:
                diff_lines = fetch_diff(repo_root, b.merge_base, b.ref, f.path)
                show_diff_pager(stdscr, diff_lines, title=f.path)
                state.needs_redraw = True

        state.rows = flatten_all(branches)
        state.needs_redraw = True

    os.close(pipe_r)
    os.close(pipe_w)


if __name__ == '__main__':
    curses.wrapper(main)
