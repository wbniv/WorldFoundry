# Plan — Distinct enemy meshes (Slick/Sam, Ugg/Wrong-Way, Coily)

**Target plan doc on commit:** `docs/plans/2026-05-11-qbert-distinct-enemy-meshes.md`
**Status:** DONE (commits `f56169de`, `47999900`, `36640381`) — Slick/Sam, Ugg/Wrong-Way, and Coily distinct meshes all shipped.

## Context

The TODO entry under **QBERT ARCADE FIDELITY / Visual polish** ([TODO.md:99](/home/will/WorldFoundry.2026-new-level/TODO.md)) calls out:

> Distinct enemy meshes — Slick/Sam currently use a hat-on-body flipper proxy; Ugg/Wrong-Way use a climber blob; Coily is stacked spheres. Replace with arcade-recognizable 3D characters.

Functionally the enemies are all in (see the seven retro plans landed today and the multi-enemy capture `qbert-all-enemies.mp4`), but visually only the player (`2026-05-10-qbert-player-mesh.md`) has had a deliberate silhouette pass. The proxies read as generic shapes — Coily in particular is four stacked icospheres, which has the right *count* of segments but none of the snake personality.

This plan upgrades the three remaining enemy silhouettes to arcade-recognisable 3D forms, following the established procedural-Blender-primitives pattern used by the player mesh.

## Reference (arcade Q*bert)

Sprite reference will come from MAME extraction first; web/visual reference is the fallback if extraction proves slow. **Per user direction: don't get stuck in extraction** — if the tooling balks, fall back to visual reference and move on.

| Enemy | Arcade silhouette (3D interpretation) |
|---|---|
| **Slick** | Green-hatted small humanoid: white/cream body, broad flat green hat, big eyes, stubby feet. Reads as a "cube-flipper" — small enough to ride a cube top. |
| **Sam** | Same body as Slick, blue hat (arcade uses blue, not red — verify against ROM; current Python uses red `0.85/0.10/0.10`). |
| **Ugg** | Purple humanoid climber: round purple body, two prominent eyes (top side when climbing the face), small feet. Arcade has him as a yellow-orange creature with a red face — verify. |
| **Wrong-Way** | Mirror of Ugg, opposite colour palette (yellow/orange body if Ugg is purple, or vice-versa). |
| **Coily egg** | Single purple-flashing egg shape — taller than wide, slight taper. Replace stacked-icospheres proxy with a single elongated sphere. |
| **Coily snake** | Stack of segments **with a head**: 3–4 body balls tapering from larger head (with eyes, antenna/forked tongue optional) down to smaller tail. Top ball ≠ body balls — that's the personality. Arcade Coily curls/uncurls; static stack is fine for v1. |

## Critical files

| File | Change |
|------|--------|
| [wflevels/qbert_practice/blender_create_qbert.py](/home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) | Replace `_flipper_build_mesh()` (lines 1291–1331), the climber `_climber_build_mesh()` (~lines 1401–1481), and the Coily egg + snake builders (~lines 1673–1793). Mailboxes, scripts, schema wiring, rotation composition (Ugg/WW pitch+yaw) all stay; **only the geometry changes**. |
| [scripts/research/mame/](/home/will/WorldFoundry.2026-new-level/scripts/research/mame/) | Optional new Lua: `qbert_sprite_capture.lua` to dump enemy sprite tiles + per-enemy palette to disk. Pattern mirrors existing `qbert_palette_capture.lua`. If extraction is hard, skip. |
| [docs/investigations/](/home/will/WorldFoundry.2026-new-level/docs/investigations/) | Optional `2026-05-1X-qbert-enemy-sprites.md` capturing the extracted sprite reference + arcade-accurate colours per enemy. |

**No changes** to: `enemy.oad`, `redball_script` Forth source, mailbox layouts, the `_build_*_actor` wiring (only the mesh-building helper signatures change). Slick/Sam keep `wf_Mesh Name = 'slick_mesh.iff'` / `'sam_mesh.iff'`, etc.

## Pattern to mirror

From `_build_qbert_player_mesh` (player-mesh plan §"Mesh construction"):

1. Single mesh object per enemy, primitives joined with `bpy.ops.object.join()`.
2. Multiple material slots; per-face `material_index` for colour partitioning. The existing flipper builder (lines 1336–1358) already shows the multi-material idiom.
3. Materials use `Principled BSDF` `Base Color`; the exporter `_write_mesh_iff` ([wftools/wf_blender/export_level.py:422–537](/home/will/WorldFoundry.2026-new-level/wftools/wf_blender/export_level.py)) reads them.
4. Vert budget: cubes/redball/coily are all sub-100 verts; player aims for ~250. **Per-enemy budget: stay under ~150 verts** to leave headroom for the 8-enemy-on-screen worst case.
5. Reuse `_REDBALL_VERTS` / `_REDBALL_FACES` (~42 verts, 80 faces) as a stock icosphere primitive for "body ball" components — already imported above flipper builder.

## Approach — three independent phases

Each phase is self-contained: one mesh builder swap, one rebuild, one capture for visual check. Phases land as separate commits.

### Phase A — Slick & Sam (cube-flippers)

Goal: cube-flipper humanoid silhouette, distinct hats per variant.

