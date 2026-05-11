# Plan — Q*bert cube consolidation via runtime material swap

**Date:** 2026-05-10
**Status:** Done 2026-05-10 (commit [`f3d2fe6`](../../) feat(qbert): Phase 1 cube consolidation — 1344 actors → 28 + runtime colors)

## Implementation summary (added 2026-05-11)

Landed in two commits on 2026-05-10:
- [`746bfac`](../../) `feat(engine): runtime per-face material color override + write-actor-mailbox` — engine side
- [`f3d2fe6`](../../) `feat(qbert): Phase 1 cube consolidation — 1344 actors → 28 + runtime colors` — asset + director side, 448 files changed, −30188 LOC net

### Engine wiring (commit `746bfac`)

- **Mailboxes** in [mailbox.inc:97-99](../../wfsource/source/mailbox/mailbox.inc):
  - `EMAILBOX_FACE_COLOR_TOP` = 3037 (material[0], cube top)
  - `EMAILBOX_FACE_COLOR_LIT` = 3038 (material[1], lit side)
  - `EMAILBOX_FACE_COLOR_SHADOW` = 3039 (material[2], shadow side)
- **Write handlers** at [actor.cc:1460-1480](../../wfsource/source/game/actor.cc) decode packed 24-bit RGB (0xRRGGBB) from the mailbox value's `.WholePart()` and call `_renderActor->SetMaterialColor(idx, color)` where `idx = boxnum - EMAILBOX_FACE_COLOR_TOP` (0/1/2). Read handlers (around [:1189-1191](../../wfsource/source/game/actor.cc)) are write-only stubs returning 0.
- **Storage deviation from plan**: the plan called for a per-Actor 3 × uint32 override array + dirty bit checked by the renderer. The actual landing instead **mutates the material colors in place** on `RenderObject3D::_materialList` (changed from `const Material*` to `Material*`), then re-runs `ApplyMaterials()` so the pre-baked Primitive RGBs pick up the new value on the next frame. Simpler than the override array — no override storage, no dirty bit, no per-draw branch.

  **Cost analysis.** `ApplyMaterials()` ([rendobj3.cc:120-136](../../wfsource/source/gfx/rendobj3.cc)) walks `ORDER_TABLES × _faceCount` and calls `Material::InitPrimitive()` for each triangle. Each `InitPrimitive` writes the material's RGB into the platform-specific Primitive struct used by the renderer's draw path (e.g. the per-vertex color the GL backend feeds into the vertex stream). After this re-bake, the GL `Render()` path is unchanged — it reads from `_primList` exactly as before. So the override is "free" at draw time; the work is paid up-front, at the moment of the mailbox write.

  For a cube: 12 faces × `ORDER_TABLES` (1 on Linux, 2 on PSX-class double-buffered targets, 4 with quad-buffer-of-double-buffer). So one TOP-color write costs ~12 InitPrimitive calls on Linux (per-cube), times 28 cubes if the director broadcasts to all of them in one tick.

  **Why this is acceptable for our write pattern:**
  - Per-cube TOP color: flips when a single cube's state advances 0→1→2 — at most 2 writes per cube per round, scattered across the ~20s a player takes to clear a round. Negligible.
  - Level transition (every 4 rounds): broadcast LIT + SHADOW to all 28 cubes = 56 writes × 12 InitPrimitive each = 672 InitPrimitive calls in one tick. Even at ~1 µs/call this is sub-millisecond; one-time cost per ~80-second level. Invisible at 60 Hz.
  - First-tick init: 28 cubes × 3 colors = 84 writes × 12 = ~1k InitPrimitive calls. Also one-time, well under a frame.

  Contrast with the plan's override-array approach: that would have paid `ORDER_TABLES × _faceCount × 28 cubes × 60 Hz` worth of per-draw branches forever (the dirty-bit check is cheap but non-zero, and override fan-in on every triangle adds an indirection). For a write frequency this low, write-time re-bake wins decisively. If a future use case ever sweeps colors per-frame (e.g. animated palette cycle), revisit — at that point the override-array tradeoff inverts.
