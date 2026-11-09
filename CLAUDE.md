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
task build-wf-edit       # native collaborative editor (ASan; build-editor/)
task build-wf-edit-fast  # native editor, no ASan (build-editor-fast/) — for collab/RAM
task build-web-edit      # editor → WASM/WebGL2 (build-web-edit/); needs `task dev-setup-web-edit` once
task serve-web-edit      # serve the web editor at http://localhost:8081/wf-edit.html
task md -- <file>        # render Markdown
```

## Conventions

- Scripting language in level files: **zForth** (`WF_FORTH_ENGINE=zforth`). Never use Lua/WASM/other engines in new level scripts.
- All new `.sh` scripts: `set -euo pipefail` at the top.
- Blender addon lives in `wftools/wf_blender/`. Python files there are checked by py-syntax hook.
- Level source files: `.lev` (text) → `.lvl` (binary via levcomp-rs) → `.iff` (via iffcomp-rs).
- `cd.iff` is the asset bundle; all assets loaded via `HALGetAssetAccessor()`, never from raw file paths.
- Mesh actors that rest on a surface: author the **base (lowest vertex) at local z=0**, not centered — both placement and scale (mailboxes 3040-3042) pivot on the origin, so a centered mesh sinks/grows through the floor. See `docs/level-building.md` "Mesh origin". Exception: spheres / vertically-symmetric props.

## Containers

Builds, tests and engine runs happen in containers, never on the host. The one entry point is `scripts/in-linux-container.sh` (repo at `/src`, `build-docker/` at `/build`, memory capped, core dumps off); pick the image with `WF_CONTAINER_IMAGE`.

| `WF_CONTAINER_IMAGE` | Image (Dockerfile) | Base | Use it for |
|---|---|---|---|
| `linux-test` (default) | `wf-linux-test:local` ([`docker/Dockerfile.linux-test`](docker/Dockerfile.linux-test), `task linux-test-image`) | Ubuntu 24.04 | the C++ toolchain, ctest, pytest; **running `wf_game` headless** under `xvfb-run` with Mesa llvmpipe (precedent: `scripts/planted-cycle-desktop-run.sh`). Build the engine inside it (`scripts/build-wf-game-container.sh`); the host-built `engine/wf_game` doesn't run there (glibc) |
| `blender` | `wf-blender:local` ([`docker/Dockerfile.blender`](docker/Dockerfile.blender), `task blender-image`) | Ubuntu 26.04, the host's Blender | `blender --background` level generation (`wflevels/*/build.sh`), Cycles renders for reviews. No GL: use CPU Cycles, not Workbench/EEVEE |
| `blender` + `WF_BLENDER_DOCKERFILE=Dockerfile.blender.public` | same, from bare `ubuntu:26.04` ([`docker/Dockerfile.blender.public`](docker/Dockerfile.blender.public), `task blender-image-public`) | Ubuntu 26.04 | CI and builds outside the lab |

`linux-test` is still on 24.04 while the host and the Blender image are on 26.04 (resolute).

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
