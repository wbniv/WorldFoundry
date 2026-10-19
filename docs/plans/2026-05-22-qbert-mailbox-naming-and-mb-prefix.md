# Q✱bert named mailboxes + project-wide `INDEXOF_` → `MB_` rename (one sweep)

**Status:** Parked 2026-05-22 — plan ready (consolidates the two source docs + a current audit; scope decided as the full project-wide sweep). Unpark when there's appetite for a project-wide re-export of every level.

## Context

Two parked, agreed pieces of work that touch the same files, folded into one sweep
(the second doc explicitly says to do them together to avoid two consecutive
script-source rewrites):

- **A — Q✱bert named mailboxes** ([docs/plans/2026-05-17-qbert-named-mailboxes.md](2026-05-17-qbert-named-mailboxes.md)): `qbert_practice` predates the "no bare mailbox integers in scripts" rule ([[feedback_named_mailbox_constants]]) and still uses raw integers throughout its emitted Forth and in `game.cc`. Add the missing `MAILBOXENTRY` rows and emit named constants.
- **B — `INDEXOF_` → `MB_` rename** ([docs/investigations/2026-05-18-indexof-prefix-removal.md](../investigations/2026-05-18-indexof-prefix-removal.md)): the user wants the verbose `INDEXOF_` scripting-side prefix shortened to `MB_` ([[feedback_indexof_prefix_wanted_gone]]). One-line macro flip + a mechanical sed across all script sources.

**Why one sweep, project-wide:** the prefix is single-sourced at
[`engine/stubs/scripting_stub.cc:72`](../../engine/stubs/scripting_stub.cc)
(`#define MAILBOXENTRY(name,value) { "INDEXOF_" #name, value },`). Flipping it
renames the constant for **every** engine, so any compiled `.lev` still containing
`INDEXOF_*` strings fails to load (the Forth word becomes undefined). The rename
therefore **cannot** be scoped to qbert — every generator level must be
re-exported. Doing A in `MB_` form at the same time means qbert's script is
rewritten once, not twice.

## Current audit (supersedes the 2026-05-17 row list, which was stale)

The qbert script grew since 2026-05-17. Confirmed mailbox slots in
[`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py),
in three buckets:

- **Already named in `mailbox.inc`** (just switch raw int → existing name): `3009/3010/3011`=X/Y/Z_POS, `3014`=ROTATION_C, `3017`=SOUND, `3034/3035`=DELTA_YAW/PITCH, `3037`=FACE_COLOR_TOP, `3040–3042`=X/Y/Z_SCALE, `1910`=HARDWARE_JOYSTICK1_RAW_JUSTPRESSED. **Verify** whether `425/426/427` (ROUND_NUMBER/CHANGED, LAST_LEVEL) already have rows — the `game.cc` audit suggests `425`/`1910` already do; **diff proposed rows against the file and skip duplicates** (a second `MAILBOXENTRY(ROUND_NUMBER,425)` is a redefinition).
- **Qbert-specific, need new rows** (~130 total): HUD `70/71/72`; camshot-zone `100`; per-cube `CUBE_STATE_BASE=200`, `CUBE_PREV_STATE_BASE=228`, `ROUND_TOP_LUT_BASE=256`; player/director `400–438`; visibility `CUBE_VIS_BASE=440`; fully-enumerated enemy slot blocks RB0–2 (`462–485`), GB (`486–493`), Slick (`494–501`), Sam (`502–509`); RB spawn/RNG `511/512/514/517`; **Coily egg internals `518–525` + `FLASH_TICK=545`**, **spike/curve `526–533`**, **disc `534–537`**, `COILY_ROUND_DONE=542`, **`COILY_PHASE_GLOBAL=543`**, `COILY_SPAWN_DELAY=544`; enemy active/spawn-timer mirrors `546–574`; **Coily egg #2 `575–586`** (row…active, L4 only); game-over `GO_BLOCK=590`/`GO_HOLD_TIMER=591`; **popups `592–596`**; **sequencer `597–599`**.
- **NOT mailboxes — leave as integer literals**: actor indices (the trailing arg to `write-actor-mailbox`, e.g. `33` = curse-bubble actor, `*_ACTOR_IDX`), sound-command IDs written *to* `MB_SOUND`, and plain numeric values.

`GLOBAL_USER_MAX` is **1900** (`mailbox.inc:19`); max qbert slot is `599`, all 30xx are per-actor *local* slots — everything fits, no values move.

`INDEXOF_` footprint for the sed (per file): `blender_create_qbert.py` 51, `smb_w1_1/blender_create_smb.py` 34, marble-madness generators ~13, `mm_practice/gen_lev.py` 10, `scripts/patch_*.py` ~25, engine stubs (comments + the `scripting_zforth.cc` spot-check) ~30, plus compiled `.lev` snapshots in marble-madness / mm_practice / mm_practice_blender.

## Approach

Order matters (do not leave any level referencing a prefix that no longer exists):

1. **`mailbox.inc`** — add the qbert rows (bucket 2 above), grouped with comments, following the 2026-05-17 layout. Diff against existing rows; skip any already present. Rows are prefix-agnostic (`MAILBOXENTRY(NAME, val)`).
2. **`game.cc`** (~lines 551–610) — replace raw `70/71/72/420/590/591` with `EMAILBOX_*` (and the already-named `1910`/`425`). `EMAILBOX_` is the C++ enum prefix — unaffected by the `MB_` rename, which only touches the scripting-side string.
3. **Flip the prefix** — `engine/stubs/scripting_stub.cc:72` `"INDEXOF_"` → `"MB_"`; update the doc comments + spot-check `zf_eval(..., "INDEXOF_CAMSHOT")` → `"MB_CAMSHOT"` at [`scripting_zforth.cc:~24,~305`](../../engine/stubs/scripting_zforth.cc).
4. **Rewrite `blender_create_qbert.py`** to emit **`MB_*`** names instead of raw integers — change the enemy `_mb()` helpers to return symbolic field names (`f"MB_RB{k}_{field}"` etc.) and the module mailbox constants from numeric to `"MB_…"` strings; replace any inline integer literals (`400 read-mailbox`) with the token. Actor-index args stay integers. (Pattern detailed in the 2026-05-17 plan § rewrite pattern — substitute `MB_` for `INDEXOF_`.)
5. **Sed every other script source**: `git grep -l 'INDEXOF_' -- 'wflevels/**/*.py' 'wflevels/**/*.lev' 'wflevels/**/*.aib' 'scripts/**/*.py' | xargs sed -i 's/\bINDEXOF_/MB_/g'`, plus the engine-stub comment lines. (qbert `.py` is handled by step 4, not the sed.)
6. **`task build`** — rebuild the engine; **verify the binary timestamp advanced** (`ls -la engine/wf_game`) per [[feedback_verify_build_binary]] — don't trust piped output.
7. **Re-export + rebuild every generator level** (qbert, smb_w1_1, marble-madness ×variants, mm_practice, mm_practice_blender): `blender --background --python <gen>.py` then `bash wftools/wf_blender/build_level_binary.sh <level>` per [[feedback_qbert_blender_build_pipeline]]. Standalone `.lev` snapshots without a generator get the sed only.
8. **`docs/qbert/catalogue.md`** — rewrite the 10 embedded Forth blocks to mirror the emitted `MB_*` Forth.

## Critical files

- [`wfsource/source/mailbox/mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) — +~130 qbert rows.
- [`engine/stubs/scripting_stub.cc`](../../engine/stubs/scripting_stub.cc):72 — the prefix flip; [`scripting_zforth.cc`](../../engine/stubs/scripting_zforth.cc) — comments + spot-check.
- [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py) — emit `MB_*` names.
- [`wfsource/source/game/game.cc`](../../wfsource/source/game/game.cc) — raw ints → `EMAILBOX_*`.
- All other `wflevels/**/blender_*.py`, `wflevels/**/*.lev`, `wflevels/**/*.aib`, `scripts/patch_*.py` — sed.
- [`docs/qbert/catalogue.md`](../qbert/catalogue.md) — snippet rewrite.

