---
plan: qbert-stretch-and-squash
date: 2026-05-10
status: Deferred 2026-05-11
scope: Engine wiring (~50-75 LOC across 5 files) + script consumer (~10 LOC of zForth in qbert player)
---

# Q*bert stretch-and-squash (Phase 2)

**Status:** Deferred 2026-05-11 — waits on per-actor scale wiring in the engine; revisit after enemy AI / cube logic lands.

## Context

[Phase 1 hop rotation](2026-05-10-qbert-hop-facing-rotation.md) and [Phase 1.5 hop-arc motion](2026-05-10-qbert-hop-arc-motion.md) shipped — Q*bert now visibly hops in a smoothstepped XY trajectory plus a parabolic Z arc, rotating to face each diagonal as he goes. He still hops as a *rigid* shape, though. Traditional animation calls for stretch-and-squash on every hop: vertical elongation as he leaps, horizontal compression on landing — sells the "alive, springy" feel.

This requires per-actor non-uniform scale, which WF doesn't currently support at runtime. The OAS schema already has `x_scale / y_scale / z_scale` ([levelcon.h:87](../../wfsource/source/oas/levelcon.h)) as load-time fields, but they're *stored but never read* — confirmed by `grep` returning only the debug `offsetof` print at [level.cc:391](../../wfsource/source/game/level.cc). So the engine wiring is greenfield.

This plan wires that gap (root-cause fix per [feedback_root_cause_not_symptom](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md)) — adds 3 new `LOCAL_SYSTEM` mailboxes (`X_SCALE / Y_SCALE / Z_SCALE`), routes them through actor → renderer, applies as a non-uniform scale during the matrix-construction step in `RenderActor3D::Render()`. Then the qbert player script writes per-frame scale during the hop arc.

## Approach

### Part A — Engine plumbing (~50 LOC)

**Existing pattern to mirror**: the [Phase 1 cube-color mailboxes](../investigations/2026-05-10-qbert-engine-caps.md) (commit `746bfac`) added `EMAILBOX_FACE_COLOR_TOP/LIT/SHADOW` (3037..3039) at [mailbox.inc:48-101](../../wfsource/source/mailbox/mailbox.inc), with handlers in [actor.cc](../../wfsource/source/game/actor.cc) (~line 1450) that call `_renderActor->SetMaterialColor(idx, color)`. The new scale mailboxes follow the same shape exactly.

Five files:

1. **[mailbox.inc](../../wfsource/source/mailbox/mailbox.inc)** (~4 lines): add `EMAILBOX_X_SCALE = 3040`, `EMAILBOX_Y_SCALE = 3041`, `EMAILBOX_Z_SCALE = 3042`; bump `LOCAL_SYSTEM_MAX` from 3040 → 3043.

2. **[rendacto.hp](../../wfsource/source/renderassets/rendacto.hp)** (~3 lines): add virtual `SetActorScale(const Vector3& scale)` on `RenderActor` (no-op default), override in `RenderActor3D`.

3. **[rendacto.cc](../../wfsource/source/renderassets/rendacto.cc)** (~15 lines):
   - New `Vector3 _scale = Vector3(1, 1, 1)` member on `RenderActor3D`.
   - `SetActorScale()` stores it.
   - In `Render()` (around [line 321](../../wfsource/source/renderassets/rendacto.cc)), after retrieving the matrix from `physicalObject.GetPhysicalAttributes().Matrix()`, multiply each row's first 3 columns by the corresponding scale component (manual 3×3 column scale — `Matrix34` has no `Scale()` method per [matrix34.hp:45-119](../../wfsource/source/math/matrix34.hp); the old `ConstructScale()` is commented out at line 83).

4. **[actor.cc](../../wfsource/source/game/actor.cc)** (~15 lines): in the `WriteMailbox` switch (alongside the existing `EMAILBOX_FACE_COLOR_*` cases), add three cases that read the float value, store into a per-actor `_scaleX/_scaleY/_scaleZ` member or directly call `_renderActor->SetActorScale(...)` with the latest stored XYZ. Read-handlers for symmetry (return the stored value).

5. **[actor.hp](../../wfsource/source/game/actor.hp)** (~2 lines): add `_scaleX/_scaleY/_scaleZ` cached members (defaults 1.0); these mirror what's already in OAS but are mutable per-frame.

**Wiring up the existing OAS fields** is a free win: in `Actor::BindAssets()` (around [actor.cc:390-507](../../wfsource/source/game/actor.cc)) initialize `_scaleX/_scaleY/_scaleZ` from the `_ObjectOnDisk.x_scale/y_scale/z_scale` payload (currently unread). Defaults to (1,1,1) when fields are zero (which they always are today since no level authors them). Calls `_renderActor->SetActorScale()` once at level load.

**Default safety**: actors that never write a scale mailbox keep `_scale = (1,1,1)`, render exactly as today. No regression risk on snowgoons / marble-madness / any existing level.

### Part B — Q*bert script consumer (~10 LOC of zForth)

