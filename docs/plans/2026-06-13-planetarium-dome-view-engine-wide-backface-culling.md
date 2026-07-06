# Plan: Planetarium dome view + engine-wide backface culling

## Context

Continuing the **filesystem-visualization family** in World Foundry (FSN node-link · Filelight
flat sunburst · KDirStat treemap already shipped). This turn adds the **4th view — a planetarium
dome** (sunburst wrapped onto a hemisphere; player stands at centre and looks up). While scoping
the dome's mesh facing, the user raised that the renderer's **lack of backface culling causes
display artifacts** — confirmed: nothing enables `GL_CULL_FACE`, so both sides of every polygon
draw (z-fighting on coincident faces, back-face bleed-through, doubled fill). The user chose to
**fix culling engine-wide**, via the **software normal-based** mechanism (winding-independent).

Two separable efforts result. They are independent, but because software culling keys off
**face normals** (already correct everywhere — proven by correct lighting), the dome's facing
becomes irrelevant to visibility. **Recommended order: land culling first** (engine-only, no asset
rebuilds, gives the dome a free regression check), **then build the dome against the culling-on
binary** so its framing screenshots reflect final behavior.

---

## Effort 1 — Engine-wide backface culling (software, normal-based)

**Goal:** cull every back-facing triangle engine-wide, **on by default**, with `WF_CULL=0` to
disable for instant A/B. Winding-independent — **zero mesh edits, no winding audit** — by reusing
the per-face normals the engine already computes (`CalculateNormal`, `face.hpi:27-48`) and that
one-sided lighting already proves directionally correct (outward on props, inward on interiors).

**Why software, not hardware `GL_CULL_FACE`:** winding is globally inconsistent
(`rendacto.cc:147` cube is CW-from-inside; Blender boxes CCW-from-outside; `rendmatt.cc:221` matte
ad-hoc) — a single `glFrontFace`+cull would erase a large, hard-to-enumerate set of surfaces and
require flipping every interior mesh (rooms, dome, skydome) inward. The software dot-product test
sidesteps all of it.

**The test (one chokepoint).** All triangles from all 8 `RenderPoly3D*` renderers *and* the matte
flow through `ModernRendererBackend::DrawTriangle` (`wfsource/source/gfx/glpipeline/backend_modern.cc:347-364`).
Do the cull there, in **eye space** (camera at origin, looking −Z) using the already-maintained
`_mv[16]`:
- `Ne = MV_upper3x3 * face.normal` (same transform used for light dirs at `backend_modern.cc:311-313`)
- `Pe = MV * faceCenter` where `faceCenter = (v0+v1+v2)/3`
- **cull when `dot(Ne, Pe) > 0`** (normal points away from the camera)

**DOUBLE_SIDED exception (already-dormant flag).** `material.hp:117` defines `DOUBLE_SIDED = 8`,
never used. Add inline `IsDoubleSided() const { return _materialFlags & DOUBLE_SIDED; }` to
`material.hp`. Extend `DrawTriangle`'s signature (`renderer_backend.hp:72-76` + the
`backend_modern.cc` override) with a `cullExempt` bool. The 8 `RenderPoly3D*` TUs (representative:
`rendftl.cc:75`) pass `currentRenderMaterial->IsDoubleSided()`; the matte's two `DrawTriangle`
calls (`rendmatt.cc:221-222`) pass `true` so the background is never culled.

**Global toggle.** In the backend, cache `static bool gCull = !(getenv("WF_CULL") && atoi(...)==0)`
(default ON), mirroring the `getenv("WF_GAME_SCREENSHOT_PPM")` precedent at `display.cc:983`. Gate
the whole cull block on it.

**Critical files:**
- `wfsource/source/gfx/glpipeline/backend_modern.cc` — cull test in `DrawTriangle`; `WF_CULL` read; eye-space `Ne`/`Pe` from `_mv`.
- `wfsource/source/gfx/renderer_backend.hp` — `DrawTriangle` signature `+ cullExempt`.
- `wfsource/source/gfx/material.hp` — `IsDoubleSided()` accessor.
- the 8 `wfsource/source/gfx/glpipeline/rend{f,g}{t,c}{l,p}.cc` — pass material's flag through.
- `wfsource/source/gfx/rendmatt.cc` — pass `cullExempt=true` at the two matte draws.

**Verification — A/B, headless, deterministic.** Use the built-in PPM hook
(`WF_GAME_SCREENSHOT_PPM=<path>` → `display.cc:981-1010` writes a frame-30 PPM; reproducible, no
X11 grab). For each shipped level, capture **before** (`WF_CULL=0`, current binary) and **after**
(default cull, patched binary); pixel-diff (`compare -metric AE`). Levels: SMB W1-1..1-4 (matte
background must survive), snowgoons, qbert, filesys, filelight, treemap (densest two-sided-prism
stress), **moon_site01 (interior-viewed skydome — the key must-not-vanish case)**. Gates: (1) no
foreground/interior/skydome/matte surface vanished; (2) prior back-face artifacts (z-fight
speckle, see-through) gone; (3) patched binary with `WF_CULL=0` reproduces baseline pixel-for-pixel
(toggle is the only behavioral change). Any regressor gets a `DOUBLE_SIDED` tag on the offending
mesh rather than disabling the global cull. Record a level×{before,after,AE,verdict} table.

**Plan doc to create on implementation:** `docs/plans/2026-06-13-engine-backface-culling.md` + TODO entry.

---

## Effort 2 — Planetarium dome view (`wflevels/dome/`)

Full design already written to **`docs/plans/2026-06-13-planetarium-dome-view.md`** (created this
turn). Summary:

