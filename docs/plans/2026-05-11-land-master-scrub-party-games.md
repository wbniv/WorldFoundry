# Plan B — Scrub `party-games/` from engine history and land everything on `master`

**Date:** 2026-05-11
**Status:** Not started
**Precondition:** [Plan A](2026-05-11-extract-party-games.md) complete; `~/party-games/` verified.

## Context

With `party-games/` safely extracted to `~/party-games/`, the engine repo can
have its history rewritten to remove every trace of party-games content. Then
`2026-new-level` (q*bert + tooling) and `2026-ios` land on `master`, giving a
single clean trunk. The user wants **zero `party-games/` trace in engine
history** afterward.

## Decisions

- **Paths to scrub** (same set extracted by Plan A):
  - `party-games/`
  - `docs/plans/2026-04-22-party-games-platform-phase-1.md`
  - `docs/plans/2026-04-23-party-games-phase-1d-and-2b.md`
  - `docs/plans/2026-04-23-party-games-platform-phase-5.md`
- **Keep**: `docs/plans/2026-04-23-chromecast-googletv-port.md` — engine port
  plan, not party-games platform content.
- **Stop before pushing** master to origin. Force-pushing the rewritten
  branches needs collaborator coordination on `2026-ios` (memory: shared
  branch).
- Today's `f0022f3` merge on `2026-ios` does not need an explicit revert —
  the filter pass strips its party-games payload, leaving the codemagic /
  manifest / chromecast-banner content intact.

## Pre-flight (user does first)

- Commit or stash WIP on `2026-new-level`: `actor.cc`, `display.hp`, `cd.iff`,
  `docs/plans/2026-05-10-qbert-physics-hops.md`, `.claude/settings.json`. Plan
  halts until clean.
- Optional: deal with the dirty `wf-status.md` in the `WorldFoundry`
  (2026-googletv) worktree.
- Confirm `~/wf-backup-2026-05-11.bundle` from Plan A still exists (or recreate).

## Phase 1 — Strip party-games from engine repo history

1. Mirror-clone to a sibling: `git clone --mirror
   file:///home/will/WorldFoundry/.git /tmp/wf-strip.git`. (Operating on a
   clone keeps live worktrees safe until the rewritten history is verified.)
2. `cd /tmp/wf-strip.git`.
3. Invert filter — remove the four party-games paths from every commit on
   every branch:
   ```
   git filter-repo \
     --invert-paths \
     --path party-games/ \
     --path docs/plans/2026-04-22-party-games-platform-phase-1.md \
     --path docs/plans/2026-04-23-party-games-phase-1d-and-2b.md \
     --path docs/plans/2026-04-23-party-games-platform-phase-5.md
   ```
4. Verify in the mirror:
   - `git log --all --diff-filter=A -- party-games/` returns nothing.
   - `git log --all --diff-filter=A -- 'docs/plans/*party-games*'` returns
     nothing.
   - `git log --oneline 2026-new-level | wc -l` is roughly previous count
     minus 7 (some merge commits may collapse).
   - `git ls-tree -r 2026-new-level | grep party-games` returns nothing.

## Phase 2 — Replace live engine repo with rewritten history

⚠️ Destructive on local clone — no remote impact yet (push deferred).

Strategy: keep the existing `.git` archived as a safety copy, then point each
worktree at the rewritten mirror.

1. Archive existing store: `tar -czf ~/wf-old-git-2026-05-11.tar.gz -C
   /home/will/WorldFoundry .git`.
2. In any worktree, `git remote add stripped /tmp/wf-strip.git && git fetch
   stripped`.
3. For each branch checked out in a worktree, `git -C <worktree> reset --hard
   stripped/<branch>`. Do every active worktree:
   - `/home/will/WorldFoundry` → `2026-googletv`
   - `/home/will/WorldFoundry.2026-ios` → `2026-ios`
   - `/home/will/WorldFoundry.2026-new-level` → `2026-new-level`
   - `/home/will/WorldFoundry.party-games-platform` → `party-games-platform`
4. Rename `stripped` to `origin` once verified, after dropping/renaming the
   real `origin` to `origin-old` so a stray `git fetch` can't reintroduce
   stripped content.
5. Sanity: every worktree's `git status` should match its pre-rewrite contents
   except for any stripped party-games files.

## Phase 3 — Land everything on `master`

In `/home/will/WorldFoundry.2026-new-level` (now on rewritten history):

1. `git checkout master`.
2. `git merge --no-ff 2026-new-level -m "merge 2026-new-level: q*bert recreation + tooling + everything"`
   — should be conflict-free; rewritten `2026-new-level` is a strict
   descendant of rewritten `master`.
3. `git merge --no-ff 2026-ios -m "merge 2026-ios: iOS port consolidation"` —
   adds 2026-ios's small remaining delta (b247454, d9594d7, 08f32f7 + today's
   plan/TODO docs).
4. **Stop**. No push.

## Phase 4 — Post-rewrite cleanup (TODO follow-ups, not in this plan)

Append to `TODO.md` under `## PLATFORMS`:

- Force-push rewritten branches to origin — coordinate with collaborator on
  `2026-ios` first; they'll need `git fetch && git reset --hard
  origin/<branch>` in their checkout. Affected branches: `master`, `2026-ios`,
  `2026-new-level`, `2026-android`, `2026-googletv`, `party-games-platform`,
  `2026-first-working-gap`, `drop-dead-renderers`,
  `2026-04-14-scripting-language-replacement`.
- Push `~/party-games/` to a new GitHub repo once user picks the target.
- Retire stale local `2026-googletv` + `party-games-platform` branches /
  worktrees (existing TODO entry; subsumed by master-landing).
- Optional reflog purge: `git reflog expire --expire=now --all && git gc
  --prune=now --aggressive` to drop any local references to stripped commits.

## Risks

- **Collaborator on `2026-ios`** — force-push breaks their local clone. Push
  is deferred; user messages them first.
- **filter-repo merge collapsing** — merges whose only contribution was
  party-games collapse to parent. `f0022f3` should *not* (it brought
  codemagic + manifest + banner too). Verify post-Phase 1.
- **`origin` re-poisoning** — after the swap, `git fetch origin` would
  re-introduce stripped commits via `origin/2026-new-level` etc. Phase 2
  step 4 mitigates by renaming the real origin out of the way.
- **Worktree count** — 5 worktrees all need the reset dance. Easy to miss one.

## Verification (end-to-end)

- `git -C /home/will/WorldFoundry.2026-new-level log --all --diff-filter=A -- party-games/`
  returns nothing.
- `find /home/will/WorldFoundry.2026-new-level -name 'party-games' -prune -print`
  returns nothing.
- `git -C /home/will/WorldFoundry.2026-new-level log --oneline master | head`
  shows the two Phase 3 merges on top.
- All 5 worktrees report a clean `git status` after Phase 2.
- `~/wf-old-git-2026-05-11.tar.gz` exists (rollback path).

## Out of scope

- Pushing master or any rewritten branch to origin.
- Pushing `~/party-games/` anywhere.
- Branch retirement (existing TODO; will land naturally once master is the
  authoritative trunk).
