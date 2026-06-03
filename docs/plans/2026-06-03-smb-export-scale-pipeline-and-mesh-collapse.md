# Plan: per-actor scale through the export pipeline (P2-pre) + SMB mesh collapse (P2b)

**Date:** 2026-06-03
**Status:** DONE (2026-06-03)
**Parent:** [`2026-06-02-smb-common-extraction-and-mesh-sharing.md`](2026-06-02-smb-common-extraction-and-mesh-sharing.md) — deferred items P2-pre and P2b.

## Results

| Level | mesh `.iff` files before | after | Δ |
|---|--:|--:|--:|
| smb_w1_1 | 74 | **34** | −40 (−54%) |
| smb_w1_2 | 85 | **37** | −48 (−56%) |

Collapsed clusters (W1-1 examples): 14 bricks → 1 shared datablock, 16 staircase/pyramid
`mat_hard` boxes → 1, 7 `?`-blocks/power-up blocks → 1, 5 pipes → 1. **P2-pre** verified a no-op
for all existing content (snowgoons/qbert/W1-1/W1-2 rebuild byte-identical `.lvl`/`.iff`; W1-1
re-exports byte-identical `.lev`; +4 levcomp unit tests). **P2b** verified behaviour-equivalent:
`verify_smb_scroll`, `verify_smb_scoring`, `verify_smb_powerup_block`, `verify_smb_brick_break`
all green; W1-2 boots clean (object count 142, 0 issues, player rests on the scaled ground).

**Discovery fallout (fixed):** mesh-sharing breaks the test idiom of identifying an actor by its
mesh-`.iff` name (N actors now share one). Added `discover_by_pos()` to
[`debug_bridge_client.py`](../../tests/debug_bridge_client.py) — bridges authored name → runtime
idx via position (the runtime carries no actor name; the `.lev` has name+pos, the log has idx+pos).
Rewired `verify_smb_powerup_block` + `verify_smb_brick_break` (the latter was already broken at HEAD:
it required a `brick_hidden` mesh the layout renamed to `mushroom_block` long ago).

## Goal

Stop the export pipeline from throwing away per-actor scale, then use it to collapse the
SMB levels' size-variant box meshes from ~one-`.iff`-per-block down to ~one per material.
Today every box bakes its dimensions into a unique mesh datablock → a unique `.iff` in the
room pool. With scale carried through, identical-shape boxes share one unit mesh instanced at
different scales.

## Verified facts (checked, not assumed)

1. **The engine already honours per-actor scale — for rendering only.**
   - OAS fields `x_scale/y_scale/z_scale` exist ([`levelcon.h:87`](../../wfsource/source/oas/levelcon.h)),
     loaded into `_scaleX/Y/Z` at [`actor.cc:715-721`](../../wfsource/source/game/actor.cc) (zero → 1.0 default),
     mutable via `EMAILBOX_X/Y/Z_SCALE` (mailboxes 3040-3042).
   - Consumed only in [`rendacto.cc:481-483`](../../wfsource/source/renderassets/rendacto.cc) — it scales the
     render matrix rows. The comment at `actor.cc:709-713` is explicit: **"Per-actor non-uniform _render_
     scale … consumed in RenderActor3D::Render()."**
   - **Consequence:** scale does *not* scale the collision `BOX3`. The exporter must therefore still emit
     the **true (scaled) bounding box** even when the mesh is a shared unit box — collision comes from the
     `BOX3`/OAS bbox, geometry size from the scaled mesh render.

2. **The pipeline currently drops scale entirely.**
   - [`export_level.py`](../../wftools/wf_blender/export_level.py) emits only `VEC3 "Position"` + `EULR "Orientation"` (+ `BOX3`); no scale chunk.
   - [`levcomp-rs/src/lvl_writer.rs:340`](../../wftools/levcomp-rs/src/lvl_writer.rs) hardcodes the header scale to `(ONE, ONE, ONE)` (`ONE = 0x10000`).
   - [`lev_parser.rs`](../../wftools/levcomp-rs/src/lev_parser.rs) `LevObject` has no `scale` field.

