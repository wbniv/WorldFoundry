# Plan — Q*bert cube template-spawn via Generator (Phase 2 follow-up)

**Date:** 2026-05-10
**Status:** Not started — sequenced AFTER [2026-05-10-qbert-cube-consolidation.md](2026-05-10-qbert-cube-consolidation.md)

## Context

Phase 1 (the cube-consolidation plan) collapses 1344 cube actors → 28, with all 28 baked into the .lev file via blender_create_qbert.py's per-position actor-creation loop. Each cube is an explicit, named Actor record in the level data carrying mesh ref + script slot + position.

WF already has the **OAD Template Object** mechanism ([oad.h:42](../../wfsource/source/oas/oad.h)) and the **Generator** actor ([generator.cc:107](../../wfsource/source/game/generator.cc)) that spawns instances of a template via `Level::ConstructTemplateObject` ([level.cc:1489](../../wfsource/source/game/level.cc)). Today these are used only for dynamic enemy spawning.

This Phase 2 plan converts qbert from "28 baked cube instances" to "1 cube template + 28 generators that spawn cubes at level init", reusing existing engine infrastructure with **zero engine changes** (or 10 LOC for an optional self-destruct optimisation in Phase 2.5).

## Quantified delta (vs. Phase 1)

This is a *small* additional reduction on top of Phase 1. Phase 1 captures the big wins (29 MB → ~3 MB HalLmalloc); Phase 2 trims a few more KB and validates the template/generator pattern on a static-spawn use case.

