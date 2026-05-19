# SMB `?`-block coin — fix the off-by-one first, refactor to a template second

**Status:** In progress 2026-05-19. Plan approved 2026-05-18 (originally drafted at `~/.claude/plans/abstract-wishing-map.md`); filed in repo today per workflow. **Phase 1 premise turned out to be wrong** — see "Phase 1 update" below. The plan now bridges into deeper diagnosis OR jumping to Phase 2.

## Context

Commit [`8a4f822`](../../wflevels/smb_w1_1/blender_create_smb.py) shipped a pre-placed `qblock_00_coin` anchored statplat per `?`-block, with mailboxes 1805 / 1806 toggling its visibility + animating its Z via `write-actor-mailbox` from Mario's per-tick Forth. User reported two problems:

1. **No coin appears interactively.** Originally diagnosed (incorrectly) as an off-by-one in `COIN_ACTOR_IDX`.
2. **Wrong shape architecturally.** A full SMB level produces many coins; one pre-placed actor per coin slot doesn't scale.

User chose: fix Phase 1 as a cheap win first, hard pause for visual verification, then Phase 2 refactor.

### Standing directive — level-designer's-guide updates during execution

Both phases touch level authoring (Blender export, mailbox conventions, template-object machinery, Generator wiring). Any **gotcha, clever technique, hack, surprise, or non-obvious workaround** discovered during execution must be written to the designer-facing docs **immediately when discovered**, not batched at the end:

- Symptom-shaped problems + workarounds → [`docs/level-design-troubleshooting.md`](../level-design-troubleshooting.md) (the running gotcha log; sorted by diagnosis time).
- New authoring conventions or genuinely interesting techniques → [`docs/level-building.md`](../level-building.md).

Two entries logged so far this run:
- ["Runtime actor indices do NOT match the .lev OBJECT ordering"](../level-design-troubleshooting.md) — counted-from-`.lev` indices are usually off-by-one or off-by-two vs. what `--debug-print-actors` reports.

## Phase 1 update — premise wrong, no cheap win

`engine/wf_game --debug-print-actors` after rebuild confirms the coin is at runtime **idx 14**, exactly where the original `COIN_ACTOR_IDX = 14` placed it. The explore agent that diagnosed "the coin is at 13" miscounted `.lev` OBJECT entries — runtime indices include implicit actors at low slots:

```
actor idx=12 mesh=qblock_00.iff
actor idx=13 mesh=qblock_00_used.iff
actor idx=14 mesh=qblock_00_coin.iff   ← coin
actor idx=15 mesh=qblock_01.iff
```

Further diagnosis ruled out (against both [`level-design-troubleshooting.md`](../level-design-troubleshooting.md) and [`level-building.md`](../level-building.md)):

| Documented cause | Status for coin |
|---|---|
| Position on room bbox boundary → PERM | Center (12, 0, 7.5) is well inside Room01 |
| Camera FOV culling | Bump-flip gold→tan IS visible in same frame |
| `Model Type = NONE` | `.lev` shows `Mesh` (twice, both consistent) |
| Visibility Mailbox = 0 | Forced to hardwired `=1`; still invisible |
| Falls outside every room bbox | `RenderActor3DAnimates` log count = 11 (matches all mesh actors incl. coin) |
| FLAT_SHADED vs TEXTURE_MAPPED | Parsed both `.iff` files; coin has `flags=0x00000000 color=0x00ffd600 texname=''` |
| Empty atlas / texture fallback | Same — no texture |
| Wrong face normals | Same `make_mat()` + `add_box()` path as the rendering used-block |
| Two `Mesh Name` fields | Coin has ONE `Mesh Name` |

User's hint: a prior bug was "wrong coordinate system → object invisibly thin from the side camera angle." Diagnostic tests are now mid-flight: **(a)** fatten Y from 0.04 m to 0.2 m, **(b)** raise `coin_z` from `BLOCK_Z + BSIZE` (= 7.5) to `BLOCK_Z + BSIZE + COIN_R` so the coin sits fully above the block top instead of half-embedded in it. Both applied together to either rule out or pin down the geometry issue.