- **Reuses Filelight's `fl-scan` table verbatim** — depth→**elevation band**, a0/a1→azimuth (rev),
  branch→hue; `seg-size` unused (size lives in the arc). **No `scripting_zforth.cc` change, no
  engine rebuild** — the strongest proof yet of "a new view = new `.fth` + meshes."
- **NEW `wflevels/dome/blender_dome.py`** (cloned from `blender_filelight.py`): astronaut, lights,
  floor, room, Director, ActBoxOR + **player-controlled look-around camera** (see below) +
  per-depth **`spherical_band_geo` patch templates** (idx 12/13/14) + a **zenith cap** (idx 15).
  Elevation bands: cwd cap φ∈[72,90]°, depth1 [50,72]°, depth2 [28,50]°, depth3 [8,28]°;
  hemisphere R≈35. Patch normals point **inward** (toward the player) — which, under software
  culling, is exactly what keeps them visible (normal faces camera ⇒ not culled).
- **Camera — player turns to look around (not Fixed).** Unlike Filelight's `Rotation = Fixed`
  position-tracking camshot, the dome camera follows the **player's heading**: it sits at the
  player (centre of the dome) with a **fixed upward pitch** at the bands, and its **azimuth =
  the player's facing**, so turning the joystick swings the upward view around the dome (the
  natural "stand under the planetarium and look around" feel — no automated spin). Exact CamShot
  config (heading-follow mode + up-pitch + FOV≈80) is an M2 tuning step against a screenshot.
- **Director `.fth` render policy:** `depth→band-tmpl`, per-branch `hsv>rgb` hue (identical to
  Filelight), `spawn0`+`set-rotation` (Z-heading rev) per arc wedge, zenith cap spawned once. No
  height curve (size is angular). Static dome geometry — no `fl-navigate`/`fl-flydown`.
- **NEW `task run-dome`** (mirror of `run-filelight`); build via the generic `task build-level -- dome`.
- **Verification:** M1 static dome renders (N segments, bands + cap, no asserts/out-of-room/terminate,
  <500 pool); M2 per-branch hue + camera framing + screenshot to `wflevels/dome/screenshots/`;
  M3 hot-reload proof (edit Director `.fth` only, rebuild level only, engine untouched).
- **Out of scope:** walk-/aim-to-re-root navigation, size→radial relief, tiered monument
  (#2, the last remaining sunburst variant).

**Dome ↔ culling dependency:** none under software culling — the dome's inward normals are correct
for both lighting and the normal-based cull. Build the dome after culling lands so M2 screenshots
already reflect culling-on.

---

## Sequencing & deliverables

1. **Culling** (engine): implement → `task build` → A/B verify across the level set → commit +
   `docs/plans/2026-06-13-engine-backface-culling.md` + flip `docs/level-design-troubleshooting.md:721`
   note ("culling is now ON by default; mark interior/special meshes `DOUBLE_SIDED`") + TODO.
2. **Dome** (level): `blender_dome.py` → `task build-level -- dome` → `task run-dome` against the
   culling-on binary → M1/M2/M3 verify + screenshot → commit + mark the dome done in TODO
   (filesystem-viz family open-items), link the commit.

Both commits stage **only** their own files (the tree has unrelated `moon_site01`, `.history`,
`y-crdt`, wf-edit changes — leave them).

---

## Outcome — Effort 1 (culling), 2026-06-13

**Shipped the cull mechanism but DEFAULT-OFF (`WF_CULL=1` opt-in)** — not on-by-default as planned.

A/B across 7 shipped levels (frame-30 PPM, `WF_CULL=0` vs on) found:
- **Mechanism correct.** qbert, snowgoons (standalone iff), filesys, moon_site01 (run with its
  `--vram-*` params) are pixel-clean; the matte background is correctly cull-exempt.
- **But the "normals are already correct" premise is false.** Several procedural generators are
  wound **inward** — `add_solid_box` / `make_box_mesh` / `disk_geo`. Derived from
  `CalculateNormal=(v2-v0)×(v1-v0)` (`face.hpi:35`): the box `top` face `(4,5,6,7)` normal is −Z
  (down). So culling removed visible tops — SMB ground top **vanished**, treemap cell tops +
  filelight centre disk **darkened**. These faces were already rendering ambient-only (latent
  under-lighting); culling just exposed it.
- **Reversing winding is not a clean fix.** Tried it on filelight (`disk_geo` + `add_solid_box`)
  and treemap (`add_solid_box`): the disk came out *dimmer* than its intended bright look, and the
  treemap cells were **not** restored — because appearance is entangled with one-sided lighting +
  the `set-color`/`FACE_COLOR` override, not winding alone. (Those edits were **reverted**; the
  levels are byte-identical to before.)

**Decision (user-approved):** ship the mechanism `WF_CULL`-gated, **off by default**; keep all 7
levels pixel-identical; treat "rewind every shipped mesh to consistent normals + flip the default
on" as a **separate scoped effort** (TODO). The planetarium dome — authored with correct normals
from scratch — is the first `WF_CULL=1` consumer.

**Landed (engine, default-off):** the cull in `backend_modern.cc` + `backend_metal.mm`,
`DrawTriangle` `cullExempt` param (`renderer_backend.hp`, stub), `Material::IsDoubleSided()`
(`material.hp`), the 8 `rend*.cc` pass the flag, `rendmatt.cc` cull-exempt. Docs updated
(`level-design-troubleshooting.md`, `level-building.md`) with the winding rule + `WF_CULL` toggle.

> Capture caveat: a fresh post-flip confirmation screenshot wasn't grabbed (display/process
> contention late in the session); default-off is guaranteed by the code (`WF_CULL` unset → cull
> skipped) and the cull path was exercised by the 12-PPM A/B sweep on the same binary.
