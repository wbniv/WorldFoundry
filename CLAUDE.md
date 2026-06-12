# WorldFoundry-wbniv

> Project-specific conventions. Shared conventions cascade from `~/SRC/CLAUDE.md`.

## Stack

| Layer | Technology |
|-------|-----------|
| Engine | C++17 / CMake |
| Scripting | Forth (zForth) — `WF_FORTH_ENGINE=zforth` |
| Tools | Rust (iffcomp-rs, levcomp-rs, textile-rs, chargrab-rs) |
| Physics | Jolt |
| Graphics | OpenGL (Linux/Android), Metal (iOS) |
| Blender addon | Python (`wftools/wf_blender/`) |
| CI/CD | Codemagic (iOS), GitHub Actions |
| Build | Taskfile + CMake |

## Key Commands

```
task build               # CMake build (Linux)
task build-cmake-android # Android NDK build
task build-apk           # Android APK
task md -- <file>        # render Markdown
```

## Conventions

- Scripting language in level files: **zForth** (`WF_FORTH_ENGINE=zforth`). Never use Lua/WASM/other engines in new level scripts.
- All new `.sh` scripts: `set -euo pipefail` at the top.
- Blender addon lives in `wftools/wf_blender/`. Python files there are checked by py-syntax hook.
- Level source files: `.lev` (text) → `.lvl` (binary via levcomp-rs) → `.iff` (via iffcomp-rs).
- `cd.iff` is the asset bundle; all assets loaded via `HALGetAssetAccessor()`, never from raw file paths.
- Mesh actors that rest on a surface: author the **base (lowest vertex) at local z=0**, not centered — both placement and scale (mailboxes 3040-3042) pivot on the origin, so a centered mesh sinks/grows through the floor. See `docs/level-building.md` "Mesh origin". Exception: spheres / vertically-symmetric props.

## Coordinate Systems

### World Foundry (WF)

| Axis | Direction |
|------|-----------|
| X | right (screen-right in side-view) |
| Y | depth (into screen in side-view) |
| Z | up |

### Blender

Same orientation: Blender X=right, Y=depth, Z=up. The `bl_to_wf()` exporter function is an identity transform.

Euler angles map 1:1: `rotation_euler[0,1,2]` → WF Euler `a,b,c` with no additional rotation.

### WF Euler angles

The three angles are `a` (pitch / X-rot), `b` (roll / Y-rot), `c` (heading / Z-rot).

**`currentDir()` formula** (`wfsource/source/physics/physicalobject.hpi:52`):

```
currentDir() = (cos C, sin C, 0)
```

> The comment in `movement.cc:698` says `(sin C, cos C, 0)` — that comment is **wrong**. The implementation is authoritative.

| C value | currentDir | faces |
|---------|-----------|-------|
| 0 | (1, 0, 0) | +X (screen-right) |
| π/2 | (0, 1, 0) | +Y (into depth / away from camera) |

**StepRight** (doom-stick, TurnRate=0) = `(sin C, −cos C, 0)`.

| C | StepLeft | StepRight |
|---|----------|-----------|
| 0 | (0, +1, 0) = toward camera | (0, −1, 0) = away from camera |
| π/2 | (−1, 0, 0) = screen-left | (+1, 0, 0) = screen-right ✓ |

### Side-scroller recipe

Camera at Y=−20 looking toward +Y. Set player `rotation_euler.z = math.pi / 2` (WF Euler C=π/2) in the Blender script. This gives:

- `currentDir` = +Y (player faces into the scene, away from camera)
- LEFT joystick → kBtnStepLeft → −X (screen-left) ✓
- RIGHT joystick → kBtnStepRight → +X (screen-right) ✓
