# Plan: Remove Dead Rendering & Platform Code

## Context

World Foundry originally targeted PSX, Saturn, DOS, Windows, and Linux. Only the Linux/OpenGL path is active today. This plan removes all dead renderer code (PSX hardware, software rasterizer, DirectX, legacy XWindows) and all non-Linux platform code (Win/Saturn/DOS guards and subsystem directories). `__LINUX__` guards are **deliberately preserved** so a future port to another platform (macOS, BSD, handheld, etc.) can start from "here are the Linux-specific paths" rather than rediscovering them.

**Active (keep):** `gfx/gl/` + `gfx/glpipeline/` + all shared gfx code, stripped of PSX/Win/DirectX/Software guards but with `__LINUX__` guards intact.

**Dead (delete):** PSX & Windows renderer dirs, PSX & Win subsystem dirs, obsolete single files (see Phase 1). Also strip `__PSX__`, `__WIN__`/`_WIN32`, `__SATURN__`, `__DOS__`, `RENDERER_{PSX,SOFTWARE,DIRECTX,XWINDOWS}`, `RENDERER_PIPELINE_{PSX,SOFTWARE,DIRECTX}`, and `SCALAR_TYPE_FIXED` guards from the ~90 kept files.

**Active build entry point:** `wftools/wf_engine/build_game.sh` (hand-rolled bash) — *not* the GNU makefiles. `task run` invokes the pre-built binary it produces.

---

## Why delete Windows code rather than preserve it for Xbox?

Future platform interest is Xbox, not Windows PC. The tempting-but-wrong instinct is "Xbox is Windows-adjacent, keep the `__WIN__` code as a head start." In fact the Windows code here is worse than useless for modern Xbox:

1. **Vintage DirectX.** `gfx/directx/` is DX5/6/7 era with DirectDraw and a `winmain.cc`/`winproc.cc` scaffolding. Modern Xbox (One / Series) uses DX11/12 + GDK; the API surface is unrecognizable. `audio/win/` is DirectSound, deprecated in favor of XAudio2 / WASAPI. The 1999 code isn't a head start — it's a map drawn before the terrain was built.

2. **`__WIN__` guards aren't porting scaffolding; `__LINUX__` guards are.** In the Shape-D platform chains, `#elif defined(__WIN__)` is a dead *selector* branch alongside the `#elif defined(__LINUX__)` branch that actually marks "here's a platform boundary, fork here." Stripping `__WIN__` and keeping `__LINUX__` loses zero porting signal. When Xbox work starts, grep `__LINUX__`, every hit is a decision point, add an `__XBOX__` arm at the same location.

3. **Git history preserves everything.** If in 2028 you want to inspect 1999's `hal/win/` or `winmain.cc`, `git show <commit>^:path/to/file` brings it back verbatim. Deletion on HEAD is not loss.

**Optional belt-and-braces:** before the Phase 1 commit on this branch, tag the parent commit as `preserved/pre-drop-dead-renderers` (or similar) so the pre-deletion state is trivially accessible by name later without having to remember a SHA. Zero ongoing cost.

---

## Phase 1 — Delete entire dead directories and files

All `git rm -r` safe; `build_game.sh` doesn't compile any of these, and every cross-reference from a kept file is guarded so the preprocessor skips it on Linux.

### Rendering pipelines

| Directory | Notes |
|-----------|-------|
| `wfsource/source/gfx/psx/` | PSX GTE renderer |
| `wfsource/source/gfx/softwarepipeline/` | Software rasterizer / PSX emulation (mostly `.ccs`/`.bas`/`.exs`/`.ins` prep-DSL) |
| `wfsource/source/gfx/directxpipeline/` | DirectX pipeline |
| `wfsource/source/gfx/directx/` | DirectX renderer (~16k lines of C++, including winmain/winproc/d3d*) |
| `wfsource/source/gfx/xwindows/` | Legacy XWindows (superseded by `gfx/gl/`); contains its own `wgl.cc` and `mesa.cc` |

### Subsystem `psx/` and `win/` directories

