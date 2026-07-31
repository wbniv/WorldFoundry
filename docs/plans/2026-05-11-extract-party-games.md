# Plan A — Extract `party-games/` to a new local repo at `~/party-games/`

**Date:** 2026-05-11
**Status:** DONE (local-only per plan scope) — extracted to `~/party-games/` (separate git repo); not pushed to origin by design.
**Precondition for:** [Plan B — scrub + land master](2026-05-11-land-master-scrub-party-games.md)

## Context

The `party-games/` directory in the engine repo is a self-contained web stack
(relay server, receiver/controller shells, JS mini-games) that doesn't belong
in the engine. Extract it to its own repo with **history preserved**, as the
precondition for Plan B (scrub from engine history + land everything else on
master).

This plan covers **only** the extraction. It does not modify the engine repo or
any of its worktrees.

## Decisions

- **New repo location**: `~/party-games/` — local-only, no GitHub remote yet.
- **Paths to extract** (history of these paths is kept; everything else stripped):
  - `party-games/` (entire directory)
  - `docs/plans/2026-04-22-party-games-platform-phase-1.md`
  - `docs/plans/2026-04-23-party-games-phase-1d-and-2b.md`
  - `docs/plans/2026-04-23-party-games-platform-phase-5.md`
- Stop before pushing the new repo to any remote.

## Pre-flight

- Install `git filter-repo`: `pipx install git-filter-repo` (or
  `sudo apt install git-filter-repo` if pipx unavailable).
- Backup all engine refs:
  `git -C /home/will/WorldFoundry bundle create ~/wf-backup-2026-05-11.bundle --all`
  (the `WorldFoundry` worktree's `.git` is the canonical store shared by all
  5 worktrees; one bundle covers them all).
- Verify: `git bundle list-heads ~/wf-backup-2026-05-11.bundle | head`.
- Engine worktrees may stay dirty — extraction operates on a clone.

## Steps

1. Mirror-clone the engine repo to a temp dir:
   ```
   git clone --mirror file:///home/will/WorldFoundry/.git /tmp/party-games-extract.git
   ```
2. `cd /tmp/party-games-extract.git`.
3. Filter to keep only party-games-related paths:
   ```
   git filter-repo \
     --path party-games/ \
     --path docs/plans/2026-04-22-party-games-platform-phase-1.md \
     --path docs/plans/2026-04-23-party-games-phase-1d-and-2b.md \
     --path docs/plans/2026-04-23-party-games-platform-phase-5.md
   ```
4. Inspect what survived:
   - `git log --all --oneline | head -30` — expect ~7+ party-games commits +
     the plan-doc commits, authors/dates preserved.
   - `git branch -a` — see which branches retained content.
5. Materialize as a working repo at `~/party-games/`:
   ```
   git clone /tmp/party-games-extract.git ~/party-games
   cd ~/party-games
   ```
6. Tidy the new repo:
   - Pick the latest party-games tip branch (likely `party-games-platform`)
     and rename to `main`: `git branch -m party-games-platform main`.
   - Delete other branches.
   - Remove the `origin` remote pointing at `/tmp/party-games-extract.git`:
     `git remote remove origin`.
7. **Optional path-rename** (recommended): a second filter-repo pass to lift
   `party-games/...` to repo root:
   `git filter-repo --path-rename party-games/:`. Skip if user prefers
   original path structure.
8. Stop. Don't push. Don't touch the engine repo.

## Verification

- `git -C ~/party-games log --oneline | wc -l` matches the count of
  party-games-touching commits in the original repo.
- `git -C ~/party-games log --pretty=format:'%an %ae' | sort -u` — author
  metadata preserved.
- `find ~/party-games -type f -not -path '*/.git/*' | head` — only the
  expected files.
- Engine repo untouched: `git -C /home/will/WorldFoundry log -1 --oneline`
  matches pre-plan; no worktree's `git status` has changed.

## Out of scope

- Anything that modifies the engine repo. See
  [Plan B](2026-05-11-land-master-scrub-party-games.md).
- Pushing `~/party-games/` to a GitHub remote.