- **New zForth primitive** `write-actor-mailbox ( val idx actor_idx -- )` — lets a script on one actor write a mailbox on another. The director needs this to address each of the 28 cubes individually. (`746bfac` Forth-side support; without this, the consolidation isn't expressible from a single director script.)

### Asset side (commit `f3d2fe6`, [gen_cube.py](../../wflevels/qbert_practice/gen_cube.py))

- Dropped the `16 rounds × 3 states` outer loop. Emits **one** 1112-byte `cube.iff` with 3 placeholder white materials (`#FFFFFF`).
- Per-round color data moved out of gen_cube.py into Python module-level constants `ROUND_TOP_COLORS`, `LEVEL_SIDE_COLORS`, `ROUND_SIDE_OVERRIDES` (per-round side overrides exist for L2R4, L4R2 flat rounds, plus a few other arcade-quirk rounds where the arcade deviates from the level-default side palette).
- Removed 447 prebaked variant .iff files (`cube_NN_rN_sN.iff`, `cube_stateN_rN.iff`, etc.) — visible in the commit's deleted-file list.

### Level / director side (commit `f3d2fe6`, [blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py))

- **Cube creation loop**: 1344 actor creates → 28. All 28 reference the same `cube.iff` (single mesh datablock in Blender; iffcomp deduplicates the on-disk asset).
- **Mailbox layout**: `INDEXOF_VIS_BASE` (1344 slots) deleted; `NUM_MAILBOXES` drops 1800 → 500.
- **`CUBE_ACTOR_BASE`** is computed at Blender-export time from the count of actors emitted before the cube loop, then embedded as a constant into the director's Forth source. The director reaches each cube N with `write-actor-mailbox` to actor index `CUBE_ACTOR_BASE + N`.
- **Director Forth rewrites**:
  - First-tick init: populate the `ROUND_TOP_LUT` from the in-script LUT data, write initial TOP/LIT/SHADOW colors to all 28 cubes.
  - Per-tick: detect cube state changes (0→1→2 hop progression) and write the new TOP color for that cube.
  - Level transition (`ROUND_NUMBER // 4` change): broadcast new LIT/SHADOW side colors to all 28 cubes (28 × 2 = 56 mailbox writes per transition × 3 transitions per game).

### Cap-bump reverts (commit `f3d2fe6`, in-source comments)

| File | Constant | Pre-bump | Post-revert (current) |
|---|---|---|---|
| [level.cc:1296](../../wfsource/source/game/level.cc) | `MAX_ASMP_SIZE` | 16 sectors | 16 sectors (annotated: "was bumped to 64 on 2026-05-10 for the qbert 1344-actor pyramid, reverted 2026-05-10 after Phase 1 cube consolidation dropped ASS chunk count to 18") |
| [assets.hp:88](../../wfsource/source/asset/assets.hp) | `MAX_ASSETS_PER_ROOM` | 1024 | 1024 (annotated: "bumped to 4000 on 2026-05-10 for fan-out, reverted 2026-05-10") |
| [assets.hp:116](../../wfsource/source/asset/assets.hp) | `_assetStringMap[]` | 1024 | 1024 (same annotation) |

### Measured savings (from commit message)

HalLmalloc post-load (64 MB cbHalLmalloc, snowgoons-class OBJD=200K ROOM=500K):

| Build | Used | Free |
|---|---|---|
| Baseline (May-9 fan-out, 1344 cubes) | **29.24 MB** | 34.76 MB |
| Phase 1 (28 cubes, runtime swap) | **2.47 MB** | 61.53 MB |
| snowgoons (for comparison) | 1.56 MB | 62.44 MB |

**92% reduction.** Inner iff drops 1.93 MB → 45 KB; ASS chunks 1353 → 18.

### Follow-on work (also landed)

Subsequent commits on 2026-05-10 stacked cleanly on the 28-actor layout:
- `78c4eb6` hop-direction facing rotation with smooth lerp
- `6a13ad3` 180° hop-turn camera-visibility fix; off-edge cube flip suppression
- `16e0668` hop-arc motion (smoothstep XY + parabolic Z); LANDED on landing; restart re-colors all cubes
- `ce1e193` Phase 2 stretch-and-squash — per-actor non-uniform scale
- `26580bb` low-poly player mesh + restore Level/Room pool sizes
- `9c6695f` autopilot via joystick injection

The detailed plan below is preserved for historical reference.

---

## Context

The Q*bert level today materialises 1344 distinct cube actors (28 pyramid positions × 16 round palettes × 3 hop states), with the level director toggling visibility flags every round so exactly one of 48 prebaked-color variants per position is rendered. This was the only way to get per-round palette changes without a runtime material API.

It works, but it's expensive: post-load HalLmalloc sits at **29.24 MB** for qbert vs **1.67 MB** for snowgoons (measured 2026-05-10, [2026-05-10-qbert-engine-caps.md](../investigations/2026-05-10-qbert-engine-caps.md)). The recent cap-chase (`MAX_ASSETS_PER_ROOM`, `MAX_ASMP_SIZE`, Jolt body pool, asset string map, binstrm length) was all downstream of this fan-out.

This plan replaces the fan-out with **one cube actor per pyramid position (28 total)** plus a small engine change that lets the director write face colors at runtime via mailboxes. There is no overlap of anything between levels — the same 28 per-cube mailboxes are reused across all 16 rounds and all 4 levels; on level change the director just rewrites them.

## Quantified savings

Post-consolidation HalLmalloc usage estimate, stacked from the agent breakdowns:

| Cost | Now (1344 cubes) | After (28 cubes) | Saved |
|---|---|---|---|
| AssetSlot per-cube data (~15 KB/cube measured) | ~20 MB | ~0.4 MB | **~20 MB** |
| Per-actor RenderObject3D primitive table | ~7.9 MB | ~0.17 MB | **~7.7 MB** |
| Jolt static-body pool (1344→28 bodies) | ~6.6 MB | ~0.14 MB | **~6.5 MB** |
| Per-Actor object pool | ~360 KB | ~8 KB | ~0.35 MB |
| Asset string map | ~48 KB | ~1 KB | ~0.05 MB |
| TOC entries | ~42 KB | ~1 KB | ~0.04 MB |

Rough projected total: **29 MB → ~3 MB**, snowgoons-class. (Numbers above overlap somewhat — the 15 KB/cube AssetSlot measurement already captures part of the per-actor RenderObject3D and Jolt body cost — so the actual saved is bounded above by the 29 MB starting point. Verify by re-measuring after the change.)

After consolidation, the May-10 cap bumps become unnecessary — they can revert. That's a separate validation that the change actually fixed the underlying pressure rather than just relocating it.

## Approach

### 1. Engine change — runtime per-face material color

Materials are currently `const Material* _materialList` in [wfsource/source/gfx/rendobj3.hp:76](../../wfsource/source/gfx/rendobj3.hp); colors are baked into the renderer's primitives at load via `RenderObject3D::ApplyMaterials()` ([rendobj3.cc:118-134](../../wfsource/source/gfx/rendobj3.cc)). Make this mutable on a per-actor basis.

**New mailbox slots** in [wfsource/source/mailbox/mailbox.inc](../../wfsource/source/mailbox/mailbox.inc):
- `EMAILBOX_FACE_COLOR_TOP` — color for material index 0 (cube top)
- `EMAILBOX_FACE_COLOR_LIT` — color for material index 1 (lit side)
- `EMAILBOX_FACE_COLOR_SHADOW` — color for material index 2 (shadow side)

Three is the minimum that matches the cube's existing 3-material layout (set by [gen_cube.py:86-137](../../wflevels/qbert_practice/gen_cube.py)) and stays useful for any other STAT actor with up to 3 colored faces.

**Wire the mailboxes** in [wfsource/source/game/actor.cc](../../wfsource/source/game/actor.cc) WriteSystemMailbox switch (around the existing X_POS/XSPEED handlers near :1313-1428). Each handler writes into a per-actor color override array (3 × uint32 RGB, default = 0xFFFFFF means "use the loaded material color").

**Override storage**: add a small struct on Actor (or in PhysicalAttributes) — 3 × uint32 = 12 bytes, plus a "dirty" bit that the renderer checks at draw time. Cheap; lives on every actor regardless of whether they use it.

**Renderer applies override**: in the per-frame draw path that reads material colors (the OpenGL backend at [wfsource/source/gfx/gl/rendobj3.cc:49](../../wfsource/source/gfx/gl/rendobj3.cc) `RenderObject3D::Render()`), check the actor's override before falling back to the loaded `_materialList[i]._color`. The simplest path is to plumb a Vector3-or-RGB array through Render() rather than mutating the const Material — keeps the load-time cache intact.

**Estimated engine LOC**: ~50-100, concentrated in actor.cc + one renderer file. No data structure layout changes that affect on-disk format.

### 2. Asset change — one cube .iff, neutral colors

Rewrite [wflevels/qbert_practice/gen_cube.py](../../wflevels/qbert_practice/gen_cube.py):
- Drop the 16-round, 3-state outer loop. Emit a single `cube.iff` with the same 8-vertex geometry, 12 faces, and the same 3-material MATL chunk — but with **placeholder colors** (e.g., white). The runtime override replaces them.
- Remove `ROUND_COLORS` from gen_cube.py; move it to blender_create_qbert.py where the director Forth needs it as a lookup table.

Result: 48 × 1112 byte cube .iffs → 1 × 1112 byte cube.iff. Asset count drops 1344 → 1 mesh asset (plus other infra).

### 3. Level change — 28 cube actors, simpler director Forth

In [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py):

- **Cube creation loop** (currently :777-856): collapse from `for r in range(16): for state in range(3): create actor` to a single per-position loop that creates 28 actors, all referencing the same `cube.iff`. Each actor still gets its world position + the per-cube state mailbox (200+N).

- **Mailbox layout** (:47-81): drop the 1344-slot `INDEXOF_VIS_BASE` allocation entirely. `NUM_MAILBOXES` can drop from 1800 back toward ~500. The 28 cube state mailboxes (200..227) and the 28 cube actors' new TOP_COLOR / LIT_COLOR / SHADOW_COLOR per-actor system mailboxes are the new surface. The per-cube TOP color mailbox is the only one that flips during a round; LIT/SHADOW are written once per level transition.

- **Director Forth visibility fan-out** (:694-772): delete entirely. Replace with: `ROUND_PALETTE_TABLE` data block (16 × 3 = 48 RGB values for tops) + a per-cube color update — when cube N's state changes, look up the (round, state) → top RGB from the table and write to cube N's TOP color mailbox.

- **Level transition handler** (currently round-clear at :753-771 increments ROUND_NUMBER 0..15): on the round change that crosses a level boundary (round 4→5, 8→9, 12→13), look up the level's lit/shadow side colors and write them to all 28 cubes' LIT/SHADOW mailboxes via a Forth loop. (28 × 2 = 56 mailbox writes per level change × 3 transitions per game = 168 writes total. Trivial.)

- **gen_player.py / player.iff**: untouched.

### 4. Revert May-10 cap bumps

After consolidation lands and the level boots+plays, restore the pre-May-10 values:

| File | Constant | Pre-bump | Post-revert |
|---|---|---|---|
| `wfsource/source/game/level.cc:1296` | `MAX_ASMP_SIZE` | 16 sectors | 16 sectors (or 4 — original snowgoons value) |
| `wfsource/source/asset/assets.hp:88` | `MAX_ASSETS_PER_ROOM` | 1024 | 1024 (or 200 — pre-qbert original) |
| `wfsource/source/asset/assets.hp:116` | `_assetStringMap[]` | 1024 | 1024 |
| `wfsource/source/asset/assets.cc:233` | matching assert | `<= 1024` | `<= 1024` |
| `wfsource/source/streams/binstrm.cc:301` | `len <` | 512000 | 512000 |
| `wfsource/source/physics/jolt/jolt_backend.cc:669` | Jolt body pool | 1024 | 1024 |

If any of these still trip after consolidation, the underlying issue isn't really fixed — investigate before re-bumping.

### 5. (Out of this plan) physics-hop and walker work

The [physics-hops plan](2026-05-10-qbert-physics-hops.md) and the walker harness changes from earlier today sit on top of this. After consolidation lands, the physics-hops work proceeds against 28 cube actors instead of 1344 — the cube positions are the same, so the (row, col) → world XYZ math doesn't change, but the per-cube identity used for landing detection becomes much simpler (no need to figure out which of 48 visibility-shadows you landed on).

## Critical files

| File | Action |
|---|---|
| `wfsource/source/mailbox/mailbox.inc` | add 3 EMAILBOX_FACE_COLOR_* enum entries |
| `wfsource/source/game/actor.cc` (~:1313-1428 region) | add 3 mailbox handlers writing to per-actor color override |
| `wfsource/source/game/actor.hp` | add 3-RGB override + dirty bit on Actor (or PhysicalAttributes) |
| `wfsource/source/gfx/gl/rendobj3.cc` (`Render()` ~:49) | apply per-actor override before falling back to `_materialList[i]._color` |
| `wflevels/qbert_practice/gen_cube.py` | collapse 48-variant loop → emit one `cube.iff` with neutral colors |
| `wflevels/qbert_practice/blender_create_qbert.py` | 28-actor cube loop; delete fan-out Forth; add per-cube top-color update + level-transition side-color writes |
| `wfsource/source/game/level.cc:1296` etc. | revert May-10 cap bumps after verification |

## Verification

1. **Engine builds clean** with the 3 new mailboxes wired.
2. **gen_cube.py emits one file** (1112 bytes) instead of 48.
3. **Blender export → level binary** produces a qbert_practice.iff with ~50 ASS chunks (vs 1353 today).
4. **Engine boots** with the standalone wrapper using the **pre-bump** ROOM=8M / OBJD=4M budgets — no chunkID assert, no Jolt OOM, no string-map overflow.
5. **Re-measure HalLmalloc post-load** (with the same one-shot `std::cerr << HALLmalloc` we used in the cap investigation). Expect ~3 MB used (vs 29 MB today).
6. **L1R1 plays correctly**: cubes render with arcade colors; hopping changes a cube's top color (state 0 → 1 → 2 transitions); round clear advances and the new round's top-color palette appears across all 28 cubes simultaneously (since they all read the new ROUND_NUMBER on next state change).
7. **L1R4 → L2R1 transition**: lit and shadow side colors change to L2's palette; behaviour persists for the rest of L2.
8. **Walker pixel-diff regression** (pending the broader physics rebuild): re-run the existing walker harness against the consolidated cubes and confirm cube-top samples still match the MAME palette captures.
9. **Cap-bump revert**: after step 6 passes, revert all six caps from the May-10 commit; re-run step 5 — should still boot clean with even more HalLmalloc free.

## Out of scope

- Physics-based player hops (separate [plan](2026-05-10-qbert-physics-hops.md))
- Walker / pixel-diff harness changes (independent)
- Generalising face-color mailboxes to >3 materials per actor (we use exactly 3; any expansion lands when a future level needs it)
- Removing per-frame override-check overhead (the dirty bit fast-path means actors that never write color pay one branch per draw — fine)
