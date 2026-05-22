# Investigation — Blender-snowgoons renders untextured (vs textured oracle)

**Date:** 2026-05-22
**Status:** Open — root cause not yet pinned. This doc is an ultrathink-ready brief for a focused investigation session.

## Why this surfaced

The viewport gizmo work ([plan](../plans/2026-05-22-viewport-gizmo.md)) repointed the
`wf-edit` viewport from the byte-oracle snowgoons (`wflevels/snowgoons.iff`, textured) to the
**Blender-built** snowgoons (`wflevels/snowgoons-blender-standalone.iff`) so that edits + Save+Compile
stay consistent with the Doc (which reads `snowgoons-blender.lev`). That exposed a long-parked gap:
the Blender round-trip renders **flat gray / untextured** (Blender round-trip [plan](../plans/2026-04-16-blender-level-roundtrip.md)
step 6 🟡 "plays, untextured"). The data looks texture-identical to the oracle at every layer checked,
yet faces render flat — see the paradox below.

---

## The problem (paste into a fresh session)

> ⬇️ Everything below is self-contained; the leading `ultrathink` triggers deep reasoning.

```text
ultrathink

# Crack the Blender-snowgoons "untextured" render gap in WorldFoundry

Repo: /home/will/WorldFoundry.2026-new-level  (branch 2026-new-level)

## The problem
The collaborative editor `wf-edit` now loads the **Blender-built** snowgoons
(`wflevels/snowgoons-blender-standalone.iff`) in its viewport so that edits +
Save+Compile stay consistent. But that build renders **flat gray / untextured**,
while the byte-oracle build of the same level renders fully textured. I need the
ROOT CAUSE (with evidence) and a fix, without breaking anything else.

## A/B proof (already captured, same wf-edit binary + code path, 80 frames)
- `tests/screenshots/ab_oracle.png`  — oracle `wflevels/snowgoons.iff`: TEXTURED (red shakes house, green hedges)
- `tests/screenshots/ab_blender.png` — Blender `wflevels/snowgoons-blender.iff`: FLAT GRAY (bright/washed-out)

## What is ALREADY RULED OUT (verified — do NOT redo unless you distrust it):
1. **Mesh** `wflevels/snowgoons-blender/house.iff` is byte-identical to the oracle's house mesh (18488 B). It has `MODL/VRTX/MATL/FACE`; the `MATL` is `TEXTURE_MAPPED` (flags 0x2) with real texture names; `VRTX` has UVs.
2. **Texture atlas + RUV table** are byte-identical: `Room1.tga` (65 KB, the house textures), `Room1.ruv`, `Perm.tga`. `cmp -l wflevels/snowgoons.iff wflevels/snowgoons-blender.iff` = **1687 differing bytes, all in offsets ~4133–16922 (the LVL region); everything after 16922 (the PERM/RMn texture chunks) is identical.**
3. **Mesh asset-ID / room** is correct: the house is `$3001001` = IFF, room 1, slot 1 — room 1 is where `Room1.tga` lives. (See the `ASMP`/`RM1` block in `wflevels/snowgoons-blender/snowgoons-blender.iff.txt`.)
4. **At runtime the House materials load their textures fine** — running the Blender build prints `material: texture="G_Shakes.tga" ... flags_in=0x2 bitdepth=15` for every house texture, **no lookup failures / no asserts**. (Two materials have `texture="" bitdepth=16` — identify which actors those are.)

## The paradox to resolve
Mesh, atlas, RUV, and room assignment are all identical/correct, and materials
resolve their texture names at load — yet faces render flat. **The entire diff is
1687 bytes of LEVEL data.** Decompiling both inner iffs and diffing the `.lev`
(157 changed lines / 78 hunks) shows ONLY:
- actor `slopeA–D` (the supporting-plane equation in the common block): oracle `0.0`, Blender computes real values (e.g. `0.312`, `3.769`)
- a `Matte Type` flag: oracle `1` (Color), Blender `0` (None)
- camera / path float deltas (these also make the A/B camera angle differ — but the gray is uniform, not a viewing-angle artifact)

**None of those is a texture switch.** So either (a) one of these LVL deltas
disables texturing through a non-obvious path (e.g. lighting/shading washes the
texture out — the Blender render is suspiciously *bright*), or (b) the real
difference is a binary LVL field the decompiler collapses (it renders both meshes
as the string `"house.iff"`, hiding any binary divergence), or (c) it regressed in
a tool since April. Find which.

## Strong leads to chase (in rough priority)
1. **Render-path trace (most direct).** Instrument the GL draw path for ONE house
   face in BOTH builds and compare: does the face get a valid bound atlas
   PixelMap + non-degenerate UVs at draw time, or does it fall to a flat material
   colour? Key files: `wfsource/source/gfx/rendobj3.cc` (material load + `LookupTexture` ~:203-211),
   `gfx/material.cc`, `gfx/rendmatt.cc`, `gfx/glpipeline/backend_modern.cc` (the
   `Vert`/shader/`Pack()` path), `gfx/glpipeline/rend{g,f}t{p,l}.cc` (`CalcUV`),
   `gfx/pixelmap.cc`, `streams/assets.cc` (`AssetManager::LookupTexture` ~:287),
   `streams/asset.hp`.
2. **Lighting.** The Blender build looks full-bright/flat. Were the directional
   lights (`Omni01`/`Omni02`) exported correctly? A 2026-04-19 fix was literally
   "levcomp-rs over-eager STR preference removing both directional lights." Enumerate
   EVERY differing field per-object in the decompiled diff (don't stop at slope) and
   check light type/direction/colour + ambient. Flat full-bright can erase texture
   contrast.
3. **Regression bisect.** Was snowgoons-blender EVER textured? Two 2026-04-19
   wf-status entries conflict: "Snowgoons renders fully via textile-rs … textured
   roof restored" vs "Blender round-trip plays continuously, **untextured**." Decide
   which referred to the Blender round-trip. If it was ever textured, `git log`
   `wftools/textile-rs/` and `wftools/levcomp-rs/` since 2026-04-20 (suspects:
   `1e8b403a`, `11cbca78`, `72a4af9c`, `a45194c7`) and bisect the regression.
4. **`Matte Type` Color→None** and the `slopeA–D` deltas — confirm whether either
   actually reaches the renderer, or rule them out explicitly.

## Reproduce / verify (commands)
# build editor
cmake --build build-editor --target wf_edit -j        # binary: build-editor/wf-edit

# rebuild the Blender level (regenerates inner + standalone)
bash wftools/wf_blender/build_level_binary.sh snowgoons-blender

# A/B render (headless). NOTE: --frames/--screenshot take a SPACE not '='.
# Run via a background mechanism + write the PPM to a REPO path (the sandbox
# kills GPU readback for foreground/non-repo paths). Convert PPM->PNG with PIL.
DISPLAY=:0 ./build-editor/wf-edit --level=<iff> --frames 80 --screenshot tests/screenshots/X.ppm
#   oracle  : --level=wflevels/snowgoons-blender/snowgoons-standalone.iff
#   blender : --level=wflevels/snowgoons-blender-standalone.iff   (editor default)

# runtime material/texture log (no editor)
cd wfsource/source/game && LD_LIBRARY_PATH=$PWD/../../../engine/libs DISPLAY=:0 \
  ../../../engine/wf_game --frame-step-smoke=10 -L../../../wflevels/snowgoons-blender-standalone.iff 2>&1 | grep -iE "material|texture|lookup"

# decompile either iff to a readable .lev for field-level diff
wftools/levcomp-rs/target/release/levcomp decompile <input.iff> \
  wfsource/source/oas/objects.lc --oad-dir wfsource/source/oas -o /tmp/out.lev

# byte diff
cmp -l wflevels/snowgoons.iff wflevels/snowgoons-blender.iff | wc -l   # 1687

## Read first (context already written down)
- docs/plans/2026-04-16-blender-level-roundtrip.md  (step 6 "plays, untextured")
- docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md  (the 1687-byte delta analysis; claims "Texture pipeline DONE" — scrutinize that claim)
- docs/plans/2026-04-19-textile-rs-validation.md
- docs/investigations/2026-04-19-snowgoons-build-pipeline.md
- docs/investigations/2026-05-16-textile-rs-rgba555-dedup-bug.md
- docs/level-design-troubleshooting.md  and  docs/level-building.md  (texture/material sections)
- docs/plans/2026-05-22-viewport-gizmo.md  (why the editor now loads the Blender build)

## Constraints
- Do NOT touch `wflevels/snowgoons-blender/snowgoons-standalone.iff` — it's the
  byte-oracle engine-stability smoke-test fixture (`WF_TEST_SNOW_LEVEL` in
  CMakeLists.txt, the multi-cycle rendobj3 regression). The editor loads the
  separate `wflevels/snowgoons-blender-standalone.iff`.
- Keep the engine-only/editor-only split clean; don't regress the game runtime.
- Tools are Rust (textile-rs, levcomp-rs, iffcomp-rs); the C++ iff2lvl in
  `wftools/iff2lvl/` is the oracle producer — use it to see how the oracle LVL
  differs from levcomp-rs's output for the same source.
- Follow the project conventions: write a plan doc to docs/plans/ before
  implementing, commit per phase, and PROVE the fix with an A/B screenshot
  (the Blender build must match the oracle's texturing).

## Deliverable
1. Pinned root cause with concrete evidence (a render-path trace, an exact
   differing field/byte, or a regressing commit) — not a hypothesis.
2. A fix plan (files + change), then implement it.
3. Verification: `tests/screenshots/ab_blender.png` rebuilt = textured, matching
   the oracle.
```

---

## Notes for whoever picks this up
- Assumes the working-tree state as of 2026-05-22: the editor default viewport level is
  `wflevels/snowgoons-blender-standalone.iff`, and the A/B evidence PNGs (`tests/screenshots/ab_oracle.png`,
  `tests/screenshots/ab_blender.png`) exist.
- The **regression-bisect lead (#3)** is the highest-leverage *if* snowgoons-blender was ever textured —
  it could pin the cause far faster than a full render-path trace. Resolve the conflicting 2026-04-19
  wf-status entries first.
- Screenshot-capture gotchas (learned the hard way): `--frames N` / `--screenshot PATH` take a **space**
  (`=` is silently ignored → runs forever); run the editor via a background mechanism and write the PPM
  to a **repo path** (the sandbox kills GPU readback otherwise); never `pkill -f wf-edit` (it self-kills
  the calling shell).