| Directory | Notes |
|-----------|-------|
| `wfsource/source/audio/psx/`, `wfsource/source/audio/win/` | PSX SPU & Windows audio |
| `wfsource/source/hal/psx/`, `wfsource/source/hal/win/` | PSX & Windows HAL |
| `wfsource/source/math/psx/`, `wfsource/source/math/win/` (incl. `msvc/`, `watcom/`) | PSX fixed-point / Windows math |
| `wfsource/source/movie/psx/` | PSX MDEC video |
| `wfsource/source/pigsys/psx/` | PSX libc / ostream shims |
| (check `wfsource/source/pigsys/win/` if present) | Win pigsys shims |

### Single files

- `wfsource/source/pigsys/cf_psx.h`, `wfsource/source/pigsys/_cf_psx.cc`
- `wfsource/source/pigsys/cf_win.h`, `wfsource/source/pigsys/_cf_win.cc`
- `wfsource/source/gfx/gl/wgl.cc` — Windows WGL context init; never compiled on Linux (already in `build_game.sh` SKIP)
- `wfsource/source/gfx/gl/unused.cc` — already in `build_game.sh` SKIP
- `wfsource/source/gfx/xwindows/wgl.cc` — GLX variant; goes with the xwindows/ delete
- `wfsource/source/pigsys/psxlink.txt`, `wfsource/source/game/psxlink.txt` — PSX linker scripts
- `.rc` / `.ico` resource files (Windows only): `wfsource/source/gfx/gfxtest.rc`, `pigsys/psystest.rc`, `hal/haltest.rc`, `attrib/udm/udm.rc`, `gfx/directx/boids2.rc`, `gfx/directx/d3d.ico`, `hal/dxview.ico` (most covered by dead-dir deletes; listed for the sweep)
- Optional: OpusMake `Makefile*` files (`wfsource/Makefile.psx`, `wfsource/Makefile.win`, `wfsource/Makefile.template`, `wfsource/source/Makefile.inc`, per-subsystem `Makefile` NMAKE variants). Cosmetic; not on critical path.

After Phase 1, `build_game.sh` should still build and `task run` should still work — verify before proceeding.

---

## Phase 2 — Strip dead preprocessor guards (keeping `__LINUX__`)

### Use `unifdef`, not sed or hand-edits

`unifdef` is preprocessor-aware and handles the five guard shapes in this codebase correctly; hand-editing across ~90 files is where regressions come from. Per-file or per-directory invocation:

```
unifdef -m \
  -U__PSX__ -U__WIN__ -U_WIN32 -U__SATURN__ -U__DOS__ \
  -URENDERER_PSX -URENDERER_SOFTWARE -URENDERER_DIRECTX -URENDERER_XWINDOWS \
  -DRENDERER_GL \
  -URENDERER_PIPELINE_PSX -URENDERER_PIPELINE_SOFTWARE -URENDERER_PIPELINE_DIRECTX \
  -DRENDERER_PIPELINE_GL \
  -USCALAR_TYPE_FIXED -DSCALAR_TYPE_FLOAT \
  <file>
```

`__LINUX__` is intentionally neither `-D`'d nor `-U`'d: unifdef leaves `#if defined(__LINUX__)` and `#if !defined(__LINUX__)` conditions untouched. This preserves the Linux-specific/platform-specific distinction for future porting work.

### The five guard shapes, and how `unifdef` handles each

**Shape A — dead block**
```c
#if defined(__PSX__)
   <psx body>
#endif
```
→ block removed. Straightforward.

**Shape B — inverted guard, body is live**
```c
#if !defined(__PSX__)
   <live body>
#endif
```
→ guards removed, body kept. A naive regex sweep would nuke the live body; `unifdef` does it right.
Instances: `pigsys/pigsys.hp:203-205` (`ABS`), `pigsys/pigsys.cc:198` (`sys_fgetc`), `gfx/otable.cc:146`, `game/actor.cc:138`, many `math/*`.

