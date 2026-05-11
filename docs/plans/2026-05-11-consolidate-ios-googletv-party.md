# Plan: Consolidate Chromecast/iOS work onto 2026-ios

**Date:** 2026-05-11
**Status:** In progress
**Branch:** `2026-ios`, worktree `/home/will/WorldFoundry.2026-ios`
**Goal:** Bring the scattered Chromecast/Android-TV work onto the canonical iOS
trunk so further iOS + Chromecast work proceeds from one branch.

## Context

The branch landscape drifted into a confusing state:

- The branch literally named `2026-googletv` mostly holds **iOS** Metal/Simulator
  work (not Google TV).
- The actual Chromecast/Android-TV work is split across two branches —
  `origin/2026-googletv` (collaborator-pushed, single Phase 0+1 commit) and
  `party-games-platform` (alternate Phase 0+1 plus 16 follow-ups debugging the
  Codemagic Android workflow).
- `2026-ios` is the canonical iOS branch (per the shared-collaborator note).

Consolidating onto `2026-ios` keeps both Chromecast Phase 0+1 and the iOS Metal
pipeline in one place and lets the literal `2026-googletv` and
`party-games-platform` branches be retired in a follow-up.

## Branch reality (verified 2026-05-11)

```
master (71727ab)
 └── da9e5ee  (merge-base of every iOS-ish branch)
      ├── 2026-ios            (b247454)  ← target trunk
      │     +b247454 ios: enable Jolt physics
      │     +d9594d7 codemagic: ios-device-release stub
      │     +08f32f7 status: iOS Phase 3 verified
      ├── 2026-googletv local (bcc74c6) ← STRICT ANCESTOR of 2026-ios
      ├── origin/2026-googletv (0f4cf64) ← collaborator-pushed, 4 ahead of local
      │     +199db7d chromecast: Phase 0+1 (banner + Codemagic Android workflow)
      │     +0f4cf64 broken           ← deletes wflogo.gif (222 B)
      │     d9594d7, 08f32f7 already on 2026-ios
      └── party-games-platform (5fda0df) ← 18 ahead of merge-base
            chromecast plan doc + alternate Phase 0+1 commit (943a14e)
            + 16 codemagic-android workflow iteration commits
            (linux→mac→linux switch, sdkmanager path-find, SIGPIPE fix,
             jolt tarball extract, NDK/Gradle cache)
```

- Local `2026-googletv` is fully contained in `2026-ios` — no rescue needed.
- `origin/2026-googletv` has 2 unique commits (`199db7d`, `0f4cf64`) the
  collaborator pushed; locally we never pulled them.
- `party-games-platform`'s Phase 0+1 (`943a14e`) and `origin/2026-googletv`'s
  (`199db7d`) both end with the same 10 835 B `tv_banner.png`, but the
  party version is the one paired with the working/debugged Codemagic Android
  workflow.

## Decisions

1. **Source for Chromecast Phase 0+1**: `party-games-platform` line — full
   18-commit history including the debugged Codemagic Android workflow. Cherry
   pick anything unique from `199db7d` on top if needed.
2. **`0f4cf64 "broken"`**: drop. The diff is just a 222 B `wflogo.gif`
   deletion; commit message itself says "broken".
3. **Branch retirement**: deferred. Tracked as a follow-up in
   [TODO.md](../../TODO.md) under `## PLATFORMS` once consolidation is verified.

## Steps

0. Persist this plan to `docs/plans/` and commit on `2026-ios` (this commit).
1. Confirm clean `git status` in `/home/will/WorldFoundry.2026-ios` (one
   harmless stat-only change to `scripts/git-branch-browser.py` may sit in the
   tree — leave alone; party-games-platform doesn't touch that file).
2. `git fetch origin`.
3. `git merge --no-ff party-games-platform -m "merge party-games-platform: chromecast Phase 0+1 + Codemagic Android workflow"`
   — expect zero conflicts (merge-base is `da9e5ee`; only `codemagic.yaml` is a
   plausible conflict surface and the iOS workflow lives in a separate block).
4. Inspect `origin/2026-googletv`'s `199db7d` against the merged tree. If its
   `AndroidManifest.xml` line (the only file party's `943a14e` skipped) is not
   already present, cherry-pick **just that delta**.
5. **Drop** `0f4cf64 "broken"`.
6. **Confirm with user before pushing** `2026-ios` to origin.
7. Add follow-up TODO entry to `TODO.md` under `## PLATFORMS`:
   ```
   - [ ] Retire stale branches/worktrees post-consolidation — delete local
     `2026-googletv` (worktree `/home/will/WorldFoundry`, primary checkout —
     needs care) and `party-games-platform` (worktree
     `/home/will/WorldFoundry.party-games-platform`); leave origin refs alone
     unless collaborator confirms.
   ```
   Commit on `2026-ios`.

## Critical files to watch during merge

| File | Risk |
|------|------|
| `codemagic.yaml` | Touched by both chromecast commits **and** by 2026-ios's iOS workflow tweaks. Most plausible conflict surface. |
| `android/app/src/main/AndroidManifest.xml` | Touched by `199db7d` only; party-games-platform's `943a14e` skipped it. May need a small cherry-pick. |
| `android/app/src/main/res/drawable/tv_banner.png` | Both end at 10 835 B; whichever lands is fine. |
| `wflogo.gif` / `wflogo.png` | Small images that have been added/removed several times; verify final state coherent. |

## Out of scope

- The `2026-new-level` → `2026-ios` merge (qbert + tooling work, 250+ commits) —
  separate decision; the user originally asked about merging into the Chromecast
  branch, not into 2026-ios. Flag at end.
- Pushing the merge to origin — confirm before pushing.
- Any actual Chromecast Phase 2/3 device verification (still needs hardware).
- Deletion of stale local branches/worktrees — deferred to TODO follow-up.

## Verification

- `git -C /home/will/WorldFoundry.2026-ios log --oneline -20` shows
  `party-games-platform` commits + a merge commit.
- `git -C /home/will/WorldFoundry.2026-ios diff master -- android/ codemagic.yaml`
  shows the chromecast Phase 0+1 (banner, manifest, `android-apk-debug` workflow).
- `git rev-list --count 2026-ios..party-games-platform` returns `0`.
- `git rev-list --count 2026-ios..origin/2026-googletv` returns `0` (assuming
  `199db7d` was either picked or its content covered, and `0f4cf64` dropped).
