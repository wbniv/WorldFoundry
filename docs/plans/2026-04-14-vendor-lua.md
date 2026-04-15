# Plan: Vendor Lua 5.4 and statically link it into wf_game

**Date:** 2026-04-14
**Status:** **landed 2026-04-14.** `wftools/vendor/lua-5.4.8/` is in tree;
`build_game.sh` compiles the Lua TUs directly; `wf_game` no longer links
`-llua5.4`. Post-2026-04-15, the Lua plug is the file-scope `lua_engine`
namespace in `scripting_stub.cc`, called by `ScriptRouter` — see
`docs/plans/2026-04-15-lua-engine-fixes.md` for the convention.

## Context

WF's Linux build currently relies on the system `lua5.4` package (`-llua5.4` in `wftools/wf_engine/build_game.sh`). This has two problems flagged in both the mobile-port plan and the scripting-languages doc:

1. **No mobile story.** Mobile platforms (and any non-Debian-family Linux) don't ship a `liblua5.4.so` on the system, so the mobile port must vendor it anyway.
2. **Platform drift.** The system package can be any minor version (5.4.x); different dev boxes compile against different headers silently.

The user's request: vendor Lua's source, compile it into `wf_game` directly, drop the system dependency. "With #define" — compile the Lua sources with the correct `LUA_USE_*` macro for our platform (Lua's standard vendoring pattern, see its own `Makefile`).

Intended outcome: `build_game.sh` no longer needs `liblua5.4-dev` installed. The Linux build produces a larger `wf_game` (~200 KB Lua statically linked) with zero system Lua dependency. Every other platform benefits from the same code path.

## Critical files

| File | Change |
|------|--------|
| `wftools/vendor/lua-5.4.8/` | **New** — upstream tarball; record SHA256 in `wftools/vendor/README.md` |
| `wftools/vendor/README.md` | Add Lua entry |
| `wftools/wf_engine/build_game.sh` | Drop `-llua5.4`; drop system Lua `-I`; add compile of `wftools/vendor/lua-5.4.8/src/*.c` (minus `lua.c`/`luac.c` — those are the interpreter and compiler `main`s, not library TUs); add `-DLUA_USE_POSIX -DLUA_USE_DLOPEN`; add `-ldl` |
| `wftools/wf_viewer/stubs/scripting_stub.cc` | Update `#include <lua5.4/lua.h>` → `#include <lua.h>` (three such lines) |

## Approach

1. **Pick Lua version.** Lua 5.4.8 (latest 5.4.x stable as of 2026-04). Match-or-newer to the `liblua5.4-dev` headers we were linking against so we don't silently downgrade.
2. **Download + extract** from `https://www.lua.org/ftp/lua-5.4.8.tar.gz`. Record SHA256 `4f18ddae154e793e46eeab727c59ef1c0c0c2b744e7b94219710d76f530629ae`. Keep upstream layout: `src/` contains all the C files.
3. **Identify the TU set.** Lua's library = all `.c` files in `src/` **except** `lua.c` (interpreter `main`) and `luac.c` (bytecode compiler `main`). 32 TUs: `lapi lauxlib lbaselib lcode lcorolib lctype ldblib ldebug ldo ldump lfunc lgc linit liolib llex lmathlib lmem loadlib lobject lopcodes loslib lparser lstate lstring lstrlib ltable ltablib ltm lundump lutf8lib lvm lzio`.
4. **Compile flags.**
   - `-DLUA_USE_POSIX -DLUA_USE_DLOPEN` — gives `require()`/`dlopen()` support without pulling in `readline` (which is only used by Lua's standalone REPL, which we don't build).
   - Link flags: add `-ldl` (for `dlopen`) and keep `-lm`. Drop `-llua5.4`.
5. **Header include path.** Add `-I"$VENDOR/lua-5.4.8/src"` to CXXFLAGS. Update `scripting_stub.cc`'s `#include <lua5.4/...>` → `#include <...>` (three lines: `lua.h`, `lualib.h`, `lauxlib.h`).
6. **Compile the Lua `.c` files** in `build_game.sh` with `gcc` (Lua is C). Lua's headers are `extern "C"`-wrapped so the C++ TUs link fine.
7. **Verify:**
   - `build_game.sh` succeeds.
   - snowgoons runs — Fennel, Lua scripts, every existing test behaves identically.
   - `ldd wf_game` does **not** list `liblua5.4.so`.
   - `size wf_game` delta vs. pre-change binary is ~+180-220 KB.
8. **Documentation.** Update `docs/scripting-languages.md` — Lua row's Runtime column from `-llua5.4 (system) → to-vendor` to `vendored wftools/vendor/lua-5.4.8/, statically linked`. Remove `liblua5.4-dev` from `docs/dev-setup.md` if present.

## Verification

1. **No system Lua at link time.** `grep lua5.4 wftools/wf_engine/build_game.sh` returns nothing.
2. **No system Lua at runtime.** `ldd wftools/wf_engine/wf_game | grep lua` is empty.
3. **Snowgoons parity.** Full play-through matches pre-change behaviour. Lua error messages readable; Fennel's embedded Lua eval still works.
4. **Size delta recorded** in the commit message so `docs/scripting-languages.md`'s size column stays honest.

## Out of scope

- Upgrading to Lua 5.5 or LuaJIT (different plan; API surface changes).
- Retiring any Lua C-API users. The API is unchanged — only the provenance of the library changes.
- Linting Lua source: we use upstream verbatim.
