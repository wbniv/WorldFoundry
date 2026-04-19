# Plan: git-branch-browser — curses TUI for browsing a branch pipeline

**Date:** 2026-04-16 (revised 2026-04-18)
**Status:** Revised design — redesigning the v1 script (`scripts/git-branch-browser.py`, ~784 LOC) in place
**Goal:** A Python curses program at `scripts/git-branch-browser.py` that surfaces the repo's branch topology as a chronological **waypoint pipeline** (not a flat tree), with incremental per-waypoint deltas, automatic sideways-fork detection, and three diff modes (vs parent, vs master, branch-to-branch compare).

## Why not "collapsible tree of branches"

Inventory of this repo (2026-04-18) shows all nine branches form a single linear chain — every branch is a strict superset of its predecessor:

```
2026-linux → 2026-iffcomp → 2026-rust → master → scripting-replacement
           → drop-dead-renderers → 2026-first-working-gap → 2026-android
```

In that world, flattening each branch to `diff vs master` swamps the later bookmarks with cumulative deltas. The real artefact each branch represents is **the commits it added on top of the previous waypoint**. The UI should reflect that.

## Topology detection

At startup, compute a partial order over branches:

1. For every pair `(A, B)` compute `merge-base(A, B)`.
2. A branch `P` is a **candidate parent** of `B` if `merge-base(P, B) == P_tip` (i.e. `P` is a strict ancestor of `B`).
3. `B`'s **parent waypoint** is the candidate with the *latest* commit date (nearest ancestor).
4. A branch with no candidate parents is a **root waypoint** (anchored at the repo root).

A branch is classified as **sideways** when its merge-base with its parent is older than the parent's tip — i.e. it forked off the chain at an earlier point rather than adding to the end. Sideways forks render as a branch *off* the timeline, anchored at the merge-base, rather than as another link in the chain.

Main-line branches are ordered by commit date, oldest at the bottom. Sideways forks render adjacent to their parent, indented with a `├─` connector.

## Screenshots

**Main view — linear pipeline (current repo state):**

```
  * 2026-android                 934583e   +67    ←first-working-gap    ▇▇▇▇▇▇▇▇ 2026-04-18
    2026-first-working-gap       0f6c34e   +174   ←drop-dead-renderers  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇ 04-17
    drop-dead-renderers          91607e7   +36    ←scripting-…          ▇▇▇▇ 04-14
    2026-04-14-scripting-…       fe0ffbd   +1     ←master               ▏ 04-14
    master                       71727ab   +36    ←2026-rust            ▇▇▇▇ 04-14
    origin/master                5d1b1fe   +50    ←master               ▇▇▇▇▇ 04-16
    2026-rust                    9eef2d7   +71    ←2026-iffcomp         ▇▇▇▇▇▇▇▇ 04-13
    2026-iffcomp                 5d27335   +7     ←2026-linux           ▇ 04-12
    2026-linux                   ae6b09d   +28    (root)                ▇▇▇ 04-11
  9/9   ENTER=expand  m=vs-master  c=compare  q=quit
```

`▇` column is the strata bar — width proportional to commits added at that waypoint. Current branch prefixed with `*`. Expanded waypoint reveals its incremental file tree below (same widget as v1).

**Expanded waypoint (delta vs parent):**

```
  v 2026-android                 934583e   +67    ←first-working-gap    ▇▇▇▇▇▇▇▇
      v android/
          AndroidManifest.xml    [N]
          build.gradle           [N]
      v wfsource/source/game/
          game.cc                +18/-2
      (no changes in 23 other files unchanged vs first-working-gap)
    2026-first-working-gap       0f6c34e   +174   ←drop-dead-renderers  ▇▇▇▇▇▇▇▇▇…
```

Tree contains only files that changed **between `first-working-gap` and `android`** — not the cumulative delta from master. For `android` that's ~40 files, not hundreds.

**Hypothetical sideways fork:**