3. **No existing object carries a live non-identity scale.** Every `obj.scale =` assignment in
   `smb_common.py` and both level scripts is immediately followed by `bpy.ops.object.transform_apply(scale=True)`,
   which bakes the scale into the mesh and resets `obj.scale` to identity. So **enabling scale export changes
   nothing for any object that exists today** — a re-export of all four levels must stay byte-identical.

4. **A new `"Scale"` VEC3 chunk is safe in the OAD payload.** The per-object OAD payload is built by
   `serialize_oad_data(schema, obj, …)` which maps **schema field names** to `.lev` chunks; `"Scale"` is not a
   schema field, so it is never serialized into the payload — exactly like `"Position"`/`"Orientation"`/`"Class
   Name"`/`"Global Bounding Box"`, which live in `obj.fields` but are header/special-cased, never leaked.

## Phase P2-pre — carry scale through the pipeline (no behaviour change)

Three edits; byte-identical re-exports are the proof.

### P2-pre.1 — `lev_parser.rs`
- Add `pub scale: Vec3` to `LevObject`.
- Default it to identity **(ONE,ONE,ONE) = (0x10000, 0x10000, 0x10000)** when no `VEC3 "Scale"` chunk is present
  (so absent-chunk ⇒ writer emits the same `(ONE,ONE,ONE)` as today).
- In `parse_obj`, add a `VEC3` sub-branch: `if named == "Scale" && data.len() >= 12 { scale = Vec3{…} }`.

### P2-pre.2 — `lvl_writer.rs`
- Replace the hardcoded `(ONE, ONE, ONE)` at line 340 with `(obj.scale.x, obj.scale.y, obj.scale.z)`.
- (Header layout doc at lines 35-36 already says `x_scale/y_scale/z_scale` — no doc change.)

### P2-pre.3 — `export_level.py`
- After computing `wf_pos`/`wf_rot`, read `sc = obj.matrix_world.to_scale()` mapped through `bl_to_wf`
  (identity per CLAUDE.md, so component-wise).
- **Emit `VEC3 "Scale"` only when scale deviates from identity** beyond an epsilon (e.g. `abs(s-1) > 1e-6`
  on any axis). This keeps every current object byte-identical (all are identity post-`transform_apply`).
- **Scaled bbox:** in the `obj.bound_box` branch (no `wf_original_bbox`), multiply each local corner by the
  object's local scale before `bl_to_wf`. Identity scale ⇒ unchanged ⇒ byte-identical; non-identity ⇒ the
  collision box matches the rendered size. (The `wf_original_bbox` custom-prop branch stays verbatim — those
  authors already encode final extents.)

### P2-pre verification
- `cargo test` in `wftools/levcomp-rs` stays green; add a unit test: a `LevObject` with a `VEC3 "Scale"` of
  2.0 → header bytes carry `0x20000` in the three scale words; absent chunk → `0x10000`.
- Re-export **all four levels** (snowgoons L2, qbert L3, smb W1-1 L0, smb W1-2 L1) and assert each `.lev`,
  `.lvl`, standalone `.iff`, and `cd.iff` is **byte-identical** to HEAD. (No object has non-identity scale yet,
  so anything else is a bug.)
- Quick engine smoke: hand-set `x_scale` on one actor's OAS (or via the `X_SCALE` mailbox) and confirm the
  render grows while collision is unchanged — i.e. the render-only behaviour is what we wired. Commit.

## Phase P2b — collapse SMB size-variant box meshes

Two sub-wins. Both edit only `smb_common.py` builders; level scripts are unchanged.

### P2b.a — share identical *textured* boxes (no scale needed)
All bricks/`?`-blocks are the same `T³` cube and differ only by which texture (`_brick_tex` vs `_qblock_tex`)
and by their per-object generator script/mailboxes (which live in the OAS, not the mesh). Today
`_add_textured_box` builds a fresh mesh **and a fresh material** every call → every brick is a unique
datablock → unique `.iff`. Change it to **cache one canonical unit textured box per texture path** (shared
material + shared mesh datablock) and instance via `bpy.data.objects.new(name, cached_data)`, positioned at the
box centre with `obj.scale = (w, d, h)` (here all `T`, so identity — but keep the scale path for symmetry).
The exporter already dedups by `obj.data.name`, so all bricks collapse to one `.iff`, all `?`-blocks to one.

