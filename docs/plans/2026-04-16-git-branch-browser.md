# Plan: git-branch-browser — curses TUI for browsing branch diffs

**Date:** 2026-04-16
**Status:** Not started
**Goal:** A Python curses program at `scripts/git-branch-browser.py` that lets you browse all git branches, see per-branch changed files as a collapsible directory tree with status annotations, and view file diffs inline.

## Screenshots

**Main view — branch list with file tree expanded:**

```
  > 2026-04-14-scripting-language-replacement
* v 2026-first-working-gap
    v docs/
      v plans/
          2026-04-16-android-port.md          +112/-0
          2026-04-16-blender-level-roundtrip.md +89/-12
      v investigations/
          2026-04-14-mobile-port-android-ios.md [D]
    v engine/
        build_game.sh                           +47/-3
    v wfsource/source/
      v game/
          game.cc                               +18/-2
      > physics/
  > drop-dead-renderers
  > master
 3/12  ENTER=expand/diff  -/←=collapse  +/→=expand  q=quit
```

Deleted files render with strikethrough (`[D]` in red).

**Diff pager (ENTER on a file):**

```
 engine/build_game.sh
 diff --git a/engine/build_game.sh b/engine/build_game.sh
 index 3a2f1c8..d94b2a1 100755
 --- a/engine/build_game.sh
 +++ b/engine/build_game.sh
 @@ -108,7 +108,11 @@ CXXFLAGS=(
      '-D__GAME__="wf_game"' "-DERR_DEBUG(x)="
 -    -DWF_ENABLE_LUA
 +    # WF_LUA_ENGINE handled below
      -I"$SRC" -I"$SRC/game" -I"$STUBS"
 +WF_LUA_ENGINE="${WF_LUA_ENGINE:-lua54}"
 +case "$WF_LUA_ENGINE" in
 +    lua54) CXXFLAGS+=(-DWF_ENABLE_LUA -I"$LUA_DIR/src") ;;
 +    none)  ;;
 Lines 1-24 of 89 (27%)  ↑↓/PgUp/PgDn/Home/End  q/ESC=back
```

## Features

- All local + remote branches listed; expand/collapse per branch
- Files changed vs. merge-base with master shown as a directory tree
- Per-file annotations: `[N]` new (green), `[D]` deleted (red, strikethrough), `[R]` rename (yellow), `[BIN]` binary (magenta), `+NN/-MM` for modified
- Scrollable diff pager on ENTER for any file
- Lazy loading: branch file list fetched in background thread on first expand; cached thereafter

## Key bindings

| Key | Action |
|---|---|
| ↑/↓, j/k | Move cursor |
| PgUp/PgDn | Page scroll |
| ENTER on branch or dir | Toggle expand/collapse |
| `+` / → | Expand |
| `-` / ← | Collapse; on file row, collapses parent dir |
| ENTER on file | Open diff pager |
| `q` | Quit |
| ↑/↓/PgUp/PgDn in pager | Scroll diff |
| `q` / ESC in pager | Return to main view |

## Data model

```python
@dataclass class FileNode:
    name, path, status: str          # status: A D M R
    added, deleted: Optional[int]    # None = binary
    rename_from: Optional[str]

@dataclass class TreeNode:
    name, full_path: str
    children: dict                   # str -> TreeNode | FileNode
    expanded: bool = False

@dataclass class BranchNode:
    display_name, ref: str           # ref = full git ref
    is_local, is_current: bool
    expanded, loaded, loading: bool = False
    file_tree: Optional[TreeNode] = None
    merge_base: Optional[str] = None
    error: Optional[str] = None

@dataclass class DisplayRow:
    kind: str       # 'branch' | 'dir' | 'file' | 'loading' | 'empty' | 'error'
    depth: int
    label: str
    annotation: str
    ref: Any        # BranchNode | TreeNode | FileNode
    branch: Any     # owning BranchNode

@dataclass class AppState:
    repo_root: str
    branches: list[BranchNode]
    rows: list[DisplayRow]
    cursor, scroll_offset: int
    notify_pipe_r, notify_pipe_w: int   # os.pipe for thread→main wakeup
```

## Key functions

