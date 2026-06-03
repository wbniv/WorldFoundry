# Plan: `smb_common.py` extraction + per-type mesh sharing

**Date:** 2026-06-02
**Status:** Not started

> On approval, implement in phases below, committing per phase. Back-references:
> [shared-mesh-library plan](2026-06-01-smb-shared-mesh-library.md) (the gallery + the
> dedup approach this finishes) and [fireworks + faithful W1-2](2026-06-01-smb-fireworks-rework-and-faithful-w1-2.md)
> (whose B0 deferral + `.001` / mesh-sharing follow-ups this closes).

## Context

W1-1 ([`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py),
~2628 lines) and W1-2 ([`wflevels/smb_w1_2/blender_create_smb_w1_2.py`](../../wflevels/smb_w1_2/blender_create_smb_w1_2.py),
~2470 lines) each carry a **forked copy** of the same machinery: the box/texture/ground helpers,
every entity builder (goomba, koopa, coin template + dispenser, power-up template/block, brick +
debris, popup, fireball, pipe, piranha, spark + firework generators, castle + flags), the ~700-line
**Player** script, the **Director** script, and the **celebration** sequence. They have already
started to diverge (the celebration was re-derived for W1-2 by hand in B3; the koopa is inline-OO in
W1-1 but a `_build_koopa` in W1-2). Every new level forks it again. This is the deferred **B0** from
the fireworks plan.

Two axes of mesh duplication remain ([[feedback_share_mesh_datablocks]]):

1. **Per-type within a level** — the exporter already dedups objects that *share* a Blender
   datablock (landed: one `.iff` per `obj.data.name`), but the koopa/piranha/brick/qblock/etc.
   builders each build a **fresh** datablock per call, so they're never shared — which is why the
   enemies export as `koopa_green_0.001.iff`, `piranha_0.001.iff`, … and why W1-2 still has 90 unique
   meshes. Making identical actors **build once, instance many** dedups them and drops the `.001`
   names ([[feedback_check_git_diff_before_bumping_pools]] — this is the no-limit-change win).
2. **Game-wide** — each level dir re-exports its *own* copy of every mesh; there is no shared
   source `coin.iff`. The user's goal: *"one coin / koopa / brick … for the whole game, not per
   world/level."* (Part 3, the deepest layer.)

**Corrected constraint (2026-06-02, was wrong in the first draft):** WF **does** support per-actor
non-uniform render scale — [`RenderActor3D::Render`](../../wfsource/source/renderassets/rendacto.cc)
(`rendacto.cc:481-483`) multiplies each rotation-matrix row by `_scale.X/Y/Z`; an actor caches it
from the OAS `x_scale/y_scale/z_scale` fields ([`levelcon.h:87`](../../wfsource/source/oas/levelcon.h))
at load ([`actor.cc:715-720`](../../wfsource/source/game/actor.cc)) and from the runtime mailboxes
`X/Y/Z_SCALE` (3040–3042). The qbert stretch-and-squash (2026-05-10) drove it live via those
mailboxes — so the **engine** side is real and proven. The gap is the **authoring pipeline**: the
Blender exporter writes only Position + Orientation per object
([`export_level.py:1010-1011`](../../wftools/wf_blender/export_level.py)), and `levcomp-rs` then
**hardcodes** object scale to identity ([`lvl_writer.rs:340`](../../wftools/levcomp-rs/src/lvl_writer.rs)
→ `(ONE, ONE, ONE)`), so a Blender object's `scale` never reaches the binary — which is exactly why
`add_box` *bakes* the size into the mesh verts as the current workaround. **Implication:** size-variant
boxes (staircase/pyramid/pipe/ground) *can* share one unit-cube datablock with per-object scale —
once we **wire scale through the export pipeline** (the root-cause fix below). Runtime `SCALE`
mailboxes are the no-toolchain-change alternative, but need a script-capable class (statplats can't
tick a script). Same-size actors still share a datablock directly with no scale at all.

## Goal

1. **One source of truth** for the SMB builders + scripts (`wflevels/smb_common.py`), imported by
   both level scripts, so they cannot drift.
2. **One mesh datablock per actor type** within a level (build once, instance many) — fewer unique
   meshes, `.001` names gone.
3. (Stretch) **One source `.iff` per type for the whole game** — a shared mesh dir, no per-level
   source copies.

All **behaviour-preserving**: W1-1 is the golden, verified level — it must still pass
`verify_smb_scroll` + `verify_smb_scoring` and re-capture an identical celebration.

## Part 1 — `wflevels/smb_common.py` extraction (behaviour-preserving)

Extract the shared machinery into `wflevels/smb_common.py`:

- **Helpers:** `make_mat`, `add_box`, `add_statplat`, `_add_textured_box`, the `?`-block/brick TGA
  generators, the ground builder, `attach_schema`.
- **Entity builders:** `build_goomba`, `build_koopa(red=…)`, `make_coin_template` + dispenser,
  `make_powerup_template`/`make_powerup_block`, `add_brick` + debris template, `make_popup_template`,
  `make_fireball_template`/generator, `add_pipe`, `build_piranha`, `make_spark_template` +
  `add_firework_generators`, `build_castle` (+ pole/castle-flag/door), `build_flagpole`.
- **Parameterised script generators** — return the Forth string from a per-level `cfg`:
  - `player_script(cfg)` — cfg supplies `FLAGPOLE_X`, spawn, coin-room coin list, fireball/state
    mailboxes; the celebration walk uses `cfg.FLAGPOLE_X`.
  - `director_script(cfg)` — cfg supplies `FLAGPOLE_X`, camera clamps, `TIMER_UNITS`/`SECONDS`.
  - `celebration(cfg)` — builds the castle + flags + fireworks + wires the flagpole trigger
    (`SMB_CELEBRATE`) and advance trigger (`LEVEL_TO_RUN = cfg.NEXT_LEVEL_INDEX`).
- **Shared constants:** the celebration mailbox block (1862–1871), `SMB_*` indices used by both.

**Sequencing (de-risk W1-1):**
1. Write `smb_common.py` by lifting W1-1's current functions verbatim (W1-1 is the reference).
2. Re-point W1-1 to `import smb_common` and call them; **re-export W1-1 and prove it is
   behaviour-identical** — `verify_smb_scroll` + `verify_smb_scoring` green, celebration re-capture
   matches `tests/screenshots/smb_celebration_*`, level boots with the same actor inventory. (Mesh
   *bytes* may shift slightly — Blender export isn't byte-stable, TODO — so compare behaviour, not
   bytes.)
3. Only then re-point W1-2 to `smb_common`, dropping its forked copies; re-verify W1-2
   (boot + celebration video).

## Part 2 — per-type datablock sharing (build once, instance many)

In the `smb_common` builders, build each **same-size** type's geometry **once**, cache the datablock,
and instance with `bpy.data.objects.new(name, shared_data)` (the [[feedback_share_mesh_datablocks]]
pattern already used for goombas). The exporter then writes **one `.iff`** per type:

| Type | Today | After |
|---|---|---|
| Goomba | shared ✓ | shared ✓ (1) |
| Green / Red Koopa | `koopa_green_0.001`…×4 | 1 green + 1 red (2) |
| Piranha | `piranha_0.001`…×4 | 1 |
| Brick / `?`-block | per-instance ×N | 1 each |
| Coin (template + coin-room) | per-instance | 1 |
| Mushroom/Star/Flower/1-Up/spark templates | per-instance | 1 each |

**Size-variant structures** (staircase steps, pyramid steps, pipes of differing height, ground
spans) — now that we know per-actor scale is real, the clean fix is **scale, not decomposition**:

- **P2-pre — wire scale through the export pipeline (root cause).** (1) `export_level.py`: emit each
  object's `scale` (don't bake it — keep the datablock a unit cube), as a new `.lev` scale field
  (alongside the `VEC3`/`EULR` chunks). (2) `levcomp-rs`: read that field and pass it to
  `write_obj_header` instead of the hardcoded `(ONE, ONE, ONE)` at `lvl_writer.rs:340`. (3) verify
  the engine renders the scaled mesh (it already does — `rendacto.cc:481`). Round-trip-test against
  an existing level first (decompile→recompile stays byte-stable for identity-scale objects).
  Then a **unit-cube datablock + per-object scale** gives one shared `.iff` per material with correct
  in-world sizes, applied at load with **no script and no extra actors**.
- **After P2-pre:** the SMB box builders (`add_box`/`add_statplat`/`_add_brick`/`_add_pyramid`/
  `_add_staircase`/`_add_pipe`) stop `transform_apply`-ing scale — they instance one shared unit-cube
  datablock **per material** (hard-block, brick-tex, `?`-tex, pipe-green, ground-grid, …) and set
  `obj.scale`. Unique mesh count collapses toward **one box mesh per material** plus the handful of
  sculpted meshes (mario/goomba/koopa/piranha/coin/…).
- **Fallback if P2-pre is deferred:** runtime `X/Y/Z_SCALE` mailbox init on a script-capable class
  (qbert precedent) for the few worst offenders, or keep baking (status quo, per-instance). Don't
  decompose into unit cubes — it trades the mesh pool for the actor pool for no real benefit now that
  scale works.

The genuinely 1-of boxes (castle body, door) can stay per-instance — sharing buys nothing.
[[feedback_check_git_diff_before_bumping_pools]] still holds: measure, don't bump.

## Part 3 — game-wide single-source mesh library (stretch / may defer)

One canonical `.iff` per type in a shared dir (e.g. `wflevels/smb_assets/`), referenced by every SMB
level script instead of each level re-exporting its own copy. This is the literal "one coin for the
whole game." It's a build-pipeline change (the per-level export must reference shared meshes by path,
and `build_level_binary.sh` must resolve them) — scope it **after** Parts 1–2 land and only if the
per-level copies are actually causing friction. Note: PERM/rooms are per-level
([[project_*]] asset notes), so this is a *source-dedup*, not a runtime change — each level still
loads its own copy at runtime.

## Critical files

| File | Change |
|---|---|
| `wflevels/smb_common.py` (new) | Part 1: shared builders + `player_script`/`director_script`/`celebration` generators; Part 2: build-once-instance-many per type |
| [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) | import `smb_common`; drop forked copies; keep W1-1 layout + cfg |
| [`wflevels/smb_w1_2/blender_create_smb_w1_2.py`](../../wflevels/smb_w1_2/blender_create_smb_w1_2.py) | import `smb_common`; drop forked copies; keep W1-2 layout + cfg |
| `wflevels/smb_w1_{1,2}/*.iff`, `*-standalone.iff`, `cd.iff` | re-exported artifacts (fewer + renamed meshes) |

## Phasing (commit per phase)

- **P1a** — write `smb_common.py` (lift W1-1 verbatim); W1-1 imports it; prove W1-1 behaviour-identical. Commit.
- **P1b** — W1-2 imports `smb_common` (drop its fork); re-verify W1-2. Commit.
- **P2a** — same-size types build-once-instance-many in `smb_common`; re-export both; confirm unique-mesh drop + `.001` gone + both still load/play. Commit. (No pipeline change needed for these.)
- **P2-pre** — wire per-object **scale** through the export pipeline (`export_level.py` emit scale →
  `.lev` scale field → `levcomp-rs` pass it instead of hardcoded `(ONE,ONE,ONE)`); round-trip-test
  byte-stability on an existing level. Commit (toolchain change — touches wftools, verify broadly).
- **P2b** — box builders instance one shared unit-cube datablock **per material** + `obj.scale`
  (depends on P2-pre); re-export both; re-measure unique-mesh count. Commit.
- **P3** — (stretch) shared source-mesh dir. Separate decision.

## Verification

- **W1-1 regressions green throughout:** `verify_smb_scroll`, `verify_smb_scoring`.
- **Celebration re-capture** matches (W1-1 `tests/screenshots/smb_celebration_*`; W1-2
  `tests/recordings/smb_w1_2_celebration.mp4`).
- **Both levels boot** (`-L …-standalone.iff`): no OOM, actor inventory unchanged (P1) / mesh count
  dropped (P2); `cd.iff` `task run` W1-1→W1-2→W1-1 loop still works.
- **Unique-mesh count** logged before/after each Part-2 step (the metric for the dedup).

## Risks / gotchas

- **W1-1 is golden + verified** — the whole de-risk is: extract verbatim, prove unchanged via
  regressions + celebration re-capture *before* touching W1-2 or sharing meshes.
- **Per-actor scale exists but the export pipeline drops it** — engine renders it
  (`rendacto.cc:481`) + runtime mailboxes 3040–3042 (qbert precedent), but `export_level.py` emits no
  scale and `levcomp-rs` hardcodes identity (`lvl_writer.rs:340`). P2-pre wires it (root cause); until
  then box sizes are baked into geometry. **Don't** decompose into unit cubes — scale is the right
  tool. (Corrected from the first draft, which wrongly claimed no scale support — thanks to the
  user's catch.)
- **Blender export determinism — FIXED 2026-06-02 (canonicalize vertex/face order in the writer).**
  Root cause was a pure vertex/face **re-ordering**: `_write_mesh_iff` emitted verts in `bm.faces`
  encounter order, which `bpy.ops.object.join()` produced non-deterministically (identical geometry,
  churned bytes). Fix: re-key verts by fixed-point `(x,y,z,u,v)` (merge identical, sort) + remap/sort
  faces in [`export_level.py::_write_mesh_iff`](../../wftools/wf_blender/export_level.py) before
  packing `VRTX`/`FACE`. Two fresh re-exports are now byte-identical (goomba 1164→0 diff; all 74 W1-1
  meshes 0 diff). So mesh bytes **are** now a valid behaviour check, and P2's repeated W1-2 re-exports
  are reproducible. Write-up: [investigation](../investigations/2026-06-02-blender-export-nondeterminism.md).
  (Also corrected: the W1-2 re-export boot crash was **not** caused by this churn — identical geometry
  — it's a separate flaky physics/camera gap; the camera should fall back to `mainCharacter` instead
  of asserting on a null/out-of-room track object at `movecam.cc:1067`.)
- **Concurrent shared checkout** — both level scripts + `cd.iff` are hot; commit per phase with
  explicit pathspecs ([[project_concurrent_sessions_shared_checkout]]).

## Follow-ups (not this pass)
- Real moving-platform **lifts** (`platform.oas`) → unblocks **W1-3** (athletic).
- **W1-4** castle mechanics (firebars, Bowser, axe/bridge).
- Fanfare **SFX** (audio — other machine).
- Room right-edge widen so the celebration spark-fan stops falling out of room 0.