### P2b.b — unit-box + scale for size-variant *statplat* boxes (needs P2-pre)
`add_box`/`add_statplat` today create a unit cube, set `obj.scale`, then **`transform_apply(scale=True)`**
(bakes) → unique mesh per size. Change `add_box` to:
- build/reuse **one canonical unit cube datablock per material** (cache keyed by material), instanced via
  `objects.new`;
- set `obj.scale = (sx, sy, sz)` and **do not** `transform_apply` — leave the scale live so P2-pre emits it.

This collapses the size-variant clusters that differ only in dimensions — W1-2 `s5_staircase_0..7` (8),
`s4_pyramid_0..3` (4), `s4_bricks`/`s4_final_bricks`, `pipe_s3_*`, `ground_*`, staircases/pyramids/pipes —
down to ~one unit box per material (`mat_hard`, `mat_pipe`, ground colour, …).

### P2b verification
- Re-export W1-1 + W1-2; expect a sharp drop in unique mesh `.iff` count (target: staircase 8→1, pyramid 4→1,
  bricks N→1, `?`-blocks N→1; report the before/after).
- **Behaviour-equivalence** (not byte-identity — meshes legitimately change):
  - Boot both levels headless; object count unchanged, zero load-time issues.
  - `verify_smb_scroll` + `verify_smb_scoring` green.
  - Capture W1-1 + W1-2 stills (staircase, bricks, `?`-blocks, pipes) and eyeball that sizes/positions match
    the pre-P2b screenshots — scale-render must reproduce the baked geometry exactly.
  - **Collision check:** walk/stand Mario on a staircase + under a `?`-block via the debug bridge and confirm
    the scaled `BOX3` still collides (since collision is bbox-driven, this is the load-bearing check).
- Watch the room pool: this *reduces* mesh count, so no pool pressure; if anything frees headroom.

## Critical files

| File | Change |
|---|---|
| [`wftools/levcomp-rs/src/lev_parser.rs`](../../wftools/levcomp-rs/src/lev_parser.rs) | P2-pre.1: `LevObject.scale` (+ identity default) + `VEC3 "Scale"` parse |
| [`wftools/levcomp-rs/src/lvl_writer.rs`](../../wftools/levcomp-rs/src/lvl_writer.rs) | P2-pre.2: write `obj.scale` into the header instead of `(ONE,ONE,ONE)` |
| [`wftools/wf_blender/export_level.py`](../../wftools/wf_blender/export_level.py) | P2-pre.3: conditional `VEC3 "Scale"` emit + scale-multiplied bbox |
| [`wflevels/smb_common.py`](../../wflevels/smb_common.py) | P2b: `add_box` + `_add_textured_box` → shared unit datablock + live `obj.scale` (drop `transform_apply`) |
| `wflevels/smb_w1_1*`, `wflevels/smb_w1_2*`, `wfsource/source/game/cd.iff` | rebuilt artifacts |

## Risks / gotchas

- **Scale is render-only** — the #1 trap. Collision uses the `BOX3`; the exporter MUST emit the scaled bbox
  (P2-pre.3) or scaled boxes render right but collide as unit cubes.
- **Byte-identity is the P2-pre contract.** If any level's re-export differs, an object had a live scale we
  didn't expect (or the conditional-emit epsilon is wrong) — stop and find it, don't paper over it.
- **Non-uniform scale + rotation.** `rendacto.cc:481` scales matrix rows = actor-local axes. SMB boxes are
  axis-aligned (rotation identity), so local == world and non-uniform scale is clean; flag this if any scaled
  box is ever rotated.
- **`transform_apply` removal** must not strip rotation/location — only `scale=False` for those (we only stop
  applying scale). Keep location/rotation handling exactly as is.
- Blender is the golden source — every shipped `.lev` stays a Blender export; no hand-editing `.iff`.

## Follow-ups (not this pass)

- **P3** — game-wide single mesh source dir (17 byte-identical meshes already shared by name across W1-1/W1-2;
  combined with P2b this collapses the per-level mesh count further).
- Apply the unit-box+scale idiom to the colour grounds/ceilings/pits in the level scripts (they still bake).