In the existing per-tick lerp block in [blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) (right after the position writes, before the `then\n` of the lerp's outer if), compute scale from `t`:

- `z_scale = 1 + 0.30 * 4 * t * (1 - t)`  → peaks at 1.30 mid-hop (vertical stretch)
- `xy_scale = 1 - 0.15 * 4 * t * (1 - t)` → dips to 0.85 mid-hop (horizontal squash for volume preservation)

Both curves use the same `4*t*(1-t)` profile (already computed for the Z arc bonus — can reuse). Both write to mailboxes 3040 (X), 3041 (Y), 3042 (Z) per frame.

When cooldown is 0 (between hops), no script writes happen — scale stays at whatever the last lerp wrote, which for `t=1` is exactly `1.0` for both. Q*bert returns to natural shape at rest. ✓

Anticipation squash + landing impact squash are deferred to a Phase 3 follow-up.

## Critical files

| File | Change |
|---|---|
| [wfsource/source/mailbox/mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) | +3 mailbox slots, bump LOCAL_SYSTEM_MAX |
| [wfsource/source/game/actor.hp](../../wfsource/source/game/actor.hp) | +3 cached scale members |
| [wfsource/source/game/actor.cc](../../wfsource/source/game/actor.cc) | OAS load + write/read mailbox handlers |
| [wfsource/source/renderassets/rendacto.hp](../../wfsource/source/renderassets/rendacto.hp) | virtual SetActorScale |
| [wfsource/source/renderassets/rendacto.cc](../../wfsource/source/renderassets/rendacto.cc) | scale member + matrix multiply in Render() |
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | per-frame scale writes during hop lerp |

No new OAS fields. No new physics path. No new render passes.

## Existing facts to reuse

- `RenderActor3D::Render()` matrix construction at [rendacto.cc:321-330](../../wfsource/source/renderassets/rendacto.cc) is the single insertion point.
- Color-mailbox plumbing pattern from commit `746bfac` is the template for the scale mailboxes.
- OAS `x_scale/y_scale/z_scale` already in [levelcon.h:87](../../wfsource/source/oas/levelcon.h) (stored, unread). Wiring them up is the root-cause-style fix to a long-standing TODO.
- Already-computed `4*t*(1-t)` arc-bonus value in the Phase 1.5 lerp can be reused for both scale curves (save a few stack ops).

## Verification

1. **Engine builds clean** with `bash engine/build_game.sh`.
2. **Snowgoons regression check**: boot snowgoons standalone, verify player and floor render at normal scale (no scale mailbox writes anywhere → `_scale = (1,1,1)` everywhere).
3. **Q*bert smoke**: boot qbert standalone with no script changes (Part A only), verify all 28 cubes + player render at normal scale.
4. **Q*bert visual** (Part A + B): drive Q*bert through hops, verify visible vertical stretch mid-hop and horizontal narrowing. At rest, Q*bert should return to natural proportions. Try several hop directions to confirm scale isn't "stuck" anywhere.
5. **Death + respawn**: drive into a fall. Q*bert ramps Z down (FALL_PHASE) — should keep natural shape (no lerp running, scale stays at last value = `(1,1,1)`).
6. **Memory budget**: no new RAM. 3 new mailbox slots × ~4 bytes per slot per actor = ~12 bytes per actor. 28 cubes + ~17 other actors = ~540 bytes total — negligible.

## Follow-up plans

- **Wire up EMAILBOX_KEYFRAME for vertex-level morphs** — `EMAILBOX_KEYFRAME` ([mailbox.inc:64](../../wfsource/source/mailbox/mailbox.inc), local id 3015) currently has UNIMPLEMENTED stubs at [actor.cc:1184 + 1401](../../wfsource/source/game/actor.cc). The `AnimateRenderObject3D` vertex-blending machinery at `wfsource/source/anim/anim.cc:34-180` already supports per-frame vertex interpolation via `RenderObject3D::GetWrittableVertexList()`. Wiring this up enables arbitrary mesh deformation beyond what scale alone can express: twists, asymmetric squash, custom poses per hop direction, blink/wave gestures, etc. Heavier than scale (engine + mesh-bake + per-actor keyframe storage) but strictly more powerful — pursue once a use case emerges that scale can't cover. Q*bert specifically might use this in Phase 4+ for the "swearing-fit" idle animation when the player hesitates.

## Out of scope (Phase 3+)

- **Anticipation squash** at hop start (frame 0 has slight crouch before leap).
- **Landing impact squash** (final frame compresses Q*bert horizontally before recovery).
- **Recovery oscillation** — spring-back damped sine after landing (would need cooldown-extending state, currently cd=0 = "ready for next hop").
- **Per-actor uniform scale** as a separate single-axis convenience mailbox (probably not needed).
- **Authoring scale via OAS** in level files — Phase 2 wires up the load path but no levels currently set non-default scale; once the first level wants it, the Blender exporter writes the OAS values.
- **Tweening between scale states from the script side** — currently the script writes raw scale per frame; a future helper could ease between target poses.
