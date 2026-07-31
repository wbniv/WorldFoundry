---
name: Stage files explicitly when committing
description: git commit -am sweeps up pre-existing unrelated deletions in the working tree (wfsource/, wflevels/); always stage named files
type: feedback
originSessionId: f3a787ff-e88f-44fa-8fd7-2cf3a966f5ee
---
Don't use `git commit -am` in this repo. The working tree has long-standing pre-existing changes under `wfsource/` and `wflevels/` (deletions and untracked dirs that have been there since session start) that are NOT ours to ship. `-a` stages every tracked modification including those deletions. Happened twice today; had to `git reset HEAD~1 --soft` + unstage + recommit both times.

**Why:** The repo is a working copy where the user has in-progress work across many areas. Our touches are confined to `party-games/` and `docs/plans/`, and commits need to stay that scoped — sweeping up unrelated deletions makes commits misleading and risks destroying work if ever force-pushed.

**How to apply:** `git add <specific paths>` then `git commit -m …` — never `commit -a` or `commit -am`. For the Party Games project specifically, the scope is `party-games/**` and `docs/plans/**`.
