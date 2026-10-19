# git-branch-browser — user's guide

A curses TUI that renders the repo's branch topology as a
**chronological waypoint pipeline**, with per-waypoint commit deltas,
expandable file trees, and three diff modes.

## The chain

At startup the tool computes a partial order over all local + remote
branches by pairwise merge-base:

- A branch's **parent waypoint** is the nearest-ancestor branch (latest
  commit date among strict ancestors).
- A branch with no ancestor branches is a **root waypoint** and shows
  `(root)` in the arrow column.
- Main-line branches are listed chronologically, newest first.
- **Sideways forks** — branches that forked off the chain mid-way
  rather than adding to the end — render under their parent with a
  `├─` connector and an `↗` arrow.

The pipeline is a *list of what commits each branch added on top of
its predecessor*, not a flat diff against master. Each row shows:

```
  * 2026-android            43ebc05   +77   ←2026-first-working-gap  ▇▇▇▇▇▇▇  04-19
```

| Column | Meaning |
|---|---|
| `*` | marks the current branch |
| name | 32-col fixed-width, right-truncated with `…` when long |
| sha | tip commit's short hash |
| `+N` | commits added on top of the parent waypoint |
| `←name` | parent waypoint (or `(root)`, or `↗name` for sideways forks) |
| `▇▇▇` | strata bar — width proportional to commits-added |
| date | tip commit date, `MM-DD` |

## Navigation

| Key | Action |
|---|---|
| `↑` `↓` / `j` `k` | move cursor |
| `PgUp` / `PgDn` | page up/down |
| `Home` / `End` | jump to top / bottom |
| `Enter` | expand branch (loads its file-tree delta) / expand dir / open diff on a file |
| `+` / `→` | expand |
| `-` / `←` | collapse (on a file row: collapses the enclosing dir) |
| `q` | quit |
| `?` | show this help (press `?` / `Esc` / `q` to close) |
| `Ctrl+C` | quit cleanly at any time |

## Diff modes

| Key | Context | Shows |
|---|---|---|
| `Enter` on a file | **vs parent** (default) | `git diff <parent_tip>..<branch_tip> -- <path>` |
| `m` on a file | **vs master** | `git diff <master>..<branch_tip> -- <path>` |
| `c` on a branch | **mark for compare** | first `c` marks the branch; a second `c` on another branch opens the compare view |

### Compare workflow

1. Move to a branch row.
2. Press `c` — the branch is marked (shown with an underline in the name column).
3. Move to another branch row.
4. Press `c` again — a modal opens showing the file-tree delta between the two branches. `Enter` on a file shows the full diff between them.
5. `Esc` / `q` returns to the main view.

`Esc` at any time (outside a diff pager) clears the compare mark.

## Diff pager

When viewing a file diff, you're in a scrollable pager:

| Key | Action |
|---|---|
| `↑` `↓` | scroll one line |
| `PgUp` / `PgDn` | scroll one page |
| `Home` / `End` | jump to top / bottom |
| `q` / `Esc` | return to the previous view |

## Row-level cues

- **Color**: current branch = cyan bold; local branch = yellow;
  remote-tracking = cyan dim; sideways fork = magenta.
- **Parent arrow**:
  - `←name` — linear predecessor (your commits sit on top of this
    branch).
  - `↗name` — sideways fork from `name` (your commits diverged; the
    chain continued without you).
  - `(root)` — no ancestor in the branch set; this is where history
    begins.
- **Strata bar** width is scaled to the single biggest `+N` in the
  repo, so at a glance you can see which waypoints carry the most work.

## Common tasks

**"How different is `2026-android` from `master`?"** Move cursor to
`2026-android`, press `Enter` to expand its per-waypoint delta. To see
the cumulative diff vs master for any file in the tree, press `m` on
that file.

**"Which branches can I delete?"** Branches marked `✓merged` are
reachable from `master` — work is already shipped. *(Status indicators
are a planned future addition; today the tool shows topology, not
deletion candidates.)*

**"What changed between `2026-iffcomp` and `2026-android`?"** Press `c`
on `2026-iffcomp`, then `c` on `2026-android` to open the compare
view. The file tree lists every path that differs between the two.

**"I want to push this branch."** That's outside the tool's current
scope — use `git push` directly. Push-status indicators are a planned
future addition.

## Exit

`q` or `Ctrl+C` at any time. The tool closes cleanly from every view.
