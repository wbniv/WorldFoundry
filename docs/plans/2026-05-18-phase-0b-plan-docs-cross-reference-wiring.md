# Commit: Phase 0b plan docs + cross-reference wiring

**Status:** DONE — Phase 0b plan docs ([frame-step API](2026-05-18-engine-frame-step-api.md), [external GL context](2026-05-18-engine-external-gl-context.md)) created and cross-linked.

## Context

This session created two parked plan docs for the still-open Phase 0b sub-tasks of the collaborative editor work (sub-tasks #3 and #4 already shipped earlier today as `b0639c5` / `1a957f7` / `89bcb58`):

- `docs/plans/2026-05-18-engine-frame-step-api.md` — sub-task #1, split `WFGame::RunLevel` into `StepFrame`
- `docs/plans/2026-05-18-engine-external-gl-context.md` — sub-task #2, accept editor-owned `XDisplay*` / `Window` / `GLXContext`

Plus three small wiring edits so existing docs link to the new plans:

- `docs/investigations/2026-05-18-collaborative-level-editor-design.md` — Phase 0b sub-task #1 / #2 bullets in the Tier 1 entry now link to the plan docs.
- `TODO.md` — Phase 0b TODO entry now references both plan docs.
- `wf-status.md` — both plans added to the Backlog table.

The user said "commit" — straightforward request to land this session's plan-doc work.

## What to commit

Stage exactly these five files:

- `docs/plans/2026-05-18-engine-frame-step-api.md` (NEW)
- `docs/plans/2026-05-18-engine-external-gl-context.md` (NEW)
- `docs/investigations/2026-05-18-collaborative-level-editor-design.md` (link edits)
- `TODO.md` (link edits)
- `wf-status.md` (Backlog table + bundled-in user History edit, see below)

## Bundling caveats

Two files in the staging set carry the user's parallel uncommitted work that will ride along:

- **`wf-status.md`** also contains the user's earlier-today History edit: the `2026-05-17 → 2026-05-18` date bump, `36 → 37 days` count, and the "SMB Mario movement retune + Jolt airborne sync fix" history paragraph. That paragraph references `docs/plans/2026-05-18-smb-mario-movement-retune.md`, which remains untracked — the link will dangle until that plan doc is committed separately.
- **`TODO.md`** previously bundled user TODO edits (INDEXOF prefix rename, UV float-passthrough plan reference) in the prior commit `5ecbcbe`; this commit only adds a 2-line edit to the existing Phase 0b entry, no new dangling refs from this commit.

The user's other in-flight work (transcripts, `.iff` / `.lvl` / `.blend` artifacts under `wflevels/smb_w1_1/`, `wfsource/source/movement/movement.cc`, `wfsource/source/physics/jolt/jolt_backend.cc`, MP4 captures, ROM zips, asset directories) stays out of this commit — those are separate concerns for the user to commit themselves.

## Commit message

```
docs(editor): Phase 0b plan docs — frame-step API + external GL context

Two parked plans for the still-open Phase 0b sub-tasks #1 and #2 of the
collaborative editor work (sub-tasks #3 and #4 shipped earlier today).
Both follow the UV-plan template (Context, Architectural approach, Files
modified, Verification, Risks, Implementation sequence). Both note they
are independent of each other — either can land first.

- docs/plans/2026-05-18-engine-frame-step-api.md (NEW) — split
  WFGame::RunLevel into Level::Step(dt) + WFGame::StepFrame(do_swap,
  out_dt); promote _curLevel / _bContinue to members; add LoadLevel /
  UnloadLevel; deltaTime clamp at ≤100 ms; Display::MeasureDelta() so
  do_swap=false callers still recover deltaTime.

- docs/plans/2026-05-18-engine-external-gl-context.md (NEW) — new
  host_gl_context.h opaque interface; InitWithExistingContext path in
  mesa.cc; early-bails in HALCloseWindow / XEventLoop; HALRequestClose()
  for host-driven close; mobile stubs.

Cross-reference wiring:
- collaborative-level-editor-design.md: Phase 0b sub-task #1 / #2 bullets
  link to the plan docs.
- TODO.md: Phase 0b entry references both plan docs.
- wf-status.md: both plans added as Parked rows in the Backlog table.

Bundled in wf-status.md: the user's parallel History edit for SMB Mario
movement retune (date 17→18, +1 day, new history paragraph). The plan
doc that paragraph references (docs/plans/2026-05-18-smb-mario-movement-
retune.md) remains untracked — link will resolve in a separate commit.
```

## Verification

After committing:

1. `git log -1 --stat` — confirms 5 files in the commit (2 new + 3 modified).
2. `git show --name-only HEAD` — confirms only the intended files shipped; nothing from `wflevels/`, `wfsource/`, or transcripts rode along.
3. `git status` — confirms the untracked files we deliberately left out (other plan/investigation docs, transcripts, artifacts) are still untracked.

## Critical files

- `docs/plans/2026-05-18-engine-frame-step-api.md` — new plan
- `docs/plans/2026-05-18-engine-external-gl-context.md` — new plan
- `docs/investigations/2026-05-18-collaborative-level-editor-design.md` — link wiring
- `TODO.md` — link wiring
- `wf-status.md` — Backlog rows (+ bundled user History edit)

## Out of scope

- The user's other uncommitted modifications and untracked files are intentionally not staged. They are separate work streams (SMB Mario movement, transcripts, build artifacts, etc.) that the user is expected to commit themselves at their own cadence.