**Shape C — if/else, live body in `#else`**
```c
#if defined(__PSX__)
   <psx>
#else
   <live>
#endif
```
→ collapses to just `<live>`.
Instances: `pigsys/pigsys.hp:283-343` (iostreams), `pigsys/memory.hp:79`, `gfx/otable.hp:45`, `oas/levelcon.h:40,216`, `cpplib/strmnull.hp:48`, `movement/inputmap.hp:44`, `pigsys/genfh.hp:46,100`, `machine.hp:33`.

**Shape D — platform if/elif chain (crucial for Linux-guard preservation)**
```c
#if defined(__WIN__)
   <win>
#elif defined(__PSX__)
   <psx>
#elif defined(__LINUX__)
   <linux>
#else
   #error Undefined platform
#endif
```
→ collapses to `#if defined(__LINUX__) / <linux> / #else #error / #endif`. The `__LINUX__` guard stays as documentation of platform-specific code.
Instances: `pigsys/pigsys.hp:94-104` (`_MKINC` selector), `gfx/viewport.cc:29-40`, `gfx/display.cc:29-41`, `gfx/rendobj3.cc:43-52` (pipeline `#include` chain), `gfx/material.cc:64-70`, `math/scalar.cc:32-36` (nested under `SCALAR_TYPE_FIXED` which is also swept).

**Shape E — `#if !defined(__LINUX__)` block**
```c
#if !defined(__LINUX__)
   <code for non-Linux platforms>
#endif
```
→ **left in place** by `unifdef`. This is exactly the "recovered porting work" to preserve for future platforms.
Instances: `pigsys/pigsys.hp:444-454` (redefines `strcmp → sys_strcmp` etc.) and similar.

### File universe

- **~76 files** with `__PSX__` guards outside deleted dirs (grep `__PSX__` in `wfsource/source` minus deleted paths).
- **63 files** with `__WIN__` / `_WIN32`.
- **4 files** with `__SATURN__` / `__DOS__` (`hal/platform.h`, `hal/time.{cc,hp}`, `machine.hp`).
- **24 files** with `RENDERER_SOFTWARE` / `RENDERER_DIRECTX` / `RENDERER_XWINDOWS` / `RENDERER_PIPELINE_{SOFTWARE,DIRECTX}`.
- Additional: `SCALAR_TYPE_FIXED` (e.g. `math/scalar.cc:31`).

Largely overlapping — run `unifdef` over every `.cc`/`.hp`/`.hpi`/`.h` under `wfsource/source/` (excluding already-deleted dirs); files with zero guards are rewritten unchanged.

### Commit cadence

One commit per subsystem. Suggested order, leaves-first so coupling surfaces late:

1. `profile/`, `particle/`, `console/`, `anim/`, `oas/`, `machine.hp`, `memory/`
2. `pigsys/`
3. `hal/`
4. `math/`
5. `cpplib/`, `streams/`, `savegame/`
6. `gfx/`
7. `game/`

After each commit: `bash wftools/wf_engine/build_game.sh` must succeed. Shape B/C regressions surface as compile errors immediately.

### Watch items

- **`pigsys/pigsys.hp` MachineType enum**: do **not** shrink the enum. Let `unifdef` strip code that branches on its values; the enum itself is cheap documentation. If any call site still compares against a removed value, fix it in the same commit.
- **`gfx/material.cc` pipeline-include collapse (Shape D)**: must end up including the `glpipeline` arm. A typo here wires up the wrong renderer → black screen at runtime, not a compile error. Same caution for `gfx/viewport.cc`, `gfx/display.cc`, `gfx/rendobj3.cc`.
- **`SCALAR_TYPE_FIXED`**: the outer guard in `math/scalar.cc:31` wraps PSX/Win/Linux sub-guards. Stripping `SCALAR_TYPE_FIXED` first flattens it; then the inner chain collapses under Shape D.

---

## Phase 3 — Post-sweep cleanup

### Prune `wftools/wf_engine/build_game.sh`

The `SKIP` array (`build_game.sh:48-98`) currently excludes files that didn't build with PSX/Win guards present. After the sweep, re-test each and remove from SKIP if they now compile:

