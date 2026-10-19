# Investigation: Earth + Sun + Stars in the moon sky (Phase 0, reverted)

**Date:** 2026-06-01
**Status:** Reverted. All code and assets backed out; investigation kept as a record.

## TL;DR

Attempted to add an Earthrise composition (textured Earth + emissive Sun + starfield skydome) to `wflevels/moon_site01`. Spent ~3 h. The infrastructure all landed — actors spawned, textures vendored, lighting authored — but the **visual end-state never read on screen**: Earth/Sun render but appear indistinguishable from the surrounding terrain at the existing camera framing, and the camera-tilt attempt didn't propagate into a wider sky band. The whole branch was reverted; this doc captures what was tried so the next attempt doesn't re-do the dead-ends.

Restorable from commit **[`82acc135`](https://github.com/wbniv/WorldFoundry/commit/82acc135)** (`feat(moon): sky-actor Phase 0 — Earth + Sun spawn, visual tuning incomplete`). Re-checkout the relevant files with `git checkout 82acc135 -- <path>` to bring the work back.

## What was tried

### 1. Earth as a textured sphere

- **Asset:** NASA Blue Marble (https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57752/land_shallow_topo_2048.jpg), downsized 2048×1024 → 512×256 TGA, public domain.
  - **Restore:** `git checkout 82acc135 -- wflevels/moon_site01/earth.tga`
- **Mesh:** 20 m UV-sphere, 24-segment / 12-ring, smooth-shaded.
- **Material:** Principled BSDF with the texture wired into Base Color, base RGB forced to white so WF's fragment shader (`wfsource/source/gfx/glpipeline/backend_modern.cc:115`) takes the `is_white = step(0.99, …)` branch and actually samples the texture instead of using vertex color directly.
- **Actor class:** `platform`, `wf_Mobility='Anchored'`. Spawned correctly at idx=12 (bridge-confirmed via `--debug-print-actors`).
- **Helper:** `_build_earth()` in `wflevels/moon_site01/blender_create_moon.py` of commit `82acc135`.

### 2. Sun as an emissive sphere

- **Mesh:** 8 m UV-sphere, 16-segment / 8-ring.
- **Material:** Solid off-white via `_make_mat`, emission color + strength set.
- **Position:** computed from `SUN_AZ_DEG=20`, `SUN_ALT_DEG=2` at 800 m distance → `(273.4, 751.3, 27.9)`.
- **Restore:** `git checkout 82acc135 -- wflevels/moon_site01/sun.iff` and the `_build_sun()` helper in the Blender script.

### 3. Starfield skydome (attempted, abandoned)

- **Generator:** `wflevels/moon_site01/make_starfield.py` — procedural ~850 stars over black, 512×256, deterministic via `np.random.default_rng(seed=2026_06_01)`. Restorable: `git checkout 82acc135 -- wflevels/moon_site01/make_starfield.py wflevels/moon_site01/starfield.tga`.
- **Mesh:** R=200 m inverted-normal UV-sphere centred on the play area, emissive starfield texture.
- **Why it was abandoned:** at R=200 m the skydome surface is closer to the camera than the terrain at y > 200 m → opaque sphere occludes the terrain, lander, astronaut. Growing it past R~1100 m pushes outside the room bbox (would need another room bump, and even then it'd occlude the lander at distance). The correct path is either `MatteType=2` (the legacy Tiles/Map background plane — see `wfsource/source/oas/mesh.inc:21-27`) or a depth-disabled skybox draw, neither of which fits in a Phase-0 budget.

### 4. Ambient light — *the most useful finding*

This is the **load-bearing discovery** of the investigation, applicable to any future moon-sky work:

- `wfsource/source/gfx/glpipeline/backend_modern.cc` vertex shader at line 84: `vec3 lit = u_ambient; for (i…) lit += u_light_color[i] * max(0.0, dot(N, u_light_dir[i]));`. **There's no implicit ambient.** The ambient term comes from `u_ambient`, which is set by `Camera::SetAmbientColor`.
- `wfsource/source/game/level.cc:1158` defaults the camera ambient to `Color::black`. So the only way to raise it is to author an `Ambient`-type Light actor — `wfsource/source/game/light.hpi:57` is where that flows back to the camera.
- For the moon's near-grazing-altitude directional light (`SUN_ALT_DEG=2`), the dot-product term is near-zero across most of any spherical actor → without ambient, Earth's hemisphere facing the camera renders pure black.
- **Setting an Ambient light at (0.4, 0.42, 0.5) brightens the scene appropriately** — the terrain stays dramatic-but-readable, Earth's shadowed hemisphere becomes a dim blue-grey. (At 1.0 it over-exposes everything; below ~0.25 it's too dim to help.)

### 5. Camera tilt to Earthrise framing — *unsolved*

- **Attempt:** raised `LOOK_TARGET` from `(0, 0, 0)` to `(0, 0, 50)`, switched the camshot `wf_Rotation` from `Fixed` to `Track`, and explicitly set `camshot.rotation_euler` from the camera→target direction. Expected pitch −38.7° → −16.7°, sky band ~5–10% → ~50% of frame.
- **Observed:** the lander DID shift lower in frame (consistent with the new tilt), suggesting the math is correct, but the sky band remained narrow. Either the camera is partially tilted, or the visible difference is smaller than expected because the terrain extends further laterally than my back-of-envelope.
- **Where to look next:** `wfsource/source/game/movecam.cc:296-315` is where the camshot's outgoing direction is built — line 314 (`outPos.direction = targetPos - camShotPos`) already aims at the Target, so the math should propagate. `wfsource/source/game/movecam.cc:337-376` is the `Track`/`Fixed` rotation branch, but it post-multiplies the direction by the TrackObject's rotation matrix — which probably wasn't what I wanted. **Hypothesis: `Track` rotates the camshot frame around the player's heading, on top of the target-look; `Fixed` does neither, just uses the explicit camshot orientation.** Try `Fixed` with the rotation_euler set, and accept the camera may need to be more aggressively tilted than my +30° guess to actually expand the sky band.

### 6. Room bbox expansion

- Bumped `ROOM_HALF` from 510 to 1000 in `blender_create_moon.py` so Earth (y=600 in early placement) and Sun (y=751) wouldn't trigger `levcomp-rs` warnings "actor falls outside every room bbox — it will not render". This is a structural-not-cosmetic change that the next attempt will probably want to keep regardless of the visibility approach.
- **Restore:** the `ROOM_HALF = max(HALF_M + 10.0, 1000.0)` line in the room-bbox block of commit `82acc135`'s `blender_create_moon.py`.

### 7. Textile + VRAM page bumps

The new sky textures (earth.tga 512×256, starfield.tga 512×256) couldn't fit alongside the existing 1024² terrain texture in Room0's atlas at the default `PAGEY=1024`. Bumped:

- `wflevels/moon_site01/textile.flags`: `PAGEY=1024 → 2048`
- `Taskfile.yml` run-moon command: `--vram-slot-height=1024 → 2048`

Both must move together — the textile atlas size must fit in the engine's transient VRAM slot. If a future approach keeps the sky textures, this pair stays bumped.

## What WORKED but was reverted

| Component | What's salvageable |
|---|---|
| `_build_earth()` / `_build_sun()` helpers | Reuse verbatim from commit `82acc135`; just refine positioning and lighting separately |
| Blue Marble texture (earth.tga) | Public-domain, asset stays valid; re-checkout from the commit |
| Procedural starfield generator | Works, deterministic, can be re-pointed at any sphere/skybox |
| `Ambient`-type Light authoring | The key discovery — *any* moon-sky attempt needs this. The 5-line block in the script (copy `light`, set `wf_lightType='Ambient'`, set RGB ~0.4) is reusable |
| Room bbox expansion | Trivial 2-line change; will be needed if any sky actor is outside the terrain extent |
| `textile.flags PAGEY=2048` + matching `--vram-slot-height` | Will be needed for any sky-texture path |

## What DIDN'T WORK / open questions

- **Camera tilt didn't visibly expand the sky band.** The Earthrise math gives a 50% sky band on paper but the captured frame stayed mostly terrain. Either the camera isn't actually tilted to −16.7°, or the visible terrain extends much further than my naive horizon math. Investigation path: instrument `movecam.cc` to log the camera direction each frame, or use the debug bridge to query the actual camera orientation post-init.
- **Earth visible at ambient=1.0 only.** The lit crescent appears clearly upper-right when ambient is maxed out — but the rest of the scene over-exposes. At ambient=0.4 (terrain looks right), Earth's tonality (texture × ambient + grazing N·L) collapses into the same value range as the lit regolith, and it disappears. **Proper fix needs a per-material unlit/emissive flag** through MATL → shader:
  - `wftools/wf_blender/export_level.py:488-512` extracts MATL flags; needs a new bit (e.g., 0x04) set when the Blender material has Emission Strength > 0.
  - `wfsource/source/gfx/glpipeline/backend_modern.cc:84` builds `v_lit`; needs to read the new flag (per-draw uniform, similar to `u_use_tex`) and skip the lighting calc when set — output `vec3(1.0)` for "unlit".
  - The MATL parser pipeline in `wfsource/source/gfx/rendobj3.cc` is where the flag flows from the IFF to the renderer.
- **Skydome can't grow past the room bbox** to enclose the lander. Needs `MatteType=2` or a depth-disabled rendering path.
- **`Rotation=Track` semantics** in `movecam.cc:337-376` aren't what their name suggests — they rotate around player heading, NOT around the target. Documentation gap.

## Recommended Phase 1 plan

In order:

1. **Land the unlit-material flag** — biggest single unlock. Extends `export_level.py` + `backend_modern.cc` + `rendobj3.cc`. Once Earth and Sun can render "self-illuminated", every other thing downstream gets easier (no fighting ambient, no positioning around lit-vs-shadowed hemisphere).
2. **Diagnose the camera tilt** — bridge-query the actual camera orientation post-init, or instrument `movecam.cc` to print it each frame. Once we know the camera *actually* points where we want, we can position Earth/Sun against the sky band confidently.
3. **Re-land Earth/Sun** with the unlit flag + the diagnosed camera. The actor helpers from `82acc135` plug back in unchanged.
4. **Stars: a real skybox path.** Either wire `MatteType=2` (Tiles/Map parsing — see `wfsource/source/gfx/matte.cc`) or add a depth-disabled draw for a far-distance sphere. The starfield generator is ready to feed either.

## File / asset checkout commands

```bash
# Re-stage everything from the reverted commit:
git checkout 82acc135 -- \
    wflevels/moon_site01/blender_create_moon.py \
    wflevels/moon_site01/textile.flags \
    wflevels/moon_site01/earth.tga \
    wflevels/moon_site01/starfield.tga \
    wflevels/moon_site01/make_starfield.py \
    wflevels/moon_site01/earth.iff \
    wflevels/moon_site01/sun.iff \
    Taskfile.yml

# Or to grab just the assets without the script:
git checkout 82acc135 -- \
    wflevels/moon_site01/earth.tga \
    wflevels/moon_site01/starfield.tga \
    wflevels/moon_site01/make_starfield.py
```

## Verification screenshots from the failed attempt

The Phase-0 commit included two captures that show the failure modes; they're at `docs/plans/screenshots/2026-06-01-moon-sky-earth-mid-frame.png` (current ambient=0.4 — Earth lost in terrain) and `…-visible-full-ambient.png` (ambient=1.0 — Earth's crescent visible upper-right but scene over-exposed). After the revert those screenshot files are gone too; restorable from the same commit if a future investigation wants them.
