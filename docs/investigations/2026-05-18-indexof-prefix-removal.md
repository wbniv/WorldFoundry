# Rename the `INDEXOF_` prefix to `MB_` on scripting-side mailbox constants

**Status:** Parked 2026-05-18. We will do this; not right now.

**Trigger to unpark:** Next round of mailbox-naming work — natural pair with the in-flight [`docs/plans/2026-05-17-qbert-named-mailboxes.md`](../plans/2026-05-17-qbert-named-mailboxes.md) since that touches `mailbox.inc` + script source heavily. Doing both in one sweep avoids two consecutive script-source rewrites.

---

## Context

Mailbox names exposed to scripting engines (Forth, Lua, JS, WASM) all carry an 8-character `INDEXOF_` prefix: `INDEXOF_X_POS`, `INDEXOF_HARDWARE_JOYSTICK1_RAW`, `INDEXOF_SMB_PLAYER_X`, etc. The prefix is **mostly noise**:
- Every constant in the scripting constant table *is* an index by definition.
- The C-side already has its own `EMAILBOX_` prefix for the C enum.

The user wants the prefix shortened to **`MB_`** (3 chars, ~62% fewer characters per use). Same purpose — marks the symbol as a mailbox constant so it doesn't blur with Forth/Lua/JS identifiers — without the visual weight.

The whole project's mailbox prefix is single-sourced from one line at [`engine/stubs/scripting_stub.cc:72`](../../engine/stubs/scripting_stub.cc):

```c
#define MAILBOXENTRY(name,value)  { "INDEXOF_" #name, value },
```

That `#define` stamps `"INDEXOF_"` onto every entry of the constant table that `ScriptRouter` broadcasts to every engine at init. Change the string literal and the prefix changes everywhere downstream.

Discovered while implementing SMB scrolling-camera Director (2026-05-17/18) — three new entries (`INDEXOF_SMB_PLAYER_X`, `_TARGET_CAM_X`, `_MAX_CAM_X`) were added without questioning the convention; the user flagged the regret and clarified the preference is to **rename**, not drop. See [`feedback_indexof_prefix_wanted_gone`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_indexof_prefix_wanted_gone.md).

## Why rename instead of drop entirely

Earlier draft of this plan considered dropping the prefix outright (so `INDEXOF_X_POS` → `X_POS`). Trade-off analysis:

| | Drop entirely (`X_POS`) | Rename to `MB_` (`MB_X_POS`) |
|-|-|-|
| Verbosity | minimal | 3 chars |
| Marks "this is a mailbox constant" | no | yes |
| Forth `TRUE`/`FALSE` collision with `MAILBOXENTRY(TRUE,1)`/`(FALSE,0)` | **collides** (Forth has built-in `TRUE` = -1) — needs rename in mailbox.inc first | no collision (`MB_TRUE` / `MB_FALSE` don't shadow anything) |
| Confusion with local variables (`X_POS`, `INPUT`, `KIND` are short enough to look like locals) | possible | mitigated by `MB_` prefix |
| Migration scope | same | same |

The `MB_` rename keeps the marker (so readers know `MB_X_POS` is a system constant, not a local Forth word) without the verbosity of `INDEXOF_`. Drops the FALSE/TRUE collision concern that was the messiest part of the prefix-drop approach. Same one-line engine change, same sed across script source.

## Scope

### 1. Engine change (one line)

[`engine/stubs/scripting_stub.cc:72`](../../engine/stubs/scripting_stub.cc):

```c
// before:
#define MAILBOXENTRY(name,value)  { "INDEXOF_" #name, value },
// after:
#define MAILBOXENTRY(name,value)  { "MB_" #name, value },
```

Rebuild the engine (`task build`). All engines (Forth, Lua, JS, WASM) pick up the new constant table at init via `AddConstantArray`.

### 2. Script-source updates

`grep -rln INDEXOF_ wflevels/ engine/stubs/` shows the footprint:

| File | `INDEXOF_` count | Notes |
|------|------------------|-------|
| `wflevels/qbert_practice/blender_create_qbert.py` | 51 | Director + per-cube scripts |
| `wflevels/smb_w1_1/blender_create_smb.py` | 27 | Player + Director + CamShot |
| `wflevels/snowgoons-blender/snowgoons.lev` | 2 | Player input passthrough |
| `wflevels/snowgoons-blender/snowgoons-blender.lev` | 2 | Same |
| `wflevels/marble-madness/blender_*.py` (multiple drivers) | a few each | MM variants |
| `wflevels/marble-madness/*.lev`, `wflevels/marble-madness-2/*.lev` | a few each | Compiled snapshots |
| `wflevels/mm_practice/*.lev`, `wflevels/mm_practice_blender/*.lev` | a few each | More compiled snapshots |
| `wflevels/smb_w1_1/smb_w1_1.lev` | small | Will regenerate from .py |
| `wflevels/shell.aib` | small | Shell-menu script |
| `engine/stubs/scripting_{lua,js,zforth,wamr,libforth,quickjs,forth}.{hp,cc}` | inline comments mentioning `INDEXOF_*` | Documentation, not code |

**Mechanical rewrite:**

```bash
git grep -l 'INDEXOF_' -- 'wflevels/**/blender_*.py' 'wflevels/**/*.lev' 'wflevels/**/*.aib' | \
    xargs sed -i 's/\bINDEXOF_/MB_/g'
```

After the sed pass, re-export each level via its `blender_create_*.py` headless run, then `wftools/wf_blender/build_level_binary.sh <level>` so compiled artefacts (`.lev.bin`, `.lvl`, `.iff`, `.iff.txt`, `Room*.tga`, `Perm.tga`) regenerate with the renamed script strings embedded.

### 3. Engine-side documentation comments (cosmetic)

`engine/stubs/scripting_zforth.cc:24-25`:
```c
//   3024 constant INDEXOF_INPUT
//   1009 constant INDEXOF_HARDWARE_JOYSTICK1_RAW
```
and `scripting_zforth.cc:305-308`:
```c
// Spot-check: verify INDEXOF_CAMSHOT loaded correctly.
if (zf_eval(&g_ctx, "INDEXOF_CAMSHOT") == ZF_OK) {
    ...
    fprintf(stderr, "zforth: INDEXOF_CAMSHOT = %d (expect 1021)\n", (int)v);
}
```

Update the comments and the spot-check eval string (`"INDEXOF_CAMSHOT"` → `"MB_CAMSHOT"`).

### 4. Verification

| Level | What to verify |
|-------|----------------|
| `snowgoons-blender` | Player walks, camera tracks (canonical smoke test per `project_engine_runnable`). |
| `qbert_practice` | Director's per-frame cube colour pulse fires (16 rounds × cube-state cycle). Existing `tests/test_director_mailbox.py` is the regression catch — re-run. |
| `mm_practice` | Marble rolls into the trough; SW iso camera tracks. |
| `smb_w1_1` | Scrolling camera signal-chain still works — re-run `tests/verify_smb_scroll.py`. |
| `mm_*` (other variants) | Best-effort visual check; not on critical path. |

## Risks / gotchas

1. **No name collisions to resolve first** (this is the win over the prefix-drop variant). `MB_FALSE`, `MB_TRUE`, `MB_X_POS`, etc. don't shadow any Forth/Lua/JS built-ins. Quick sanity grep should still confirm before flipping the macro, but the expected answer is "no collisions".

2. **Compiled `.lev` files vs Blender source.** Per [`feedback_blender_golden_source`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md), the `.blend` is the golden source; compiled `.lev` should always be regenerable from a Blender export. Mass-sed on `.lev` text files works, but if any `.lev` has drifted from its `.blend` (hand-edited script blocks), the sed pass plus re-export-from-Blender could overwrite the hand edits. Audit: `git log -p` each level's `.lev` since its `blender_create_*.py` last changed.

3. **Marble Madness `.lev` snapshots.** `wflevels/marble-madness/` includes both `blender_*.py` generators *and* compiled `.lev` snapshots. The `.lev` text format embeds Forth/Lua script strings inline. Sed needs to handle these embedded strings — confirm with one MM `.lev` file before doing the rest.

4. **zForth dictionary entries.** Each constant takes a dict entry; renaming doesn't change the count, just the name length. The 32 KB `ZF_DICT_SIZE` budget tracked in [`TODO.md` § SCRIPTING ENGINES](../../TODO.md) is unaffected. Modest per-entry savings (`INDEXOF_` − `MB_` = 5 bytes per name × ~60 mailboxes ≈ 300 bytes recovered).

5. **Existing investigation / plan docs that quote `INDEXOF_*` names** stay correct as historical record — don't touch them. New docs use the `MB_*` names.

## Migration sequence

1. Engine: flip `scripting_stub.cc:72` to `"MB_"`.
2. Engine: update doc comments + spot-check string in `scripting_zforth.cc`.
3. `task build` — rebuild engine.
4. Sed: `git grep -l 'INDEXOF_' -- 'wflevels/**/blender_*.py' 'wflevels/**/*.lev' 'wflevels/**/*.aib' | xargs sed -i 's/\bINDEXOF_/MB_/g'`.
5. For each level with a `blender_create_*.py`: re-export headless + run `build_level_binary.sh`.
6. Run verification matrix from § Verification above.
7. Commit as one logical change (engine + scripts + rebuilt binaries).

## Estimated effort

- Engine + doc-comment edits: 5 minutes.
- Sed pass across script sources: 5 minutes.
- Rebuild engine + each level + smoke-test: 30-60 minutes.
- Buffer: 30 minutes.

**Total:** ~2 hours, mostly mechanical, single-day work when triggered.

## Related

- Convention source: [`feedback_named_mailbox_constants`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_named_mailbox_constants.md) — scripts should reference named constants, not bare integers. Still correct; this plan changes *which* name.
- User preference memo: [`feedback_indexof_prefix_wanted_gone`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_indexof_prefix_wanted_gone.md).
- In-flight naming work: [`docs/plans/2026-05-17-qbert-named-mailboxes.md`](../plans/2026-05-17-qbert-named-mailboxes.md) — the user's own active plan that touches mailbox.inc + qbert script source; natural place to fold this in.
- Single-edit-point that makes this cheap: [`engine/stubs/scripting_stub.cc:72`](../../engine/stubs/scripting_stub.cc).
- Cross-language audit confirming the constant table is broadcast uniformly: [`TODO.md` § SCRIPTING INFRASTRUCTURE](../../TODO.md) — "[investigated] Mailbox constants cross-language audit".