```
    drop-dead-renderers          91607e7   +36    ←scripting-…          ▇▇▇▇
    ├─ wip-experiment-xyz        abc1234   +12    ↗ fork from scripting…  ▇▇
```

`↗` marker + `├─` indent signals "this one didn't continue the chain, it forked off."

**Compare mode (two branches marked):**

```
  Compare: 2026-iffcomp ↔ 2026-android  (+348 commits, 127 files changed)
  v wfsource/source/game/
      game.cc                    +412/-89
      level.cc                   +178/-23
      ...
```

Same file-tree widget; base is `iffcomp`, tip is `android`.

## Diff modes

| Key | Mode | Semantics |
|---|---|---|
| `ENTER` on file | **vs parent** (default) | `git diff <parent_tip>..<branch_tip> -- <path>` |
| `m` on file | **vs master** | `git diff <master>..<branch_tip> -- <path>` (or swap if branch is ancestor of master) |
| `c` on branch | **mark for compare** | First `c` marks; second `c` opens compare view between marked branch and current row. `ESC` clears. |

Status-bar banner shows `Cmp: <marked-branch> → ?` once one branch is marked.

## Key bindings

| Key | Action |
|---|---|
| ↑/↓, j/k, PgUp/PgDn, Home/End | Navigate |
| ENTER on branch/dir | Toggle expand/collapse |
| `+` / → | Expand |
| `-` / ← | Collapse (from file: collapse parent dir) |
| ENTER on file | Open diff pager (vs parent waypoint) |
| `m` on file | Diff pager vs master |
| `c` on branch | Mark for compare / open compare view |
| `ESC` | Clear compare mark |
| `q` | Quit |
| ↑/↓/PgUp/PgDn in pager | Scroll |
| `q` / ESC in pager | Return |

## Data model (revised)

```python
@dataclass class FileNode: name, path, status, added, deleted, rename_from

@dataclass class TreeNode: name, full_path, children, expanded

@dataclass class BranchNode:
    display_name, ref: str
    is_local, is_current: bool
    tip_sha: str
    tip_date: str                # ISO — used for chronological sort
    # topology (populated after all branches are loaded)
    parent: Optional['BranchNode']  # nearest-ancestor branch; None = root
    is_sideways: bool               # True if forks off chain mid-way
    commits_ahead: int              # count of <parent>..<branch>
    # display state
    expanded, loaded, loading: bool = False
    file_tree: Optional[TreeNode] = None
    parent_base: Optional[str] = None   # merge-base(parent, self) — the diff base
    error: Optional[str] = None

@dataclass class DisplayRow:
    kind: str   # 'branch' | 'dir' | 'file' | 'loading' | 'empty' | 'error' | 'compare_banner'
    depth: int
    label, annotation: str
    ref: Any            # BranchNode | TreeNode | FileNode | None
    branch: Any         # owning BranchNode

@dataclass class AppState:
    repo_root: str
    branches: list[BranchNode]    # sorted chronologically, newest first
    rows: list[DisplayRow]
    cursor, scroll_offset: int
    notify_pipe_r, notify_pipe_w: int
    compare_mark: Optional[BranchNode] = None   # first branch picked via `c`
    max_commits_ahead: int = 1                  # for strata bar scaling
```

## Key functions

| Function | Purpose |
|---|---|
| `detect_topology(branches)` | O(N²) merge-base sweep; populates `parent`, `is_sideways`, `commits_ahead` |
| `sort_waypoints(branches)` | Chronological by `tip_date`, newest first; sideways grouped under their parent |
| `load_branch_data(branch, root, pipe_w)` | Uses `branch.parent` (not master) to compute `parent_base` + delta file tree |
| `fetch_diff(root, base, ref, path)` | Unchanged |
| `fetch_diff_vs_master(...)` | New: diff against local or origin/master |
| `open_compare_view(stdscr, state, a, b)` | New: load & render `a..b` file tree in a modal |
| `render_strata_bar(width, commits, max_commits)` | Unicode block chars scaled to column width |
| `render_waypoint_row(...)` | Replaces `_flatten_branch` branch label; includes SHA, `+N`, parent arrow, strata bar |