| Function | Purpose |
|---|---|
| `get_repo_root()` | `git rev-parse --show-toplevel` |
| `get_all_branches(root)` | `git branch -a`; locals first; deduplicate remotes |
| `get_current_branch(root)` | `git symbolic-ref HEAD`; None on detached HEAD |
| `load_branch_data(node, root, pipe_w)` | Thread: merge-base → name-status → numstat → tree; writes `b'r'` to pipe on done |
| `parse_name_status(text)` | Handles A/D/M/Rxx; skips `warning:` lines |
| `parse_numstat(text)` | Path → `(added, deleted)`; `-\t-` = binary |
| `build_file_tree(entries, numstat)` | Recursive dict; dirs sorted before files |
| `flatten_all(branches)` | Recompute display list after any state change |
| `render_main(stdscr, state)` | Draw visible rows + status bar |
| `render_row(win, y, row, is_cursor, max_w)` | Dispatch by `row.kind`; truncate long paths |
| `show_diff_pager(stdscr, lines, title)` | Blocking scroll loop; `q`/ESC returns |
| `fetch_diff(root, base, ref, path)` | `git diff base ref -- path` → list of str |
| `handle_key_main(key, state)` | Returns `'quit'`, `'show_diff'`, or None |
| `main(stdscr)` | Init → state → `select()` event loop |

## Event loop

```python
stdscr.nodelay(True)
pipe_r, pipe_w = os.pipe()
while True:
    rlist = select([stdin, pipe_r], timeout=0.05)
    if pipe_r ready: drain, recompute rows, redraw
    key = stdscr.getch()
    handle_key_main() → may Thread(load_branch_data) or return 'show_diff'
```

## Strikethrough for deleted files

Curses has no standard strikethrough attribute, and `curses.putp()` fights curses' own output buffer. The working approach:

1. Render deleted file rows normally (red, no strikethrough) via curses
2. Call `stdscr.refresh()` to flush curses output — terminal state now in sync
3. Write raw ANSI `\033[9m` (smxx) + text + `\033[29m` (rmxx) directly to `sys.stdout.buffer` using absolute cursor positioning (`\033[row;colH`)

This works because after `refresh()` the terminal is in a known state; the raw bytes land on top. On the next frame, curses re-renders only changed cells — if no state changed the deleted rows aren't redrawn, so strikethrough persists.

`smxx` on xterm-256color = `b'\x1b[9m'`. If `tigetstr('smxx')` returns empty, strikethrough is silently skipped.

## Colors (17 pairs)

| Element | Color |
|---|---|
| Current branch | Bold cyan |
| Local branch | Bold yellow |
| Remote branch | Cyan |
| Directory | Bold blue |
| `[N]` new | Green |
| `[D]` deleted | Red |
| `+NN/-MM` modified | Green/red inline |
| `[R]` rename | Yellow |
| `[BIN]` binary | Magenta |
| Status bar | Reversed |
| Diff `+` lines | Green |
| Diff `-` lines | Red |
| Diff `@@` hunks | Cyan |
| Diff headers | Bold white |

## Edge cases

- **master branch**: merge-base = HEAD → empty diff → `(no changes vs master)`
- **Detached HEAD**: `get_current_branch` returns None; no branch marked current
- **merge-base fails** (orphan branch): set `branch.error`; display inline
- **Binary files**: `[BIN]` annotation; pager shows `Binary files differ`
- **Rename entries**: placed in tree at new path; `rename_from` stored on FileNode
- **Terminal resize**: `KEY_RESIZE` → `curses.resizeterm`; `curses.error` caught on all `addstr`
- **Remote-only branches**: full ref `remotes/origin/X`; display as `origin/X`; deduped vs locals

## Critical file

- `scripts/git-branch-browser.py` — new file, sole output

## Verification

1. `python3 -m py_compile scripts/git-branch-browser.py` — exit 0
2. Run: branches appear unexpanded; ENTER on `2026-first-working-gap` → `(loading...)` → file tree
3. Navigate: ↑↓ scroll, `-` collapse, `+` expand (cached, no reload)
4. ENTER on a `.cc` file → diff pager with colors; `q` returns
5. ENTER on `master` → `(no changes vs master)`
6. Resize terminal → reflows correctly
7. `q` exits cleanly; terminal restored by `curses.wrapper`
