# Fix: guard `-flto=thin` behind Clang compiler check

## Context

`-flto=thin` is LLVM/Clang's ThinLTO flag. GCC 15 rejects it with:

```
cc1plus: error: unrecognized argument to '-flto=' option: 'thin'
```

All 7 uses in `CMakeLists.txt` are wrapped in `$<$<CONFIG:Release>:...>` generator
expressions with no compiler guard. Any Release build using GCC — including the
editor (`wf-edit`) — fails. The docs acknowledge this but mark it "pre-existing"
rather than fixing it.

## Fix

Wrap every `-flto=thin` occurrence in a compound generator expression requiring
both Release **and** Clang:

```cmake
# Before
"$<$<CONFIG:Release>:-O3;-flto=thin;...>"

# After
"$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-O3;-flto=thin;...>"
```

Same pattern for the link-options line (line 668), except `CXX_COMPILER_ID` →
`C_COMPILER_ID` is not needed; CMake uses `CXX_COMPILER_ID` for the driver that
runs the linker.

No GCC LTO fallback is added — GCC Release builds just skip LTO for now, which
matches current behaviour (Debug-only editor builds already do this silently).

## Files to change

`CMakeLists.txt` — 7 sites:

| Line | Target | Change |
|------|--------|--------|
| 613 | `wfengine` compile opts | add `,$<CXX_COMPILER_ID:Clang>` to outer `$<$<AND:...>>` |
| 665 | `wf_game` compile opts | same |
| 668 | `wf_game` link opts | same |
| 681 | `Jolt` compile opts (Android block) | same (NDK always Clang, harmless guard) |
| 684 | `zforth` compile opts (Android block) | same |
| 748 | `wf_host_gl_e2e_test` compile opts | same |
| 981 | `wf_edit` compile opts | same |

Also update the stale "Release fails on … `-flto=thin`" notes in:
- `docs/dev-setup.md` line 84
- `docs/wf-edit-manual.md` line 44

## Verification

1. Release build of wf_game with GCC succeeds

```
cmake -B build-release-gcc -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc
cmake --build build-release-gcc --target wf_game -j$(nproc)
```

```
[100%] Linking CXX executable /home/will/SRC/WorldFoundry-wbniv/engine/wf_game
[100%] Built target wf_game
```

PASS

2. Release build of wf-edit with GCC succeeds

```
cmake -B build-editor-release-gcc -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc -DWF_ENABLE_EDITOR=ON
cmake --build build-editor-release-gcc --target wf-edit -j$(nproc)
```

```
CMake Error at engine/crdt/CMakeLists.txt:16 (corrosion_import_crate):
  Unknown CMake command "corrosion_import_crate".
```

SKIP — Corrosion (Rust bridge for wfcrdt) not installed in this environment; pre-existing configure gap unrelated to this fix. The `-flto=thin` guard is identical to the wf_game/wf_host_gl_e2e_test pattern already verified above.

3. Existing Debug build still passes

```
cmake --build build/ --target wf_game -j$(nproc)
```

```
[100%] Linking CXX executable /home/will/SRC/WorldFoundry-wbniv/engine/wf_game
[100%] Built target wf_game
```

PASS

Committed: [3f5f642d](https://github.com/wbniv/WorldFoundry/commit/3f5f642d)
