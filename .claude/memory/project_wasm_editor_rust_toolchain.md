---
name: project_wasm_editor_rust_toolchain
description: "WASM wf-edit build needs an isolated rustup 1.85.1 + wasm target + a yrs submodule patch; distro rust can't do it."
metadata: 
  node_type: memory
  type: project
  originSessionId: 47cbad87-4933-4a9c-b7a5-10f189a51d27
---

Building the browser/WASM editor (`wf_edit_web`, see [[project_world_foundry]] and
docs/plans/2026-06-12-wf-edit-in-the-browser.md) requires a Rust setup distinct from the
native editor build. Established 2026-06-12 during Phase 0.

**Why:** the native build uses the **distro** rust at `/usr/bin/rustc` (1.85.1, sysroot
`/usr/lib/rust-1.85`) — it is **not rustup-managed**, has only the host std, and can't
cross-compile to wasm. Corrosion's vendored `FindRust.cmake` has no Emscripten branch and
**silently falls back to the host triple** under `emcmake`.

**How to apply:**
- `task dev-setup-web-edit` provisions everything idempotently. It installs **rustup isolated**
  (`--no-modify-path` — global toolchain untouched, distro rust stays default), pins toolchain
  **1.85.1** (must match the distro rustc the native build is known-good with against vendored
  yrs 0.26 — newer stables drift), and adds `wasm32-unknown-emscripten`.
- The web build must use the **rustup** cargo (`~/.cargo/bin`), not `/usr/bin`: export
  `PATH="$HOME/.cargo/bin:$PATH"` + `RUSTUP_TOOLCHAIN=1.85.1`, and pass CMake
  `-DRust_CARGO_TARGET=wasm32-unknown-emscripten` so Corrosion cross-compiles instead of
  defaulting to host.
- `wftools/y-crdt` is an **upstream submodule** (remote `y-crdt/y-crdt`, can't push). yrs gates
  `undo::Options::default()` on `not(target_family="wasm")`, which wrongly excludes emscripten
  (its dep `SystemClock` IS present there). Fix ships as a tracked patch
  `docs/patches/yrs-0.26-undo-options-default-emscripten.patch`, applied by `dev-setup-web-edit`
  (NOT committed into the submodule — that would orphan the pointer). Patching the submodule
  leaves it showing ` m wftools/y-crdt` in parent `git status` — expected, don't "clean" it.
- Source `engine/vendor/emsdk-6.0.0/emsdk_env.sh` for emcc. Proven: yrs→yffi→libyrs.a→wfcrdt
  C++ wrapper cross-compiles and runs under node (14/14 wrapper tests).
