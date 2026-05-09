# Spike: Blender-authored ambient lights (and friends) in WF engine

**Status:** Phases 0–6 landed on `2026-new-level` 2026-05-08 to 2026-05-09. All code work complete; new OAS fields (radius/cone/energy) deferred per the "Follow-ups — DEFERRED UNTIL LEVEL" section below. Verified end-to-end on snowgoons-blender (lit path); empty-light room and Point/Spot rendering will be exercised by the first new Blender-authored level.

**Implementation log (chronological):**
- `a3cda19` / `e54b1e2` — plan + Phase 0 investigation
- `6a2e248` — Phase 0.5: enum-inversion fix
- `6babf44` — Phase 0.7: confirmed Ambient chain works (memory entry retired) + `assert(index = -1)` typo fix
- `83d5b36` — Phase 1: unlit fallback when no Light objects authored
- `562d10a` — Phase 2: extend `lightType` enum to Ambient|Directional|Point|Spot
- `28598dc` — Phase 3: Blender exporter emits Point/Spot
- `8f90a02` — Phase 4: backend Point/Spot + RB_MAX_LIGHTS 3→8
- `a212e2e` — Phase 5: dispatch Point/Spot from `Light::Set`
- `d2d6a59` — Phase 5.5: dir-light upload moved out of RenderBegin so Point/Spot slots survive

**Carry-over follow-ups (beyond OAS-field deferrals):**
- iOS Metal backend (`wfsource/source/hal/ios/backend_metal.mm`) needs the Phase-4 treatment — unified light type + per-slot pos/radius/cone state. The `2026-ios` branch will pick this up when it merges in this spike.

---

## Context

The WF engine already has a half-wired light path: a `Light` actor class, an OAD schema (`lightRed/Green/Blue` + `lightType` enum `Directional|Ambient`), a Blender exporter that emits those fields, a per-frame loop in `Level::RenderScene` that iterates `ROOM_OBJECT_LIST_LIGHT`, and a modern GL backend that consumes 1 ambient + 3 directional lights via shader uniforms. End-to-end, an Ambient or Directional light authored in Blender today *should* light a scene.

What's missing for the goal "all lights come from the .lev export, no engine defaults, full Amb/Dir/Point/Spot":

1. The OAD `lightType` enum stops at `Directional|Ambient` — no `Point`/`Spot`.
2. The renderer backend's **per-light** path is directional-only — no light position, no per-light radius/attenuation, no spot cone math. (Scene **fog** is unrelated and is fully supported in `backend_modern.cc` — linear fog with color/near/far via `SetFog`/`SetFogEnabled`. It survived the PSX drop. This spike does not touch fog.)
3. There is no audited end-to-end test confirming the existing path actually fires (`level.cc` zeroes lights every frame at lines 1070–1073, then relies on `Light::Set()` to repopulate them — easy to silently break).
4. There is no defined behavior for a level with zero authored lights. User wants **unlit / full-bright** in that case (skip lighting math entirely), not black.

This spike answers: *what is the actual effort to land Amb+Dir+Point+Spot lights, sourced exclusively from `.lev`, with an unlit fallback?* It produces a phased implementation plan and an effort estimate, with each phase scoped to a single commit (per project convention to commit after each phase).

## Current state — confirmed by exploration