| Resource | Phase 1 (28 baked cubes) | Phase 2 (1 template + 28 generators + 28 spawned cubes) | Phase-2 saving |
|---|---|---|---|
| **HalLmalloc post-load** | ~3 MB | ~3 MB **+ ~3-4 KB** (idle generators) | **~-4 KB** (slightly worse without 2.5) |
| **HalLmalloc post-load (with 2.5)** | ~3 MB | ~3 MB | **~0** (generators self-destroy) |
| **LVL chunk: cube actor records** | 28 × ~250-500 byte cube records ≈ 7-14 KB | 1 × ~500 byte cube template + 28 × ~100 byte generator records ≈ 3.3 KB | **~4-11 KB smaller** |
| **Asset string map entries** | 28 (one per cube actor name) | 1 cube template + 28 generator names = 29 | **~0** (generators have names too) |
| **TOC entries** | 28 cube records | 1 template + 28 generators = 29 | **~0** |
| **Mailboxes** | 28 cube state + 28×3 face color = 112 system mailboxes (per-actor) | Same — spawned instances get the same per-actor mailbox slots; +1 shared activation mailbox | **+1** (negligible) |
| **Jolt static bodies** | 28 | 28 | **0** (generators don't have physics bodies) |

Total runtime memory delta: **~4 KB worse without 2.5, ~0 with 2.5**.
Total level-data binary delta: **~4-11 KB smaller LVL chunk**.

The non-quantitative wins matter more:

- **Authoring**: cube positions move out of per-cube actor exports and into 28 lightweight generator placements (each is just a position + template ref + activation mailbox, no mesh/script per cube). Blender exports one cube template and 28 generator markers.
- **Pattern reuse**: validates Generator on a static-init use case. Currently Generator is only fired by dynamic enemy spawning; using it for level-init geometry proves the pattern works for procedural construction.
- **Procedural pyramids**: a 6-row, 8-row, or off-shape pyramid takes a Blender re-export with a different generator-placement loop, but **no engine or asset changes**. The cube template is independent of pyramid shape.
- **Zero engine changes** for the core plan; an optional 10-LOC change for Phase 2.5.

## Approach

### 1. Mark cube as Template Object

In Blender (or by direct .lev edit), set the cube object's `TemplateObject` flag to 1 ([statplat.pp:103](../../wfsource/source/oas/statplat.pp) `"Template Object"` field). The cube class declaration stays in the .lev as a template; the level loader at [level.cc:519](../../wfsource/source/game/level.cc) routes it to the template pool — it does NOT spawn as a live actor at load time.

### 2. Place 28 generators

In blender_create_qbert.py, replace the 28-cube creation loop (currently [:777-856](../../wflevels/qbert_practice/blender_create_qbert.py)) with a 28-generator creation loop:

- For each `(row, col)` in the pyramid:
  - Create a Generator actor at world position `cube_world_position(row, col)` ([:97-102](../../wflevels/qbert_practice/blender_create_qbert.py))
  - Set `ObjectToThrow` = cube template index
  - Set `ActivationMailBox` = a shared mailbox slot (e.g., `INDEXOF_CUBE_SPAWN_TRIGGER = 460`)
  - Set `GenerationRate` = max (so we don't worry about re-fire timing)
  - Set `ObjectVelocity` = (0, 0, 0)
  - Set `RandomRange*` = 0 (no displacement)

The generator inherits the cube's spawn position from its own placement — no per-generator OAS field needed for "cube target position".

### 3. Director triggers spawn at first tick

Add a one-shot block to the director's wf_Script (the [LEVEL_INITIALIZED](../../wflevels/qbert_practice/blender_create_qbert.py) flag at mb 421 already gates first-tick init):

```forth
\ first tick: trigger all 28 generators to spawn their cubes
421 read-mailbox 0 = if
  1 460 write-mailbox    \ CUBE_SPAWN_TRIGGER on
  1 421 write-mailbox    \ mark level initialised
exit then

\ second tick onwards: clear the trigger so generators idle
460 read-mailbox 1 = if
  0 460 write-mailbox
then
```

By the second tick, all 28 generators have spawned exactly one cube each. The activation mailbox stays at 0 forever after; generators sit idle.

### 4. Remove baked cube actor declarations

The 28-cube creation loop in blender_create_qbert.py deletes entirely. Only the cube template and the 28 generators are exported by Blender. The director script grows by one tiny block.

### 5. (Optional) Phase 2.5 — Generator self-destruct

To recover the ~4 KB of idle-generator overhead, add a `"Single Shot"` boolean to Generator's OAS. When set, the generator removes itself from the level after spawning its first instance:

- [wfsource/source/oas/generator.pp](../../wfsource/source/oas/generator.pp): add `int32 "Single Shot"` field (default 0)
- [wfsource/source/game/generator.cc:107-118](../../wfsource/source/game/generator.cc): after `theLevel->AddObject(createdObject, pos)`, check `getOad()->SingleShot` — if set, mark this generator for removal (use existing actor-removal pattern; see how enemies kill themselves).

Total Phase 2.5 engine LOC: ~10. Saves ~4 KB OBJD pool.

This is genuinely optional — 4 KB is noise next to Phase 1's 25-MB savings. List it for completeness.

## Critical files

| File | Action |
|---|---|
| (no change) `wfsource/source/oas/`, `wfsource/source/game/` | zero engine changes for core Phase 2 |
| `wflevels/qbert_practice/blender_create_qbert.py` | mark cube as Template Object; replace 28-cube creation loop with 28-generator creation loop; add 4-line Forth init block to director script for the activation-mailbox trigger |
| (Phase 2.5 only) `wfsource/source/oas/generator.pp` + `wfsource/source/oas/generator.ht` | add `"Single Shot"` boolean field |
| (Phase 2.5 only) `wfsource/source/game/generator.cc` (~:107-118) | self-destruct after first spawn when Single Shot is set |

## Verification

1. **Phase 1 has landed and is verified.** Don't start this work until consolidation is in.
2. **Cube class loads as template** — debug log: `_numTemplateObjects` includes the cube; cube does NOT appear in the live actor list at level-load time (count stays at the non-cube level objects).
3. **Generators load as 28 actors** — debug log shows 28 generators in the live actor list at load.
4. **First-tick spawn fires** — debug log shows 28 calls to `Generato::update` triggering `ConstructTemplateObject`; live actor count grows by 28 within the first frame.
5. **Activation mailbox cycles** — `mb[460]` reads as 1 on tick 0, 0 from tick 1 onwards.
6. **Visual identity with Phase 1**: pyramid renders identically; Q*bert hops the same; round palettes flip at the same beat. The change is invisible to the player.
7. **Re-measure HalLmalloc post-first-tick** — expect within ~4 KB of the Phase 1 number (slight regression from idle generators); for Phase 2.5, expect within ~0 of Phase 1 (or slightly better, since 28 generators self-destroy).
8. **Re-measure LVL chunk size** in qbert_practice.iff — expect ~4-11 KB smaller than Phase 1.
9. **Procedural test**: temporarily change the generator-placement loop to spawn a 5-row pyramid (15 generators) instead of 7-row (28). Verify it works without engine or asset rebuild. Revert.

## Risks

- **Generator's GenerationRate timing**: even with `ActivationMailBox = 0` after tick 1, each generator's `_timeToGenerate` keeps advancing. If the activation mailbox accidentally goes to non-zero later, every generator fires immediately. Mitigation: Phase 2.5 self-destruct, OR director-side audit that `mb[460]` stays 0.
- **`AddObject` after init may have constraints**: Generator's spawn path calls `theLevel->AddObject(createdObject, pos)` ([generator.cc:118](../../wfsource/source/game/generator.cc)). This is the dynamic-add path used by enemies during gameplay; should work at first-tick init too, but verify no level-load assumption is violated (room actor list freshness, asset bindings, etc.).
- **Spawned-cube mailbox slot assignment**: dynamically-spawned actors need their per-actor mailbox slots assigned the same way as load-time actors get them. Generator already handles this for enemies (which carry mailboxes), but verify the cube's TOP/LIT/SHADOW color mailboxes from Phase 1 work correctly when the cube is spawned via Generator vs. baked at load.
- **Per-instance script binding**: Phase 1 cubes are pure-data actors (no per-cube wf_Script). If we kept a script, each spawned instance would need its own zForth context — Phase 1 already removes per-cube scripts so this is moot, but worth noting.

## Out of scope

- Procedural-level authoring tools (the generator-spawn pattern enables this; building a real level editor is separate)
- Generalising Generator beyond `ConstructTemplateObject` semantics
- Single-generator multi-spawn (one generator with a position list spawning all 28 cubes) — requires more engine work; the 28-generator approach captures the same wins with no engine code
- Template-based spawning for non-cube actors (e.g., the player) — one instance, no payoff

## TODO (potential, not committed)

### Shared / reference-counted RenderObject3D

Today (post Phase 1) each of the 28 cube actors constructs its own `RenderObject3D` from the same `cube.iff` bytes ([rendobj3.cc:140](../../wfsource/source/gfx/rendobj3.cc) on-disk constructor). That gives 28 independent Material arrays — necessary because Phase 1 stores the runtime per-face color override on each Material's `_color`. Side effect: vertex / face / primitive data is duplicated 28× in RAM even though every cube has identical geometry.

Estimated additional saving if RenderObject3D were ref-counted (or pooled by source-asset hash) and the per-actor color override moved out of Material onto the Actor itself:

- 27 redundant `RenderObject3D` instances eliminated
- 27 × `Primitive[ORDER_TABLES × faceCount]` primitive tables eliminated (cube: 12 faces × 1-4 OT = 12-48 entries each)
- 27 × duplicated vertex/face arrays eliminated
- Estimated saving: **~150-300 KB** post Phase 1 (small, since Phase 1 already collapsed 1344 → 28); the same change against 1344 actors pre-Phase-1 would have saved ~7-8 MB

Engine change scope: ~150 LOC. Touch points:

1. `RenderObject3D` gains a refcount; copy constructor uses shared-pointer semantics for `_vertexList` / `_faceList` / `_primList` / `_materialList`.
2. Per-face color override moves from `Material._color` mutation onto `Actor` (3 × Color + dirty bit, ~16 B / actor).
3. Each per-material renderer in `wfsource/source/gfx/glpipeline/rend*.cc` checks the actor's override before reading the baked Primitive color. Branch is hot-path — needs care so non-overriding actors stay free.
4. Phase 1's `RenderObject3D::SetMaterialColor` becomes `Actor::SetFaceColorOverride` and stops touching the now-shared Material array.

Why it's TODO not in-scope:
- Phase 1 buys 24 MB; this would buy <0.5 MB more.
- The hot-path cost (one extra branch per face per draw) needs benchmarking on real hardware before committing.
- The Material refactor touches every renderer subclass (rendfcl, rendgcl, rendftl, rendgtl, rendfcp, rendgcp, rendftp, rendgtp — 8 files); risk to unrelated levels.

Worth revisiting if a future level pushes total RAM near the cap or if profiling shows mesh-data duplication as a meaningful cost. For now, document the opportunity and move on.
