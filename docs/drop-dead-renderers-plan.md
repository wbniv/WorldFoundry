# Plan: Remove Dead Rendering Code (PSX, Software, DirectX)

## Context

World Foundry originally targeted PSX, Saturn, DOS, Windows, and Linux. Only the Linux/OpenGL path is active today. This plan removes all dead renderer code: the PSX hardware renderer, the software pipeline (used for PSX emulation on PC), the DirectX renderer, the legacy XWindows renderer, PSX-specific subsystem directories throughout `wfsource/`, and the `#ifdef __PSX__` guards throughout otherwise-kept files.

**Active (keep):** `gfx/gl/` + `gfx/glpipeline/` + all shared gfx code stripped of dead guards  
**Dead (delete):** everything below

---

## Phase 1 — Delete entire dead directories

These are 100% dead and can be `git rm -r`'d:

### Rendering pipelines
| Directory | LOC | Notes |
|-----------|-----|-------|
| `wfsource/source/gfx/psx/` | ~1,767 | PSX GTE renderer |
| `wfsource/source/gfx/softwarepipeline/` | ~1,576 | Software rasterizer / PSX emulation |
| `wfsource/source/gfx/directxpipeline/` | ~600 | DirectX pipeline |
| `wfsource/source/gfx/directx/` | ~2,000 | DirectX renderer |
| `wfsource/source/gfx/xwindows/` | ~400 | Legacy XWindows (superseded by Mesa) |

### PSX subsystem directories
| Directory | LOC | Notes |
|-----------|-----|-------|
| `wfsource/source/audio/psx/` | ~163 | PSX audio (SPU) |
| `wfsource/source/hal/psx/` | ~2,029 | PSX HAL (hardware abstraction) |
| `wfsource/source/math/psx/` | ~1,603 | PSX fixed-point / GTE math |
| `wfsource/source/movie/psx/` | ~437 | PSX MDEC video |
| `wfsource/source/pigsys/psx/` | ~1,648 | PSX libc / ostream shims |

### PSX config files (root-level)
- `wfsource/source/pigsys/cf_psx.h` — defines `__PSX__` and PSX config
- `wfsource/source/pigsys/_cf_psx.cc` — PSX config implementation

**Phase 1 total: ~12,200 lines deleted across ~67 files**

Also delete: `wfsource/source/gfx/gl/wgl.cc` — Windows WGL context init, never compiled on Linux.

---

## Phase 2 — Strip `#ifdef __PSX__` / `RENDERER_PIPELINE_PSX` guards from kept files

71 files contain PSX conditional blocks mixed with live code. Remove the dead branches, leave the active code bare (no ifdef needed since we're Linux-only now).

**Key files (highest PSX guard density):**

| File | PSX guards | Action |
|------|-----------|--------|
| `source/gfx/camera.cc` | 5 (RENDERER_PIPELINE_PSX) | Remove PSX blocks |
| `source/gfx/material.cc` | 6 (RENDERER_PIPELINE_PSX) | Remove PSX blocks |
| `source/gfx/math.cc` | 2 (RENDERER_PIPELINE_PSX) | Remove PSX blocks |
| `source/gfx/rendobj3.cc` | 4 (multiple RENDERER_PIPELINE_*) | Remove PSX + SOFTWARE + DIRECTX blocks |
| `source/gfx/otable.cc` | 6 (`__PSX__`) | Remove PSX blocks |
| `source/gfx/gfxtest.cc` | 11 (`__PSX__`) | Remove PSX blocks |
| `source/game/main.cc` | 12 (`__PSX__`) | Remove PSX blocks |
| `source/game/game.cc` | 8 (`__PSX__`) | Remove PSX blocks |
| `source/cpplib/afftform.cc` | 16 (`__PSX__`) | Remove PSX blocks |
| `source/pigsys/pigsys.hp` | 9 (`__PSX__`) + MachineType enum | Remove PSX, simplify enum |

Also strip PSX guards from: `display.cc`, `display.hp`, `pixelmap.*`, `viewport.*`, `prim.hp`, `otable.hp/hpi`, `texture.cc`, `util.cc`, `rendmatt.cc`, `rendobj2.cc`, `face.hp/hpi`, `material.hpi`, `hal/hal.cc`, `hal/time.cc`, `hal/diskfile.hp`, `streams/binstrm.*`, `savegame/sgin.cc`, `savegame/sgout.cc`, `math/scalar.cc`, `math/matrix3t.cc`, `math/quat.cc`, `pigsys/pigsys.cc`, `pigsys/endian.cc`, `pigsys/assert.cc/hp`.

---

## Phase 3 — Simplify the build system

**`wfsource/GNUMakefile.bld`:**
- Remove the `WF_TARGET=psx` block (~lines 83–95)
- Remove the `WF_TARGET=win` DirectX block
- Remove `ifeq ($(RENDERER_PIPELINE),software)` block
- Keep only the `WF_TARGET=linux` / `RENDERER=gl` / `RENDERER_PIPELINE=gl` path

**`wfsource/GNUMakefile.env`:**
- Remove `-DRENDERER_*` / `-DRENDERER_PIPELINE_*` flag generation — hardcode `-DRENDERER_GL -DRENDERER_PIPELINE_GL` instead

**`wfsource/GNUMakefile.rul`:**
- Remove `.PATH.cc` entries for dead pipeline dirs

---

## Order of execution

0. Create feature branch: `git checkout -b drop-dead-renderers`
1. `git rm -r` all Phase 1 directories + `wgl.cc` (one commit)
2. Strip `#ifdef __PSX__` / PSX renderer guards from kept files (one commit per subsystem — gfx, game, pigsys, etc.)
3. Simplify build system (one commit)
4. Verify: `grep -r '__PSX__\|RENDERER_PSX\|RENDERER_PIPELINE_PSX' wfsource/source/` should return nothing
5. Attempt `make WF_TARGET=linux` to confirm the GL path still compiles

## Final report — exact line counts reduced

When the branch is complete, produce a categorized summary of lines removed (measured against the merge-base with `master`, e.g. `git diff --stat $(git merge-base HEAD master)..HEAD`). Report:

**By category**
- Dead rendering pipelines (`gfx/psx`, `gfx/softwarepipeline`, `gfx/directx`, `gfx/directxpipeline`, `gfx/xwindows`, `gfx/gl/wgl.cc`)
- PSX subsystems (`audio/psx`, `hal/psx`, `math/psx`, `movie/psx`, `pigsys/psx`, `pigsys/cf_psx.*`)
- `#ifdef` guard strippage in kept files (gfx, game, pigsys, cpplib, hal, streams, savegame, math, anim, profile, movement)
- Build system simplification (`GNUMakefile.bld`, `GNUMakefile.env`, `GNUMakefile.rul`)

**For each category, report**
- Lines deleted, lines added, net delta
- File count (deleted / modified)

**Summary line:** total net LOC removed across the whole branch, plus total file count touched. Include a one-line sanity check that the verification grep (Order §4, expanded for SOFTWARE/DIRECTX/XWINDOWS) returns zero.

---

## What is NOT deleted

- `wfsource/source/gfx/gl/` — active Mesa/GLX renderer (except `wgl.cc`)
- `wfsource/source/gfx/glpipeline/` — active GL pipeline
- All shared gfx code (camera, material, rendobj3, etc.) — kept, just stripped of dead guards
- `wftools/wf_viewer/` — standalone viewer, independent of engine renderer