- `gfx/otable.cc`
- `cpplib/afftform.cc`
- `math/matrix3t.cc`, `math/quat.cc`, `math/tables.cc`
- `hal/dfoff.cc`

Leave SKIP entries for files that are genuinely excluded for other reasons (test harnesses, stub replacements, etc.).

### Empty-on-Linux files

- `wfsource/source/profile/sampprof.cc` wraps its entire body in `#if defined(__PSX__)`; `sampprof.hp:8` has `#if !defined(__PSX__) #error`. Both are empty on Linux after the sweep. Delete both, drop `profile` from `build_game.sh:139` `DIRS`, leave `profile.txt` (note file) if you like.
- Audit for similar files: `grep -rlE '^#if\s*(defined\s*\(\s*)?__PSX__' wfsource/source --include='*.cc' --include='*.hp*'` and spot-check any whose body is near-entirely PSX-gated.

### GNU / OpusMake makefiles

Not on the critical path — `build_game.sh` is the real build. Choose:

- Leave them. Cosmetic clutter; zero functional impact.
- Delete the `WF_TARGET=psx` / `WF_TARGET=win` branches from `wfsource/GNUMakefile.bld` and the `!if "$(WF_TARGET)" == "psx/win"` arms of OpusMake `Makefile*`/`Makefile.inc`.
- Delete the whole GNU/OpusMake stack.

Recommend: leave for now, address in a separate cleanup.

---

## Phase 4 — Verification

1. Preprocessor sweep clean:
   ```
   grep -rE '__PSX__|__WIN__|_WIN32|__SATURN__|__DOS__|RENDERER_PSX|RENDERER_SOFTWARE|RENDERER_DIRECTX|RENDERER_XWINDOWS|RENDERER_PIPELINE_(PSX|SOFTWARE|DIRECTX)|SCALAR_TYPE_FIXED' wfsource/source
   ```
   Expect zero hits (a handful of string-literal or comment mentions may be fine to leave). **Note:** `__LINUX__` is NOT in this regex — those guards are expected to remain.

2. Build: `bash wftools/wf_engine/build_game.sh` exits 0.

3. Smoke tests:
   - `task run` — game launches against `wfsource/source/game/cd.iff`.
   - `task run-level -- wflevels/<some-level>.iff` — level loads and renders. Test a few levels; renderer-pipeline `#include` collapses in `rendobj3.cc` / `material.cc` / `viewport.cc` / `display.cc` are the highest-risk runtime breakage spot.

---

## Execution order summary

```
Phase 1 (deletes)  →  verify build_game.sh still builds  →
Phase 2 (unifdef sweep, per-subsystem commits, build after each)  →
Phase 3 (SKIP pruning, empty-on-Linux deletes)  →
Phase 4 (grep + build + runtime smoke test)
```

## Final report — exact line counts reduced

When the branch is complete, produce a categorized summary of lines removed (measured against the merge-base with `master`, e.g. `git diff --stat $(git merge-base HEAD master)..HEAD`). Report:

**By category**
- Dead rendering pipelines (`gfx/psx`, `gfx/softwarepipeline`, `gfx/directx`, `gfx/directxpipeline`, `gfx/xwindows`, `gfx/gl/wgl.cc`, `gfx/gl/unused.cc`)
- PSX & Win subsystems (`audio/psx`, `audio/win`, `hal/psx`, `hal/win`, `math/psx`, `math/win`, `movie/psx`, `pigsys/psx`, `pigsys/cf_psx.*`, `pigsys/cf_win.*`)
- `#ifdef` guard strippage in kept files (gfx, game, pigsys, cpplib, hal, streams, savegame, math, anim, profile, movement)
- build_game.sh SKIP pruning + empty-on-Linux file deletes

**For each category, report**
- Lines deleted, lines added, net delta
- File count (deleted / modified)

**Summary line:** total net LOC removed across the whole branch, plus total file count touched. Include a one-line sanity check that the Phase 4 verification grep returns zero.

---

## What is NOT deleted or changed

