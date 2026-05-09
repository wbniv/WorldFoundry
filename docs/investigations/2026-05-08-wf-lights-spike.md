# Phase 0 — Smoke test of existing Light path

**Date:** 2026-05-08
**Branch:** `spike/blender-lights` (from `2026-new-level` HEAD)
**Plan:** [docs/plans/2026-05-08-blender-lights-spike.md](../plans/2026-05-08-blender-lights-spike.md)

Goal of Phase 0: confirm that an Ambient or Directional light authored in a Blender level today actually lights the scene end-to-end via the existing `Light` actor → `ROOM_OBJECT_LIST_LIGHT` → `Light::Set()` → `RenderCamera::SetDirectionalLight()`/`SetAmbientColor()` chain.

## Static verification (chain is fully wired)

Every link in the existing chain is present and consistent:

- **Schema** (`wfsource/source/oas/light.oas`): `lightType` is an `I32` enum with label `"Directional|Ambient"`, plus `lightRed`/`lightGreen`/`lightBlue` as `FX32`.
- **Engine constants** (`wfsource/source/oas/levelcon.h:55-59`): `enum { AMBIENT_LIGHT=0, DIRECTIONAL_LIGHT=1 };`
- **Light actor** (`wfsource/source/game/light.cc:62`, `light.hpi:35`): `if (myOAD->lightType == DIRECTIONAL_LIGHT) { ... SetDirectionalLight(); } else { assert(... == AMBIENT_LIGHT); SetAmbientColor(); }`
- **Per-frame fan-out** (`wfsource/source/game/level.cc:1070–1108`): zeroes lights, iterates `ROOM_OBJECT_LIST_LIGHT`, dispatches by `light->Type()`.
- **Class routing** (`wfsource/source/game/level.cc:293–299`): `Actor::IsLight()` → `Actor::kind() == Light_KIND` auto-routes `Light` actors into the correct list.
- **Backend uniform upload** (`wfsource/source/gfx/glpipeline/backend_modern.cc:292–325`): `SetAmbient`, `SetDirLight` write `u_ambient`, `u_light_dir[]`, `u_light_color[]`.
- **Shader consumption** (`wfsource/source/gfx/glpipeline/backend_modern.cc:82–90`): vertex shader computes `v_lit = u_ambient + Σ u_light_color[i] * max(0, dot(N, u_light_dir[i]))` when `u_lighting != 0`.

snowgoons.lev (`wflevels/snowgoons-blender/snowgoons.lev`) ships with **two `Light` objects** today (lines 1994 and 6102), each with a full `lightRed/Green/Blue/Type` field set. So the path is exercised by the default level — Phase 0 should be a quick visual confirm.

## Bug found while reading the code: enum-inversion between layers

There is an **enum-order mismatch** between three layers that all describe `lightType`:

| Layer | Source | Index 0 | Index 1 |
|---|---|---|---|
| Engine C++ enum | `wfsource/source/oas/levelcon.h:57-58` | `AMBIENT_LIGHT` | `DIRECTIONAL_LIGHT` |
| OAS schema label | `wfsource/source/oas/light.oas` | (label says `Directional`) | (label says `Ambient`) |
| Blender exporter dict | `wftools/wf_blender/export_level.py:1018` | `directional` | `ambient` |
| Blender exporter Lamp-type map | `wftools/wf_blender/export_level.py:1012` | (anything not POINT) | (POINT) |
| Blender exporter STR-label string | `wftools/wf_blender/export_level.py:1023` | writes `"Directional"` when `lt=0` | writes `"Ambient"` when `lt=1` |

The C++ engine and the OAS label disagree. Engine treats `0` as Ambient; OAS schema (and therefore the Blender editor UI and the exporter) treats `0` as Directional. Existing snowgoons lights stored as `lightType=0`:

```
{ 'I32' { 'NAME' "lightType" } { 'DATA' 0l  // Directional|Ambient } { 'STR' "Ambient" } }
```

The on-disc value `0` is consumed by the engine as `AMBIENT_LIGHT` (works correctly because both lights in snowgoons happen to be intended as Ambient). The accompanying STR `"Ambient"` was hand-written in the source `.lev`; the exporter would have written `"Directional"` for the same `0` value. The labels are decorative — the engine reads `DATA`, not `STR` — so the bug is silent today, but anyone authoring a new `Directional` light in Blender (where the exporter writes `lt=0`) will get an Ambient light in-engine, and vice-versa.