| Area | File:line | Notes |
|---|---|---|
| Engine light actor | `wfsource/source/game/light.hp:52`, `light.hpi:30–59` | `Light::Set()` calls `camera.SetDirectionalLight()` / `SetAmbientColor()`; reads transform matrix from `GetPhysicalAttributes()` |
| Per-frame fan-out | `wfsource/source/game/level.cc:1070–1108` | Zeros all lights, iterates `ROOM_OBJECT_LIST_LIGHT`, calls `light->Set(_camera, index)` |
| Class → list routing | `wfsource/source/game/level.cc:293–299`, `Actor::IsLight()` | Auto-routed via `Actor::kind() == Light_KIND` |
| OAD schema | `wfsource/source/oas/light.oad` | `lightType` enum `Directional\|Ambient`; FX32 RGB |
| Backend interface | `wfsource/source/gfx/renderer_backend.hp:46–56,97` | `RB_MAX_LIGHTS = 3`; directional only. The `3` is a vestige of PSX hardware limits — no longer constrains us. |
| GL backend | `wfsource/source/gfx/glpipeline/backend_modern.cc:82–90,292–325` | Vertex-shader `dot(N, dir)` lighting; `SetLightingEnabled(false)` already exists and shader respects it |
| Blender exporter | `wftools/wf_blender/export_level.py:1008–1023` | Emits `lightRed/Green/Blue/Type`; reads `obj.data.color` + custom `lightType` prop. **Does not** read Blender lamp `energy` or `type` |
| Lev parser | `wftools/levcomp-rs/src/lev_parser.rs:71–92` | Schema-agnostic; light fields already parse via generic `find_field()` |

Single GL backend (`backend_modern.cc`) — the legacy fixed-function backend has been retired, so there is only one renderer to extend.

## Branch

Implementation lives on **`spike/blender-lights`**, branched from `2026-new-level` HEAD on 2026-05-08. All phase commits land on that branch; merge target decided when the spike completes.

## Plan

### Phase 0 — Smoke test the existing path (½ day)

Goal: confirm Ambient + Directional already work end-to-end before changing anything.

- Author one Ambient + one Directional light in a Blender test level (e.g. snowgoons-blender or a fresh tiny level). Set the WF `lightType` custom property + the Blender `Light` datablock color. Export → `.lev` → `.lvl` → `.iff`.
- Run `wf_game` and visually confirm illumination changes when those lights' colors change.
- If it doesn't work: bisect. Likely culprits in priority order: (a) exporter not emitting because object class not "Light" / schema not attached, (b) `Actor::IsLight()` not returning true, (c) shader uniforms not bound that frame.

Deliverable: short note in `docs/investigations/2026-05-08-wf-lights-spike.md` recording observed behavior + test level path.

### Phase 0.5 — Fix enum-inversion between OAS / engine / Blender exporter (¼ day)

Goal: make all three layers agree on what `lightType=0` means. Discovered during Phase 0 static reading (see [docs/investigations/2026-05-08-wf-lights-spike.md](../investigations/2026-05-08-wf-lights-spike.md)).

- `wfsource/source/oas/light.oas`: change enum label from `"Directional|Ambient"` → `"Ambient|Directional"` (matches engine `AMBIENT_LIGHT=0, DIRECTIONAL_LIGHT=1` in `wfsource/source/oas/levelcon.h:57`).
- `wftools/wf_blender/export_level.py:1018`: flip dict to `{"ambient": 0, "directional": 1}`.
- `wftools/wf_blender/export_level.py:1012`: flip Lamp-type mapping (Blender `POINT` → 0, others → 1).
- `wftools/wf_blender/export_level.py:1023`: flip STR-label string to `'Directional' if lt else 'Ambient'`.
- snowgoons.lev's existing `lightType=0` data stays correct (engine treats 0 as Ambient; OAS now also says 0 is Ambient).
- `python3 -m py_compile` after every edit.

Rationale for choosing OAS-flip over engine-flip: zero on-disc data churn. Existing snowgoons + qbert + marble-madness levels' `lightType=0` bytes stay valid.

Commit.

### Phase 0.7 — Diagnose and fix broken Ambient propagation (½–1 day)

Goal: make `lightType=Ambient` actually light the scene. Per prior runtime testing (recorded in user memory), `_ambientColor` set via `Light::Set()` does not reach the shader's `u_ambient` uniform despite the chain reading correctly statically. The qbert shipping workaround is per-face lit/shadow colours + Directional lights only — that workaround stays for qbert's arcade-style aesthetic, but new Blender-authored levels need real Ambient to work.