- `wfsource/source/gfx/gl/` — active Mesa/GLX renderer (minus `wgl.cc`, `unused.cc`)
- `wfsource/source/gfx/glpipeline/` — active GL pipeline
- All shared gfx/game code (`camera`, `material`, `rendobj3`, `game/*`, etc.) — kept, with non-Linux guards stripped
- **All `__LINUX__` and `#if !defined(__LINUX__)` guards** — preserved as porting documentation
- `pigsys/pigsys.hp` `MachineType` enum — values kept; only code that branches on them goes away
- `wftools/wf_viewer/` — standalone, independent of engine renderer
- GNU / OpusMake makefiles — not the active build; leave alone (or address in a follow-up)

---

## Final report (2026-04-14)

Measured against merge-base `71727ab` on branch `2026-first-working-gap`, scope restricted to `wfsource/` and excluding unrelated OAS additions that landed on the same branch.

Baseline: 132,257 C/C++ LOC in `wfsource/source/` at merge-base. Percentages below are relative to that baseline.

**By category**

| Category | Files | Insertions | Deletions | Net | % of baseline |
|---|---:|---:|---:|---:|---:|
| Dead rendering pipelines (`gfx/{psx,softwarepipeline,directx,directxpipeline,xwindows}`, `gfx/gl/{wgl,unused}.cc`) | 74 | 0 | 22,990 | −22,990 | −17.4% |
| PSX & Win subsystems (`audio/{psx,win}`, `hal/{psx,win}`, `math/{psx,win}`, `movie/psx`, `pigsys/psx`, `pigsys/cf_{psx,win}.*`) | 57 | 0 | 8,870 | −8,870 | −6.7% |
| `#ifdef` strippage in kept files (Phase 2 unifdef + Phase 3a compound-guard hand-edits + Phase 4 cosmetic scrub) | ~124 | 32 | 3,933 | −3,901 | −2.9% |
| Phase 3c empty-on-Linux deletes (13 `.cc` shells, 6 empty `.hp`/`.hpi`/`.h`) | 19 | 0 | ~380 | −380 | −0.3% |

**Per-subsystem (Phase 2+3+4 only, top hitters — % of that subsystem's baseline)**

- `gfx/` −24,244 in 108 files (−76.1% of 31,847; includes pipeline deletes)
- `hal/` −4,020 in 32 files (−42.1% of 9,557)
- `pigsys/` −2,414 in 30 files (−42.6% of 5,671)
- `math/` −2,795 in 28 files (−27.1% of 10,305; SCALAR_TYPE_FIXED preserved by design)
- `game/` −327 in 10 files (−2.5% of 13,154)

**Summary line:** 264 files changed, +32/−36,170, **net −36,138 LOC (−27.3% of wfsource/source)** removed on the renderer-drop path.

**Phase 4 grep gate:** `grep -rE '__PSX__|__WIN__|_WIN32|__SATURN__|__DOS__|RENDERER_{PSX,SOFTWARE,DIRECTX,XWINDOWS}|RENDERER_PIPELINE_{PSX,SOFTWARE,DIRECTX}|SCALAR_TYPE_FIXED' wfsource/source` returns only expected hits: `SCALAR_TYPE_FIXED` branches (retained per Phase 3b), `profile/profile.txt` (a note file), and `audiofmt/sox.cc` (vendored — `defined(unix)` is always true on Linux). **Zero leaks.**

**SKIP pruning (Phase 3):** Of the six candidates the plan flagged (`gfx/otable.cc`, `cpplib/afftform.cc`, `math/{matrix3t,quat,tables}.cc`, `hal/dfoff.cc`), five remain genuinely broken for reasons unrelated to platform guards (missing headers, ambiguous operators, unqualified `std::` names). `hal/dfoff.cc` compiles, but its SKIP entry is a deliberate choice over `dfhd.cc` (conflicting `HalInitFileSubsystem`). `SKIP` left unchanged.

**Runtime smoke:** `task run` launches snowgoons and renders. Keyboard input is broken — pre-existing TCL→Lua migration gap, unrelated to this sweep; tracked as a follow-up against the Lua-vendor plan.
