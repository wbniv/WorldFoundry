# Plan — Distinct enemy meshes (Slick/Sam, Ugg/Wrong-Way, Coily)

**Date:** 2026-05-11
**Status:** Not started

## Context

The TODO entry under **QBERT ARCADE FIDELITY / Visual polish** ([TODO.md](../../TODO.md)) calls out:

> Distinct enemy meshes — Slick/Sam currently use a hat-on-body flipper proxy; Ugg/Wrong-Way use a climber blob; Coily is stacked spheres. Replace with arcade-recognizable 3D characters.

Functionally the enemies are all in (see today's retro plans and the multi-enemy capture `qbert-all-enemies.mp4`), but visually only the player ([2026-05-10-qbert-player-mesh.md](2026-05-10-qbert-player-mesh.md)) has had a deliberate silhouette pass. The proxies read as generic shapes — Coily in particular is four stacked icospheres, which has the right *count* of segments but none of the snake personality.

This plan upgrades the three remaining enemy silhouettes to arcade-recognisable 3D forms, following the established procedural-Blender-primitives pattern used by the player mesh.

## Reference (arcade Q*bert)

Reference comes from **MAME screenshots and web reference images**, not from ROM sprite extraction. Pixel-tile extraction adds no value for 3D-mesh authoring — we just need the silhouette and the palette, both of which a screenshot delivers directly. Save reference images to `docs/plans/screenshots/qbert-arcade-ref-*.png` as we collect them.

| Enemy | Arcade silhouette (3D interpretation) |
|---|---|
| **Slick** | Green-hatted small humanoid: white/cream body, broad flat green hat, big eyes, stubby feet. Reads as a "cube-flipper" — small enough to ride a cube top. |
| **Sam** | Same body as Slick, blue hat (arcade uses blue, not red — verify against ROM; current Python uses red `0.85/0.10/0.10`). |
| **Ugg** | Purple humanoid climber: round purple body, two prominent eyes (top side when climbing the face), small feet. Arcade has him as a yellow-orange creature with a red face — verify. |
| **Wrong-Way** | Mirror of Ugg, opposite colour palette (yellow/orange body if Ugg is purple, or vice-versa). |
| **Coily egg** | Single purple-flashing egg shape — taller than wide, slight taper. Replace stacked-icospheres proxy with a single elongated sphere. |
| **Coily snake** | Stack of segments **with a head**: 3–4 body balls tapering from larger head (with eyes, antenna/forked tongue optional) down to smaller tail. Top ball ≠ body balls — that's the personality. Arcade Coily curls/uncurls; static stack is fine for v1. |

References:

- [Wikipedia — Q*bert](https://en.wikipedia.org/wiki/Q*bert) — enemy roster and visual descriptions.
- Existing arcade-palette extraction work: [2026-05-04-qbert-arcade-palette-all-rounds.md](../investigations/2026-05-04-qbert-arcade-palette-all-rounds.md).

## Critical files

| File | Change |
|------|--------|
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | Replace `_flipper_build_mesh()` (lines 1291–1331), the climber `_climber_build_mesh()` (~lines 1401–1481), and the Coily egg + snake builders (~lines 1673–1793). Mailboxes, scripts, schema wiring, rotation composition (Ugg/WW pitch+yaw) all stay; **only the geometry changes**. |
| `docs/plans/screenshots/` | Add MAME / web reference screenshots for each enemy (silhouette + palette) before/during implementation. |

**No changes** to: `enemy.oad`, `redball_script` Forth source, mailbox layouts, the `_build_*_actor` wiring (only the mesh-building helper signatures change). Slick/Sam keep `wf_Mesh Name = 'slick_mesh.iff'` / `'sam_mesh.iff'`, etc.

## Pattern to mirror

From `_build_qbert_player_mesh` ([2026-05-10-qbert-player-mesh.md](2026-05-10-qbert-player-mesh.md) §"Mesh construction"):

1. Single mesh object per enemy, primitives joined with `bpy.ops.object.join()`.
2. Multiple material slots; per-face `material_index` for colour partitioning. The existing flipper builder ([blender_create_qbert.py:1336–1358](../../wflevels/qbert_practice/blender_create_qbert.py)) already shows the multi-material idiom.
3. Materials use `Principled BSDF` `Base Color`; the exporter `_write_mesh_iff` ([wftools/wf_blender/export_level.py:422–537](../../wftools/wf_blender/export_level.py)) reads them.
4. Vert budget: cubes / redball / coily are all sub-100 verts; player aims for ~250. **Per-enemy budget: stay under ~150 verts** to leave headroom for the 8-enemy-on-screen worst case.
5. Reuse `_REDBALL_VERTS` / `_REDBALL_FACES` (~42 verts, 80 faces) as a stock icosphere primitive for "body ball" components — already imported above the flipper builder.

## Approach — three independent phases

Each phase is self-contained: one mesh builder swap, one rebuild, one capture for visual check. Phases land as separate commits.

### Phase A — Slick & Sam (cube-flippers)

**Status:** Done — Blender mesh + build pipeline green; in-engine verify pending capture.

![Slick (left, lighter green) and Sam (right, slightly darker green) — humanoid mesh with hat, eyes with pupils, and feet](screenshots/qbert-slick-sam-mesh-2026-05-11.png)
*Slick & Sam rest-pose mesh, Blender EEVEE render. White icosphere body, 12-sided cylinder hat, white-sphere eyes with black-sphere pupils, flat-oval feet.*

Goal: cube-flipper humanoid silhouette.

1. Replace the shared-mesh `_flipper_build_mesh()` + `_build_flipper_actor()` pair with a single per-actor `_build_flipper_actor(name, mesh_name, hat_rgb, location)` that uses `bpy.ops.mesh.primitive_*` + `bpy.ops.object.join()` (matches the player-mesh pattern at [`_build_qbert_player_mesh`](../../wflevels/qbert_practice/blender_create_qbert.py)).
2. Components:
   - Body: icosphere subdiv 1 (42 verts), scale 0.45, Z-squash 0.75. White.
   - Hat: 12-sided flat cylinder, radius 0.55, depth 0.10. Coloured per actor.
   - **Eyes:** two small white UV-spheres on +X face of body, segments=6.
   - **Pupils:** smaller black UV-spheres just in front of the eyes.
   - **Feet:** two flat ovals (scaled UV-spheres), straddling ±Y, dark grey.
3. Hat colour: arcade has Slick & Sam **both green-hatted** ([L2R1 attract reference](screenshots/qbert-arcade-L2R1-early.png)). Distinguish via subtle brightness — Slick brighter `(0.10, 0.85, 0.20)`, Sam slightly darker `(0.05, 0.55, 0.12)`. (Original Python had Sam red `(0.85, 0.10, 0.10)` — arcade-wrong; fixed here.)
4. Total verts: ~150 (body 42 + hat 26 + 2 eyes ~24 each + 2 pupils ~15 each + 2 feet ~30 each).

### Phase B — Ugg & Wrong-Way (side-of-pyramid climbers)

**Status:** Done — Blender mesh + build pipeline green; in-engine Escher-tip verify pending capture.

![Ugg (left, orange) and Wrong-Way (right, purple) — upright rest pose with body, smaller head, big eyes with pupils, flat feet](screenshots/qbert-ugg-wrongway-mesh-2026-05-11.png)
*Ugg & Wrong-Way rest-pose mesh, Blender EEVEE render. The engine applies a DELTA_PITCH ±0.25 rev + DELTA_YAW 0.5/0 rev at runtime to tip these onto the cube's side face — see [2026-05-11-qbert-ugg-wrongway.md](2026-05-11-qbert-ugg-wrongway.md).*

Goal: humanoid climber that reads as "creature standing on the side of a cube" after the Escher pitch+yaw rotation.

1. Replace `_climber_build_mesh()` + `_build_climber_actor()` with a single per-actor primitive-based builder, same pattern as Slick/Sam. The rotation is applied at the actor level **after** mesh build, so model the mesh in upright rest pose (+X forward, +Z up, like the player) — the engine tips it.
2. Components:
   - Body: icosphere subdiv 1, scale 0.40, Z-squash 0.85. Variant body colour.
   - Head: smaller icosphere on top, same body colour.
   - **Eyes:** two large white UV-spheres on +X face of the head.
   - **Pupils:** smaller black spheres in front of the eyes.
   - **Feet:** two flat ovals at the bottom, dark grey.
   - **Horns removed** — not arcade-faithful for either Ugg or Wrong-Way.
3. Per-variant body colour: Ugg `(1.00, 0.55, 0.10)` orange, Wrong-Way `(0.55, 0.10, 0.85)` purple (preserved from prior code; arcade-faithful confirmation deferred to a colour-grading pass).
4. Total vert budget: ~150 verts.

### Phase C — Coily (egg + snake)

**Status:** Done — Blender mesh + build pipeline green; in-engine verify pending capture.

![Coily egg (left, elongated icosphere) and Coily snake (right, 4 tapered segments with head + eyes + pupils)](screenshots/qbert-coily-mesh-2026-05-11.png)
*Coily egg + snake rest-pose mesh, Blender EEVEE render. Egg: subdiv-1 icosphere scaled (0.72, 0.72, 1.30). Snake: 4 icosphere segments stacked along Z with radii (0.22, 0.30, 0.38, 0.50) bottom→top, plus white eye-spheres and black pupils on the head.*

Goal: visibly snake-like Coily; egg distinct from a plain ball.

**Coily egg:**

1. Replace the unit icosphere with an elongated variant: `_EGG_VERTS = [(x*0.72, y*0.72, z*1.30) for (x,y,z) in _REDBALL_VERTS]`. Same face indices, so 42 verts / 80 faces. Material flashes purple/red as today (3.75 Hz oscillator at lines 1564–1568) — no script change.

**Coily snake:**

1. Replace `_coily_build_mesh()` (and the shared `_coily_mesh` datablock + assignment) with a per-actor `_build_coily_snake_actor()` builder that mirrors the Slick/Sam/Ugg/WW primitive pattern.
2. Stack 4 icosphere segments at the same `_COILY_SEG_SPACING` as before (preserves the actor-positioning math via `_COILY_HALF_HEIGHT`), but with per-segment radii in `_COILY_SEG_RADII = [0.22, 0.30, 0.38, 0.50]` bottom→top — tail is small, head is large. Each segment is Z-squashed to `_COILY_SEG_HEIGHT / radius` so heights stay consistent.
3. Add eyes on the head (top segment): two white UV-spheres at `(0.32, ±0.18, head_z)` + two black-sphere pupils at `(0.40, ±0.18, head_z)`.
4. Material: purple body, white+black eyes.
5. Total verts: ~150 (4 icospheres × 12 verts + 2 eye spheres + 2 pupils).

## Verification

Per phase, run the full qbert build pipeline and visually inspect:

```
# 1. Author in Blender — rerun the level script
blender -b wflevels/qbert_practice/qbert_practice.blend -P wflevels/qbert_practice/blender_create_qbert.py

# 2. Build .lev → .iff via wf_blender exporter (per feedback_qbert_blender_build_pipeline)
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

End-to-end smoke: full play of L1R1 with all enemies in flight — confirm no asset-pool overflow (memory rule: `feedback_check_git_diff_before_bumping_pools`) and no regression in the existing FALL_DEATH / Slick-cube-flip / green-ball-freeze interactions.

## Documentation artefacts (screenshots in-plan)

As each enemy mesh is developed, capture renderings/screenshots and **embed them in this plan doc** so the doc evolves from "what we'll build" into "what we built". Mirror the pattern from [2026-05-11-qbert-red-ball-enemy.md](2026-05-11-qbert-red-ball-enemy.md), which embeds a Blender-authored mesh screenshot inline.

Directory: `docs/plans/screenshots/` (already in use — see `qbert-redball-2026-05-11.png`).

Per phase, add to this plan doc:

- **Blender viewport render** of the rest-pose mesh (orthographic side + 3/4 perspective), captured via `bpy.ops.render.opengl()` or screenshot. Filename: `qbert-<enemy>-mesh-2026-05-1X.png`.
- **In-engine screenshot** of the enemy on the pyramid, captured via the existing `screenshot` debug-bridge op (see [debug-bridge phase A plan](2026-05-03-debug-bridge-phase-a.md) if it exists, otherwise the `mb[432] CAPTURE_TRIGGER` path mentioned in [2026-05-09-qbert-walker-wf-parity.md](2026-05-09-qbert-walker-wf-parity.md)). Filename: `qbert-<enemy>-ingame-2026-05-1X.png`.
- **Before/after comparison** strip: proxy mesh next to new mesh in the same camera framing. Filename: `qbert-<enemy>-before-after-2026-05-1X.png`.

Embed inline in the relevant phase section using Markdown image syntax with descriptive alt text and a caption line, e.g.:

```markdown
![Slick — humanoid flipper mesh with green hat, eyes, feet](screenshots/qbert-slick-mesh-2026-05-11.png)
*Slick rest-pose mesh in Blender, viewport side view + 3/4 perspective.*
```

Each phase commit (see below) should include both the source change *and* the screenshot artefacts, so the plan doc and the visual evidence land together.

## Commit strategy

One commit per phase per the `feedback_commit_after_each_phase` rule:

1. `feat(qbert): Slick & Sam — humanoid mesh with eyes & feet`
2. `feat(qbert): Ugg & Wrong-Way — humanoid climber mesh`
3. `feat(qbert): Coily — snake silhouette with distinct head`

Optional preamble commit if reference screenshots are gathered as a separate step:

0. `chore(qbert): arcade reference screenshots for enemy meshes`

## Out of scope

- Animation (Coily curling, Slick/Sam tipping, Ugg/WW gait). Static silhouettes only; arcade attract mode is 2D anyway.
- Sprite-accurate texture mapping. Flat-shaded Principled BSDF materials only — matches the project's existing aesthetic.
- Mesh LOD. Single mesh per enemy.
- Replacing the red ball mesh (it's already a proper icosphere) or the green ball (same mesh, tinted).
- Rewriting `redball_script` or any director logic.

## Open questions

- **Arcade colour ground truth for Slick/Sam/Ugg/WW:** the current Python may have the per-enemy colours wrong (Sam red vs. blue, Ugg orange vs. purple, etc.). Confirm via MAME or web screenshots *before* committing the new mesh colours; otherwise the visual upgrade will encode the wrong palette and need a second pass.