- Run snowgoons (after `cd.iff` regen — see Phase 0 note) and confirm Ambient bug reproduces.
- Add DBSTREAM logging at each chain link to find where the value drops:
  - `Light::Set` else-branch — log `_color` before `SetAmbientColor`.
  - `RenderCamera::SetAmbientColor` (`camera.hpi:46`) — log incoming color and stored `_ambientColor`.
  - `RenderCamera::RenderBegin` (`camera.cc:221`) — log `_ambientColor` immediately before `ConvertToGLColor`.
  - `ModernBackend::SetAmbient` (`backend_modern.cc:292`) — log incoming r/g/b.
  - `ModernBackend` per-draw — confirm `glUniform3fv(_uAmbient, ...)` runs and `_ambient[]` is non-zero.
- Likely culprits (highest probability first):
  - **(a)** `level.cc:1070` zero-pass runs *after* per-light `Set` for the active room iteration, clobbering `_ambientColor`. Trivial fix: re-order, or only zero when no Ambient light is authored.
  - **(b)** `_color` in `Light::Set` is FX32-RGB but `Color` constructor expects different scale/format → silently builds black.
  - **(c)** `_ambientColor.Validate()` (`camera.hpi:84`) silently rejects.
- Fix the dropout. Verify by running snowgoons and visually observing the Ambient light's color affecting unshadowed surfaces.

Commit.

### Phase 1 — Unlit fallback when no lights are authored (½ day)

Goal: when a level has zero `Light` objects, render full-bright instead of black.

- In `wfsource/source/game/level.cc:1070`, before the zero-loop, count the room's `ROOM_OBJECT_LIST_LIGHT` size. If zero → `_camera->GetRenderCamera().SetLightingEnabled(false)`. Else → existing zero+populate path with `SetLightingEnabled(true)`.
- The `u_lighting` uniform branch already exists in the vertex shader (backend_modern.cc:82–91) — no shader change needed.
- Verify: temporarily strip lights from a working level, confirm geometry renders at full albedo, restore lights, confirm lit again.

Commit at end of phase.

### Phase 2 — Extend `lightType` enum only (¼ day)

Goal: data model can name Point/Spot. **No new OAS fields** — per project policy, new field additions to `.oad` schemas are deferred until after the first new level ships. Only the enum widens.

- Edit `wfsource/source/oas/light.oad`:
  - Extend `lightType` enum to `Directional|Ambient|Point|Spot`.
- Rebuild `cd_*.iff.txt` artifacts; confirm existing levels still load (oracle-mirror-first: zero byte change for existing Directional/Ambient lights — adding enum values does not move existing field bytes).
- No engine code change yet — `Light::Set()` will hit the `default:` arm for Point/Spot and do nothing. Intentional.

Commit.

### Phase 3 — Extend Blender exporter to emit Point + Spot type (¼ day)

Goal: `.lev` carries the new `lightType` values. No new fields (radius/cone deferred — see Follow-ups).

- `wftools/wf_blender/export_level.py:1008–1023`:
  - Map Blender `obj.data.type` → WF `lightType`: `POINT→Point`, `SUN→Directional`, `SPOT→Spot`, `AREA→Point` (best-effort).
  - Continue to allow a manual override via custom property (existing path) for Ambient.
  - **Do NOT** emit `lightRadius`, `lightConeAngle`, or `lightEnergy` — those OAS fields don't exist yet (see Follow-ups TODO).
- `python3 -m py_compile` after every edit per project convention.
- Test by exporting a level with each type and grepping `.lev` text for the new `lightType` values.

Commit.

### Phase 4 — Backend: extend renderer for Point + Spot (1–1½ days)

Goal: shader and backend interface support the new types.