This will need fixing as part of the spike. Cleanest options:
- **(a)** Flip the C++ enum to `DIRECTIONAL_LIGHT=0, AMBIENT_LIGHT=1` to match the OAS label, then verify all on-disc levels (snowgoons + qbert + marble madness) are still self-consistent. Adjust the snowgoons authored data if needed.
- **(b)** Flip the OAS label to `"Ambient|Directional"` to match the engine, and update the Blender exporter dict + Lamp-type mapping + STR-label string. Existing levels stay untouched on disc.

Option (b) is lower-risk (no on-disc data churn). Address this in **Phase 0.5** before Phase 1's fallback work — otherwise the fallback path's correctness can't be reasoned about.

## Visual verification: BLOCKED by preexisting `cd.iff` assertion

Built `wf_game` cleanly via `engine/build_game.sh`, but running it (`cd wfsource/source/game && wf_game`) aborts on this assertion:

```
+- ASSERTION MESSAGE ---
AssertMsg: Attempted to read past end of chunk: ALGN  count = 12, _bytesLeft = 4
+- ASSERTION FAILED ---
| _bytesLeft >= count
| in file "wfsource/source/iff/iffread.cc" on line 108
```

This happens during `Opening cd.iff`, well before any rendering. The committed `cd.iff` and the engine's iff reader are out of sync — preexisting on `2026-new-level`, not introduced by this spike. Same behavior with both the working-tree `cd.iff` (md5 `46934ae3...`) and the HEAD-committed one (same md5; working tree matches HEAD).

This blocks the Phase 0 visual confirm. Three ways to unblock, in order of investigation:

1. **Regenerate `cd.iff`** via the iff/level toolchain (`task` build of `cd_*.iff.txt` → iffcomp-rs). If the source `.iff.txt` was updated more recently than the binary `cd.iff`, this will resync them.
2. **Bisect `cd.iff` breakage** to a prior commit (likely qbert WIP touched the asset or the iff reader).
3. **Run a different level** that doesn't share the broken cd.iff codepath, if any exists.

Suggest tackling #1 first — it's the most likely cause and is a one-command fix if the toolchain still works. If that doesn't resolve, this spike will need a sidebar to fix the engine-runs gate before continuing.

## Bug found via prior empirical testing: Ambient propagation broken

Independent of the static chain analysis above, prior runtime testing (recorded in user memory) established that **`lightType=Ambient` does not actually light the scene** — `_ambientColor` does not propagate to the shader's `u_ambient` uniform in practice, even though every link in the chain reads correctly statically. Current workaround in shipping levels is to author all lights as Directional and aim them between visible faces to simulate ambient.

The chain that *should* fire when a snowgoons Ambient light is loaded:

```
Light::Set(_camera, -1)                                  light.hpi:57
  → camera.GetRenderCamera().SetAmbientColor(_color)
    → RenderCamera::_ambientColor = color                camera.hpi:50
                                                         (next frame:)
RenderCamera::RenderBegin()                              camera.cc:221
  → ConvertToGLColor(_ambientColor, lightColor)
  → RendererBackendGet().SetAmbient(...)                 camera.cc:222
    → backend._ambient[0..2] = ...                       backend_modern.cc:295
                                                         (per-draw:)
glUniform3fv(_uAmbient, 1, _ambient)                     backend_modern.cc:544
                                                         shader: vec3 lit = u_ambient + Σ ...
```

Possible disconnects (not yet bisected — sidebar from Phase 0):
- `_color` in `Light::Set` constructed from FX32 `lightRed/Green/Blue` may be miscomputed.
- `level.cc:1070`'s `SetAmbientColor(Color::black)` zero-pass may run *after* the per-light `Set` call due to a per-room iteration ordering quirk, clobbering it.
- `_ambientColor.Validate()` in `camera.hpi:84` may be silently rejecting valid colors.
- snowgoons-specific: snowgoons may have its Ambient lights in a room that isn't the active room when the camera renders (the loop at level.cc:1066 iterates `_theActiveRooms`).

This needs a runtime trace once `cd.iff` loads, not more static reading.

## Phase 0 status

- ✅ Static chain verification: complete; existing path looks wired end-to-end and snowgoons exercises it.
- ❌ **Empirical: Ambient path is broken** (per prior testing). Bisecting where `_ambientColor` gets lost is its own deliverable.
- ⚠️ Enum-inversion bug: identified; needs Phase 0.5 fix before Phase 1.
- ❌ Visual confirmation: blocked by preexisting `cd.iff` load assertion (unrelated to lighting).

