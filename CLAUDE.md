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
