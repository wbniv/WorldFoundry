# Vendored third-party sources

Checked-in mirrors of third-party libraries that get statically linked into the
engine. The CD / embedded target has no runtime filesystem, so everything ships
as source and is linked in at build time.

## Contents

| Directory | Version | License | Upstream |
|-----------|---------|---------|----------|
| `quickjs-v0.14.0/` | 0.14.0 (2025-04-13) | MIT | https://bellard.org/quickjs/ |
| `jerryscript-v3.0.0/` | 3.0.0 | Apache-2.0 | https://github.com/jerryscript-project/jerryscript/releases/tag/v3.0.0 |
| `wasm3-v0.5.0/` | 0.5.0 | MIT | https://github.com/wasm3/wasm3/releases/tag/v0.5.0 |
| `lua-5.4.8/` | 5.4.8 | MIT | https://www.lua.org/ftp/lua-5.4.8.tar.gz |

## Tarball SHA256

- `jerryscript-v3.0.0.tar.gz` — `4d586d922ba575d95482693a45169ebe6cb539c4b5a0d256a6651a39e47bf0fc` (upstream GitHub tarball)
- `wasm3-v0.5.0.tar.gz` — `b778dd72ee2251f4fe9e2666ee3fe1c26f06f517c3ffce572416db067546536c` (upstream GitHub tarball)
- `lua-5.4.8.tar.gz` — `4f18ddae154e793e46eeab727c59ef1c0c0c2b744e7b94219710d76f530629ae` (upstream www.lua.org tarball)

## Notes

- Optional. Only one JS engine (or none) links into a given build. Selection
  happens in `wftools/wf_engine/build_game.sh` via `WF_JS_ENGINE`.
- Optional. Only one wasm engine (or none) links into a given build. Selection
  happens in `wftools/wf_engine/build_game.sh` via `WF_WASM_ENGINE`.
- See `docs/plans/2026-04-14-pluggable-scripting-engine.md` for the JS dispatch
  contract and the JerryScript `wf-minimal` profile, and
  `docs/plans/2026-04-14-wasm3-scripting-engine.md` for the wasm3 plan.