Hit a side-issue mid-test: `--debug-port` flag isn't being parsed by the current engine binary (engine was rebuilt mid-session); the bridge ends up unbound and `set_mailbox`/`screenshot` ops go to the REST API on `:8765` which silently drops them. Workaround: capture the X11 window externally, OR rebuild the engine if `--debug-port` parsing regressed.

## Phase 2 — template-object refactor (deferred until Phase 1 closes)

User picked **Generator + mailbox** over a new zForth `spawn-template` primitive; Forth-side gaps surfaced during execution get logged as TODOs rather than fixed inline.

### Design

**Coin template** in `blender_create_smb.py`:
- Class `Stat` (verify gravity support in [`wfsource/source/oas/stat.oas`](../../wfsource/source/oas/stat.oas) during execution).
- `wf_Template Object = 1`. Verify exact custom-prop key via [`wftools/wf_blender/panels.py`](../../wftools/wf_blender/panels.py).
- Yellow disc, half-extents X=Z=0.3 m, Y=0.08 m.
- Parked off-screen — templates aren't placed in `_actors[]` (see [`level.cc:520-550`](../../wfsource/source/game/level.cc)).
- `Falling Acceleration` ≈ 12 m/s². Gravity arcs the coin.
- Per-instance suicide: tiny Forth script that writes `INDEXOF_SUICIDE 1 write-actor-mailbox` once Z falls below block top. Audit whether the suicide mailbox is wired; log TODO under SCRIPTING ENGINES if not.

**Per-block Generator**:
```python
spawner = add_generator(
    f'coin_spawner_{i:02d}',
    position=(bx, 0, BLOCK_Z + BSIZE + 0.4),
    object_to_throw='coin_template',
    activation_mailbox=MB_SMB_QBLOCK_0_COIN_SPAWN,
    generation_rate=10.0,                  # effective one-shot per pulse
    object_velocity=(0, 0, 8.0),           # ~2 m peak under g=12
)
```

**Mailbox changes** in [`wfsource/source/mailbox/mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc):
- Remove `SMB_QBLOCK_0_COIN_VISIBLE` (1805) + `SMB_QBLOCK_0_COIN_PHASE` (1806).
- Add `SMB_QBLOCK_0_COIN_SPAWN` (1805) — generator activation pulse.
- Per `feedback_indexof_prefix_wanted_gone`: still propagating `INDEXOF_` prefix; eventual fix at [`engine/stubs/scripting_stub.cc:72`](../../engine/stubs/scripting_stub.cc), tracked separately.

**Mario's Forth script** — strip kickoff + per-tick animation; replace with a one-tick latch:
```forth
\ inside bump branch
1 INDEXOF_SMB_QBLOCK_0_COIN_SPAWN write-mailbox

\ end-of-script clear (next tick after spawn)
INDEXOF_SMB_QBLOCK_0_COIN_SPAWN read-mailbox 0<> if
  0 INDEXOF_SMB_QBLOCK_0_COIN_SPAWN write-mailbox
then
```

Tick N: bump sets 1; tick N+1: generator fires + Mario clears; tick N+2: both see 0.

### Reusable in-tree machinery

- [`Level::ConstructTemplateObject`](../../wfsource/source/game/level.cc) at `level.cc:1672`; collision-safe wrapper at `:1572`.
- [`Generato::update()`](../../wfsource/source/game/generator.cc) at `:64-115` — activation-mailbox gate + spawn loop.
- [`generator.oas`](../../wfsource/source/oas/generator.oas) at `:9-30` — Generator OAS schema.
- [`flagbloc.inc:8`](../../wfsource/source/oas/flagbloc.inc) — `Template Object` field.

### Out of scope (both phases)

- Generalising to blocks 1 + 2 (cheap follow-up).
- Single shared generator that takes a runtime position.
- `+200` score popup, coin pickup sound.
- A Forth `spawn-template` primitive.
- Coin–Mario collision shaping.

## Verification

- `engine/build_game.sh` succeeds.
- `--debug-print-actors` confirms expected actor index for the spawned coins.
- Interactive bump: gold→tan flip + visible coin arc. Screenshots at `~/tmp/smb-shots/coin_template_*.png` (capture path TBD — bridge issue from Phase 1 must be resolved or worked around).
- Regression: gold→tan flip from `f4071a3` still works; block bumped only once.