- `wfsource/source/gfx/renderer_backend.hp`:
  - Bump `RB_MAX_LIGHTS` from 3 → **8** (plus the existing 1 ambient slot). Rationale: matches Unity URP Mobile (8 additional) and Godot 4 Mobile (8 omni + 8 spot); safe on the weakest realistic Google TV target (Chromecast-w/-Google-TV, Mali-G31 MP2); leaves ample headroom on flagship phones / Shield TV. The legacy `3` was a PSX hardware vestige and is no longer a constraint. Uniform-array footprint stays small (~6 vec4 × 8 = 48 vec4 of light data, well under the GLES 3.0 ~256-vec4 default budget).
  - Add `SetPointLight(idx, pos, color, radius)` and `SetSpotLight(idx, pos, dir, color, radius, coneRev)` virtuals; keep `SetDirLight` for Directional.
  - Add a per-light `type` field stored in backend state.
- `wfsource/source/gfx/glpipeline/backend_modern.cc:292–325`:
  - Add uniforms: `u_light_type[N]`, `u_light_pos[N]`, `u_light_radius[N]`, `u_light_cone[N]`.
  - Vertex shader: replace the hardcoded directional `dot(N, dir)` (line 86) with a per-light branch on `u_light_type[i]`:
    - Directional: existing `dot(N, dir)`.
    - Point: `L = pos - worldPos; atten = max(0, 1 - length(L)/radius); lit += color * max(0, dot(N, normalize(L))) * atten;`.
    - Spot: like Point, multiplied by `smoothstep(cos(coneOuter), cos(coneInner), dot(-spotDir, normalize(L)))`. Convert revolutions→radians inside the shader (`* 2π`).
  - Keep `u_lighting` early-out unchanged — Phase 1 fallback still works.
- Verify shader compiles on GLES 3.0 (Android target) — branchy uniform indexing is fine on that profile.

Commit.

### Phase 5 — Engine: dispatch new types in Light::Set (½ day)

Goal: connect Light actor to new backend methods, using **hardcoded defaults** for radius and cone angle (those OAS fields are deferred).

- `wfsource/source/game/light.hpi:30–59`:
  - Add `case Point:` → read transform position from `GetPhysicalAttributes().Matrix()`; call `camera.SetPointLight(index, pos, color, /*radius=*/kDefaultPointRadius)`.
  - Add `case Spot:` → read position + forward axis from matrix; call `camera.SetSpotLight(index, pos, dir, color, /*radius=*/kDefaultPointRadius, /*coneRev=*/kDefaultSpotCone)`.
  - Defaults to define near top of file with `// TODO: read from OAS once lightRadius/lightConeAngle fields exist (see plan: deferred until level)`. Suggested values:
    - `kDefaultPointRadius` = 10.0 world units
    - `kDefaultSpotCone` = 0.083 revolutions (≈30°)
- Add `RenderCamera::SetPointLight` / `SetSpotLight` thin wrappers in `wfsource/source/gfx/camera.cc:221–235` that forward to the backend.
- Verify with a level containing all four types: visually distinct lit areas. Brightness/coverage will not be tunable per-light yet — that lands when Follow-ups #1 ships.

Commit.

### Phase 6 — Audit + cleanup (½ day)

- Confirm no "default" lights are created anywhere in the engine. Grep for `SetDirLight`, `SetAmbient`, `glLight`, hardcoded color literals in any rendering path. The only call sites should be inside `Light::Set()` and the Phase 1 zero-fallback toggle.
- Update `wfsource/source/game/level.cc:1070–1073` comment to describe the new "no defaults; full-bright if empty" contract.
- Confirm a freshly empty `.lev` (no Light objects) loads and renders unlit.
- Update `docs/wf-status.md` rolling summary (one sentence at the top per project convention).

Commit.

## Effort estimate

Updated 2026-05-09 after Phase 0 surfaced two preexisting bugs (enum-inversion + Ambient propagation) requiring new Phases 0.5 and 0.7.

- **Optimistic**: 4 working days.
- **Realistic**: 5–6 working days. Most likely overruns: Phase 0.7 (Ambient propagation bisect) blowing past 1 day, Phase 4 shader debugging on Android/GLES.
- **Pessimistic**: 8 days if the `lightType` enum on-disc encoding turns out to be a U8 with no spare values, forcing the deferred-fields conversation to happen now after all.