## Gotchas

- **Mesh-export non-determinism** (TODO § TOOLS, surfaced 2026-05-22): re-exporting qbert re-writes `player.iff`/`coily_snake_mesh.iff` byte-differently with no real change; other levels likely do too. `git checkout HEAD --` the mesh `.iff`s that only differ by float-noise, then rebuild the bundle, to keep the diff to script-string changes. Don't let it bloat the commit.
- **`.lev` vs `.blend` drift** ([[feedback_blender_golden_source]]): for a level with a generator, the sed on its `.lev` is overwritten by the re-export — fine. But audit (`git log -p`) any `.lev` hand-edited since its generator last changed before sed+re-export clobbers it (the 2026-05-18 doc flags marble-madness snapshots specifically).
- **No name collisions** to resolve first — `MB_FALSE`/`MB_TRUE`/`MB_X_POS` shadow nothing (the win over dropping the prefix). Quick confirming grep before the flip.
- **Skip duplicate rows** — don't redefine `MAILBOXENTRY`s that already exist (425/426/427/1910 likely do).

## Verify

1. `task build` succeeds + binary timestamp advanced; `MB_CAMSHOT` spot-check prints the expected value at zforth init.
2. `python3 -m py_compile wflevels/qbert_practice/blender_create_qbert.py` (and any other edited generator) per [[feedback_py_compile_check]].
3. **Per-level smoke** ([2026-05-18 doc § Verification matrix]): snowgoons player walks + camera tracks; **qbert** — re-run `tests/test_director_mailbox.py` (16-round regression) + an in-game screenshot via `tests/screenshot_qbert_enemies.py` ([[feedback_screenshots_for_proof]], [[project_qbert_bridge_screenshot]]); **smb_w1_1** — `tests/verify_smb_scroll.py`; marble-madness — best-effort visual.
4. **Residual-literal grep** in qbert: `grep -nE '\b[0-9]{2,4}\s+(read|write)-(actor-)?mailbox' wflevels/qbert_practice/blender_create_qbert.py` → only `write-actor-mailbox` actor-idx args and sound IDs should remain (review by hand).
5. **Residual-prefix grep**: `git grep -n 'INDEXOF_' -- 'wflevels' 'scripts' 'engine/stubs'` → only historical doc text (don't touch per the 2026-05-18 doc § Risks #5).
6. Behaviour is byte-identical at runtime (names resolve to the same integers), so all smoke tests should pass unchanged.
7. Commit engine + scripts + rebuilt binaries + this doc as one logical change ([[feedback_commit_docs_with_code]]); note duration ([[feedback_plan_duration_tracking]]). Update the two parked docs' Status to point here as the executed sweep.

## Out of scope

- The separate `read-actor-mailbox` primitive and the `write-actor-mailbox` removal question (TODO § SCRIPTING INFRASTRUCTURE) — naming only here.
- `mm_practice`'s own qbert-unrelated raw-int mailboxes beyond what the sed/rename touches.
