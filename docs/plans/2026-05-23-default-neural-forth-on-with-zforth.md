# Plan: Default WF_NEURAL_FORTH=ON when WF_FORTH_ENGINE=zforth

**Date:** 2026-05-23
**Status:** PARTIAL — CMake default flipped ON (verified); `engine/build_game.sh` neural-forth integration + `wf_game` symbol check remain.

## Context

Up to commit `9c91f83e` (build glue) and `86b11999` (scripting dispatch gate), `WF_NEURAL_FORTH` defaulted to OFF — meaning the engine and editor were compiled *without* the fuzzy-logic / NN / autograd C sources unless the developer explicitly passed `-DWF_NEURAL_FORTH=ON` to CMake or `WF_NEURAL_FORTH=1` to `build_game.sh`.

User request: flip this so it's automatically ON whenever `WF_FORTH_ENGINE=zforth` (which is the default). The fatal-error guard for non-zforth Forth engines stays — neural-forth is only valid when zforth is selected.

## Scope

Two build entry points need the change:

1. **CMake** (`CMakeLists.txt`) — already migrated to `cmake_dependent_option` in this session. Verified default flips to ON via `build/CMakeCache.txt`. Affects `wf_game`, `wf_edit`, `nf_test`, ASan editor builds.
2. **`engine/build_game.sh`** — the canonical engine build that `task build` invokes. Currently does not reference `WF_NEURAL_FORTH` at all. Needs to:
   - Read `WF_NEURAL_FORTH` env var; default `auto` (= ON for zforth, OFF otherwise).
   - When ON: define `-DWF_NEURAL_FORTH`, add `-I engine/neural-forth`, compile the six C sources (`dictionary.c`, `tensor.c`, `autograd.c`, `fuzzy.c`, `nn.c`, `slot.c`) and link them into `wf_game`.
   - When OFF or non-zforth: skip silently. `scripting_zforth.cc`'s `#ifdef WF_NEURAL_FORTH` guards already handle the absent-macro case.

## Editor

`wf_edit` is built by CMake only and links against `wfengine` (the static lib from `WF_SOURCES`). Because `WF_SOURCES` already picks up the neural-forth C sources when `WF_NEURAL_FORTH` is set (line 422 in CMakeLists.txt), and the new `cmake_dependent_option` flips that ON by default, **no editor-specific change is needed** — the editor inherits via the static lib.

## Files to change

- `CMakeLists.txt:20–28` — option → cmake_dependent_option. **Done in this session.**
- `engine/build_game.sh` — case statement at line 197–204 (CXXFLAGS), and a new compile-and-link block parallel to the zforth one near line 525. **Partially done; see below.**

## Verification

1. `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release` — confirm `WF_NEURAL_FORTH:BOOL=ON` in `build/CMakeCache.txt`. **PASS** (verified mid-session.)
2. `cd build-nf && ctest -R neural_forth_unit --output-on-failure` — confirm nf_test still passes.
3. `task build` — confirm `wf_game` links with `WF_NEURAL_FORTH` defined and the neural-forth C sources compiled in.
4. `nm engine/wf_game | grep -E 'nf_init|nf_dispatch'` — confirm the neural-forth symbols are present in the wf_game binary.
5. `cmake --build build --target wf_edit` — confirm `wf_edit` builds with the new default. (Note: there's a pre-existing `-flto=thin` flag in `wf_edit` target that gcc rejects; that's an *editor* CMake bug unrelated to this change, to address separately if it bites.)

## Out of scope

- Adding any *runtime* use of neural-forth in level scripts — that's a separate plan once the demos in `docs/investigations/2026-05-23-fuzzy-logic-visualization-gaps-v2.md` start.
- The `-flto=thin` editor build error is pre-existing and not addressed here.