## Topology algorithm (pseudocode)

```python
def detect_topology(branches):
    # 1. Resolve tip SHA and commit date for each branch
    for b in branches:
        b.tip_sha  = git('rev-parse', b.ref).strip()
        b.tip_date = git('log', '-1', '--format=%cI', b.ref).strip()

    # 2. Pairwise merge-base → find strict ancestors (candidate parents)
    for b in branches:
        candidates = []
        for p in branches:
            if p is b: continue
            mb = git('merge-base', p.ref, b.ref).strip()
            if mb == p.tip_sha and mb != b.tip_sha:
                candidates.append((p, mb))

        if not candidates:
            b.parent, b.parent_base, b.is_sideways = None, None, False
            continue

        # 3. Nearest ancestor = latest commit date among candidates
        candidates.sort(key=lambda pm: pm[0].tip_date, reverse=True)
        parent, _ = candidates[0]
        b.parent = parent
        b.parent_base = parent.tip_sha
        # 4. Sideways check: is there another branch whose tip is between
        #    parent.tip and b.tip, but which b is NOT a descendant of?
        b.is_sideways = any(
            is_between(c.tip_sha, parent.tip_sha, b.tip_sha) and
            not is_ancestor(c.tip_sha, b.tip_sha)
            for c in branches if c not in (b, parent)
        )
        b.commits_ahead = int(git('rev-list', '--count', f'{parent.tip_sha}..{b.tip_sha}').strip())
```

## Strata bar

- Width is a fixed column (10–20 chars depending on terminal width).
- `▇` Unicode block full; `▏ ▎ ▍ ▌ ▋ ▊ ▉` for sub-char fractions (8 levels).
- Scale: `ceil((commits_ahead / max_commits_ahead) * col_width * 8)` eighths.
- Colour: matches the branch's waypoint colour (cyan/yellow/dim).
- No separate view — it's a column in the main pipeline list.

## Edge cases

- **Root branches** (no ancestor in set): `←` shows `(root)`; `parent_base` = empty tree, so all files render as `[N]`.
- **Sideways fork off master**: rendered under master with `├─` + `↗` annotation; diff base is the merge-base.
- **Compare across sideways**: works naturally — `git diff a..b` doesn't care about chain structure.
- **Detached HEAD**: same handling as v1; no branch marked current.
- **Topology load cost**: O(N²) merge-base calls. At ~10 branches that's 100 calls, ~100ms. Acceptable for one-shot startup. For >50 branches we'd batch via `git for-each-ref` + `--contains`, but not needed now.
- **Cache invalidation**: if a branch tip moves during a session, re-run doesn't auto-detect; `R` (reload) could be added but is out of scope.

## Critical file

- `scripts/git-branch-browser.py` — refactored in place. No new files.

## Verification

1. `python3 -m py_compile scripts/git-branch-browser.py` — exit 0.
2. Run in `/home/will/WorldFoundry`: all 9 branches listed chronologically, `2026-android` at top marked `*`, `2026-linux` at bottom marked `(root)`, each row shows `+N` commits vs its parent, strata bars visible.
3. ENTER on `2026-android` expands to ~40 files, not hundreds (diff vs `first-working-gap`, not master).
4. `m` on any file inside an expanded `2026-android` opens the vs-master diff for the same file.
5. `c` on `2026-iffcomp`, then `c` on `2026-android` opens compare view; file tree shows accumulated delta across the whole chain between those two points.
6. `ESC` clears the compare mark; banner disappears.
7. Root branch `2026-linux` expands to show all its files as `[N]` (full introduction).
8. Resize terminal → reflows; strata bar rescales.