1. Rewrite `_flipper_build_mesh()` to return `(verts, faces, material_face_map)` where `material_face_map` is a dict `{mat_index: [face_indices]}` covering: body, hat, eyes, feet.
2. Components:
   - Body: smaller icosphere (~scale 0.45, slight Z-squash), white. *(retains current)*
   - Hat: 12-sided flat cylinder, raised slightly with a rim. *(retains current — its silhouette is already arcade-correct)*
   - **Eyes:** two small white spheres on top of body, +X side. Pupils via a 2nd material (black) on a small face subset — cheap version is just slightly smaller dark spheres in front of the whites.
   - **Feet:** two flattened spheres straddling ±Y, dark grey or matching hat colour.
3. Hat colour per actor stays the only per-variant delta: green for Slick, **blue** for Sam (correct arcade colour; current Python uses red — confirm via ROM or arcade screenshot before committing).
4. Total vert budget target: ~80–100 verts.

### Phase B — Ugg & Wrong-Way (side-of-pyramid climbers)

Goal: humanoid climber that reads as "creature standing on the side of a cube" after the Escher pitch+yaw rotation (DELTA_PITCH ±0.25 rev + DELTA_YAW 0.5/0 rev — see [2026-05-11-qbert-ugg-wrongway.md](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-11-qbert-ugg-wrongway.md)).

1. Replace `_climber_build_mesh()`. The rotation is applied at the actor level **after** mesh build, so model the mesh in upright rest pose (+X forward, +Z up, like the player) — the engine will tip it.
2. Components:
   - Body: squashed icosphere (current proxy is close — but **remove the horns**, they're not arcade-faithful for either Ugg or Wrong-Way).
   - Head: smaller sphere on top with two large round eyes (white + dark pupil materials).
   - Arms: optional — two small flattened spheres at ±Y body sides, low priority.
   - Feet: two flat ovals, current proxy is fine.
3. Per-variant material delta is purely body colour: Ugg purple, Wrong-Way yellow/orange. (Verify arcade colours; current Python has Ugg orange / WW purple — sprite extraction will confirm which is which.)
4. Total vert budget target: ~110 verts.

### Phase C — Coily (egg + snake)

Goal: visibly snake-like Coily; egg distinct from a plain ball.

**Coily egg:**
1. Replace the stacked-icosphere variant with a single elongated icosphere (Z scale ~1.3, XY scale ~0.7). Material flashes purple/red as today (3.75 Hz oscillator already in place at lines 1564–1568) — no script change.
2. ~42 verts.

**Coily snake:**
1. Replace 4-equal-stack with a tapered stack of **3 body balls + 1 head**:
   - Head: larger icosphere (radius ~0.50) on top, with two eye spheres on the +X face and an optional small antenna/tongue cone.
   - 3 body segments: radii 0.40, 0.32, 0.24, decreasing downward.
2. Total vert budget target: ~130 verts (head with eyes adds ~30 verts).
3. Material: purple body, white+black eyes. Optional bright red antenna/tongue accent.

## Verification

Per phase, run the full qbert build pipeline and visually inspect:

```
# 1. Author in Blender — rerun the level script
blender -b wflevels/qbert_practice/qbert_practice.blend -P wflevels/qbert_practice/blender_create_qbert.py

# 2. Build .lev → .iff via wf_blender exporter (per [feedback_qbert_blender_build_pipeline])
./build_level_binary.sh qbert_practice

# 3. Compile bundle
./iffcomp standalone qbert_practice

# 4. Run
cd wfsource/source/game && ./wf_game qbert_practice-standalone
```

For each phase:
- Spawn the relevant enemy via director timers (already happens at level start).
- Visually confirm: silhouette reads as the named enemy from a player-perspective camera angle.
- For Ugg/Wrong-Way: confirm the Escher pitch+yaw still looks right with the new mesh (head up the slope, feet on cube face).
- For Coily snake: confirm chase AI motion still reads as "snake" not "blob".
- Capture a short video to `qbert-<enemy>-mesh-2026-05-1X.mp4` for diffing against the prior proxy.
- After all three phases land, capture a fresh `qbert-all-enemies-v2.mp4` superseding the existing capture.

End-to-end smoke: full play of L1R1 with all enemies in flight — confirm no asset-pool overflow ([feedback_check_git_diff_before_bumping_pools](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_check_git_diff_before_bumping_pools.md)) and no regression in the existing FALL_DEATH / Slick-cube-flip / green-ball-freeze interactions.

## Commit strategy

One commit per phase per [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md):

1. `feat(qbert): Slick &amp; Sam — humanoid mesh with eyes &amp; feet`
2. `feat(qbert): Ugg &amp; Wrong-Way — humanoid climber mesh`
3. `feat(qbert): Coily — snake silhouette with distinct head`

Optional preamble commit if sprite extraction lands as a separate research step:

0. `chore(qbert): MAME sprite + palette capture for arcade enemies`

## Out of scope

- Animation (Coily curling, Slick/Sam tipping, Ugg/WW gait). Static silhouettes only; arcade attract mode is 2D anyway.
- Sprite-accurate texture mapping. Flat-shaded Principled BSDF materials only — matches the project's existing aesthetic.
- Mesh LOD. Single mesh per enemy.
- Replacing the red ball mesh (it's already a proper icosphere) or the green ball (same mesh, tinted).
- Rewriting `redball_script` or any director logic.

## Open questions

- **Sprite extraction effort:** if the existing MAME palette-capture pattern doesn't extend trivially to sprite tile extraction, fall back to visual reference. Don't sink more than ~30 min into making the Lua work before falling back.
- **Arcade colour ground truth for Slick/Sam/Ugg/WW:** the current Python may have the per-enemy colours wrong (Sam red vs. blue, Ugg orange vs. purple, etc.). Confirm via extraction or arcade reference *before* committing the new mesh colours; otherwise the visual upgrade will encode the wrong palette and need a second pass.
