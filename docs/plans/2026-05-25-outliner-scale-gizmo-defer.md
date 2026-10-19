# Scale: record the bug, defer the real fix, shelve the gizmo

## Context

"Gizmo scale" looked like a ~1 h quick win, but it isn't. Per-actor scale
(mailboxes `EMAILBOX_X/Y/Z_SCALE` 3040–3042) is **render-only**:
`actor.cc:1606-1622` caches `_scaleX/Y/Z` → `RenderActor3D::SetActorScale`, which
column-multiplies the world matrix *at draw time*. It does **not** scale the
collision bbox (`coarse` rect, `_ObjectOnDisk` bytes 36–60) or the Jolt physics
shape — so a scaled actor's collision/physics stays original-size. That's a bug
(benign for qbert's just-shipped visual-only scaling; an authoring trap
elsewhere). Persisting a render-scale into the `.lev` would be a footgun and
fights the Blender-golden-source model. The proper fix — physics-correct instance
scale via OAD fields (render + bbox + Jolt `ScaledShape`), authored as Blender
object scale — needs new OAS fields, so it waits until after the new level ships.

Decision (Will): note the collision/physics gap as a bug; log the OAD-field
solution under DEFERRED UNTIL LEVEL; shelve the scale gizmo. No feature code.

## Changes

### 1. `TODO.md` — PHYSICS section (after the Surface-Friction entry, line 92)
New `- [ ]` bug: render scale (3040–3042 → `_scaleX/Y/Z` → `SetActorScale`,
`actor.cc:1606-1622`) scales only the drawn mesh; **not** the collision bbox
(`_ObjectOnDisk` bytes 36–60) or the Jolt shape. Acceptable for qbert
(visual-only, no mesh-to-mesh collision) but a latent desync elsewhere. Surfaced
2026-05-25 evaluating a scale gizmo. Proper fix = the DEFERRED-UNTIL-LEVEL item.

### 2. `TODO.md` — DEFERRED UNTIL LEVEL section
New `- [ ]`: physics-correct instance scale via **OAD fields** (x/y/z scale that
scale render + collision bbox + Jolt `ScaledShape` together), authored as Blender
object scale, persisted through the `.lev` pipeline. Pipeline insertion points
already mapped (`decompile.rs:24`, `lev_parser.rs`/`lvl_writer.rs`,
`export_level.py`). Blocked on new OAS fields → after the new level ships
([[feedback_no_new_oas_fields_premerge]]). Jolt caveat: non-uniform scale is
restricted on rounded shapes (spheres/capsules uniform-only; box/convex/mesh OK).
Unblocks the deferred wf-edit scale gizmo + is the proper fix for the PHYSICS bug.

### 3. `docs/plans/2026-05-22-viewport-gizmo.md` — "Deferred — scale" section
Update: scale gizmo **shelved 2026-05-25**. The blocker is deeper than "no `.lev`
leaf" — render scale is visual-only (collision/physics don't follow; see TODO
PHYSICS), so persisting it is a footgun. Proper path = physics-correct instance
scale via OAD fields (TODO DEFERRED UNTIL LEVEL). Once that lands, the gizmo is a
small ImGuizmo `SCALE`-mode add mirroring the translate/rotate Commit path.

### 4. `docs/level-design-troubleshooting.md` — new gotcha
"## Per-actor scale is visual-only — collision and physics don't scale": scaling
an actor (mailbox 3040–3042 / Blender object scale once wired) stretches only the
rendered mesh; the collision bbox + Jolt shape stay original-size. Fine for purely
visual scaling; for gameplay-affecting size, edit the mesh in Blender (or wait for
physics-correct instance scale).

### 5. Commit
One commit, all four files. Message records the scale decision + the bug.

## Verification
- `grep -n "visual-only\|ScaledShape" TODO.md` shows both new entries in the right
  sections; gizmo plan's deferred-scale section reflects the shelving;
  troubleshooting gotcha renders (`task md -- docs/level-design-troubleshooting.md`).
- No engine/tool code changed — docs + TODO only.