## Critical files (quick reference)

- `wfsource/source/oas/light.oad` — schema
- `wfsource/source/game/light.hpi:30–59` — actor → backend dispatch
- `wfsource/source/game/level.cc:1070–1108` — per-frame light loop, fallback hook
- `wfsource/source/gfx/renderer_backend.hp` — backend interface, `RB_MAX_LIGHTS`
- `wfsource/source/gfx/glpipeline/backend_modern.cc:82–90,292–325` — shader + uniforms
- `wfsource/source/gfx/camera.cc:221–235` — RenderCamera façade
- `wftools/wf_blender/export_level.py:1008–1023` — Blender → `.lev`
- `wftools/levcomp-rs/src/lev_parser.rs:71–92` — generic field parsing (no change expected)

## Verification (end-to-end)

1. Build engine: `task build`.
2. Build a Blender test level with one of each light type (Ambient, Sun, Point, Spot) plus a flat plane and a sphere; export to `.lev`; compile to `.iff`.
3. Run `wf_game` against that level; visually confirm:
   - Ambient lifts shadowed sides.
   - Sun produces correct directional shading.
   - Point's brightness falls off with distance to the sphere; outside `lightRadius` is unaffected.
   - Spot illuminates only inside the cone.
4. Delete all lights from the same level, re-export, re-run; confirm full-bright albedo (Phase 1 fallback).
5. Run snowgoons unchanged; confirm no regression vs current visual.
6. Android APK build (`task build-cmake-android` + `task build-apk`); confirm shader compiles on GLES 3.0.

## Follow-ups — DEFERRED UNTIL LEVEL

These add new fields to `.oad` schemas, which the project policy currently defers until after the first new level ships. Bundle them as a single follow-up pass once that gate clears.

- **`lightRadius` (FX32) on Light.oad** — replaces the hardcoded `kDefaultPointRadius` in Phase 5. Used by Point and Spot lights for attenuation falloff. Blender exporter reads `obj.data.cutoff_distance` (or shadow soft size as fallback).
- **`lightConeAngle` (FX32, revolutions) on Light.oad** — replaces the hardcoded `kDefaultSpotCone` in Phase 5. Used by Spot. Blender exporter reads `obj.data.spot_size` and converts radians → revolutions.
- **`lightEnergy` (FX32) on Light.oad** — explicit brightness multiplier independent of color. Blender exporter reads `obj.data.energy`. Currently brightness is encoded by RGB magnitude alone — workable but lossy.
- Shadows. **Note:** the engine already has a `Shadow` actor (`wfsource/source/game/shadow.{hp,cc}`, `wfsource/source/oas/shadow.oad`, plus `shadowp` projected variant) — a cheap per-actor blob/projected-shadow system designed for late-90s hardware constraints. **Not sacred:** the existing implementation is open for replacement, not just augmentation. Options span the spectrum: (a) keep the current Shadow actor, drive its projector from the brightest authored Light; (b) replace it with a real shadow-map pass keyed off Lights (Directional/Spot first, omnidirectional cubemap for Point later); (c) something in between (cascaded shadow maps for Sun-class Directional, projector blobs for everything else). Decision deferred — depends on perf budget on Mali-G31-class Google TV and how much shadow fidelity the new levels actually need.
- Per-room / per-object light culling: when more than `RB_MAX_LIGHTS` lights are visible, sort by `intensity / distance²` and pick the brightest N. Trivial to add once we have a real test case that exceeds 8.
- Revisit `RB_MAX_LIGHTS=8` if profiling on a Mali-G31 Google TV shows fragment-shader cost is the bottleneck (drop to 4) or if a level designer needs more (raise to 16, still cheap on flagships).
- HDR / tonemapping (lights can currently overflow `[0,1]` in shader — clamping in vertex output saves it but cheaply).

---

*This plan file lives in the harness at `~/.claude/plans/`. Per project convention, on approval also copy to `docs/plans/2026-05-08-blender-lights-spike.md` before implementation begins.*