## Plan adjustment — proposed new phase

Insert **Phase 0.7 — Diagnose and fix Ambient propagation** between Phase 0.5 (enum-inversion fix) and Phase 1 (zero-light fallback). Without it, the Phase 1 fallback can't be verified ("no lights → full bright") since "Ambient at full brightness" doesn't actually demonstrate working lighting today. Cheapest fix likely lands in either `Light::Set`, `camera.cc:RenderBegin`, or `level.cc:1070` zero ordering.

Phase ordering becomes: 0 (this) → 0.5 (enum fix) → 0.7 (Ambient propagation fix) → 1 → 2 → 3 → 4 → 5 → 6.

Effort revised: optimistic 3.5 days → 4 days; realistic 4–5 days → 5–6 days.

## Recommended next step

1. Resolve the `cd.iff` load failure (likely just regenerate the binary from `cd_*.iff.txt` source).
2. Run snowgoons. Confirm the Ambient bug reproduces.
3. Bisect using DBSTREAM logging at each chain link until `_ambientColor` is found to drop out.
4. Patch the dropout. Verify both Ambient-only and Ambient+Directional levels light correctly.
5. Then proceed to Phase 0.5 enum fix, then Phase 1 fallback.

---

## 2026-05-09 update: Phase 0.5 done, Phase 0.7 reaches a different conclusion than expected

**Phase 0.5 (enum-inversion fix) committed** in `6a2e248`. light.oas label flipped to `"Ambient|Directional"` to match engine `AMBIENT_LIGHT=0, DIRECTIONAL_LIGHT=1`. Blender exporter dict, Lamp-type mapping, and STR-label string all flipped to match. light.oad regenerated via oas2oad-rs; same byte count (label-only delta). Engine rebuilt clean; marble-madness still renders identically.

**Phase 0.7: Ambient is actually working.** Diagnostic `fprintf(stderr, ...)` added at `ModernRendererBackend::SetAmbient` and binary rebuilt. Running `snowgoons-blender/snowgoons-standalone.iff` produced:

```
[diag-ambient] SetAmbient(0.996, 0.996, 0.996)
[diag-ambient] SetAmbient(0.996, 0.996, 0.996)
[diag-ambient] SetAmbient(0.996, 0.996, 0.996)
[diag-ambient] SetAmbient(0.996, 0.996, 0.996)
[diag-ambient] SetAmbient(0.996, 0.996, 0.996)
```

`0.996` = 255/256.0 (Color::Red() returns 255 for FX32 lightRed=1.0; ConvertToGLColor divides by 256). The chain works. The shader receives `u_ambient = (0.996, 0.996, 0.996)` every frame — basically full white — and snowgoons-blender renders fully lit (white snow ground, textured houses). Visual evidence consistent with the diagnostic.

**Memory revision:** The user-memory entry "Ambient lights don't actually work — use Directional" appears to be a misattribution. qbert's `feat: per-face lit/shadow shading for arcade-style fixed colours` (commit 238df2a) was authored as an arcade-aesthetic choice — Q*bert's iconic three-tone-per-cube look mandated explicit per-face colours regardless of any lighting state — not as a workaround for a broken Ambient path. The Ambient propagation chain (`Light::Set` → `RenderCamera::SetAmbientColor` → `RenderCamera::RenderBegin::ConvertToGLColor` → `ModernRendererBackend::SetAmbient` → `glUniform3fv(_uAmbient)`) is intact and functional.

**Bonus bug fix:** while reading `wfsource/source/game/light.hpi:56`, found `assert(index = -1)` (assignment, not comparison). Always passes; harmless because `index` is unused after the assert. Fixed to `assert(index == -1)` as part of this Phase 0.7 commit.

## Phase 0.7 status — REVISED

- ❌ ~~Ambient propagation broken~~ → ✅ Ambient propagation works; memory entry retired.
- ✅ Bonus fix: `assert(index = -1)` typo corrected.
- ✅ Diagnostic removed before commit.

Phase 0.7 collapses to a one-line typo fix + memory cleanup. **Phase 1 (unlit fallback when no lights authored) is now unblocked** as the next thing to tackle. Effort estimate revises back down: realistic 4–5 days.
