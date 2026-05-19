# Snowgoons crash chase — `RenderObject3D::Render` past-end read + side-effect-assert past-end write

**Date:** 2026-05-19
**Status:** FIXED — fix landed in commit `<sha>` (to be filled at commit time).
**TL;DR:** Two long-standing bugs in [`gfx/glpipeline/rendobj3.cc`](../../wfsource/source/gfx/glpipeline/rendobj3.cc) — (1) wrong `&&` short-circuit order at line 83 reads `_faceList[_faceCount].materialIndex` (past-end) before the bounds check, and (2) line 101 was `assert(_faceList[_faceCount].materialIndex = -1)` — single `=`, an assignment that writes -1 past the end of the static `cubeFaceList[12]` (with asserts enabled). Surfaced today by running the snowgoons level under the CMake-built `wf_host_gl_e2e_test` harness; manifested as a SIGSEGV inside `DrainDoneSounds` reading a non-canonical `0xffff000000000000` from `sDoneHead`. The makefile-build of `wf_game` happened to mask the SIGSEGV (different defines / different downstream memory layout) but was still doing the past-end write.

## Premise

Yesterday's host-GL plan flagged "multi-cycle snowgoons crashes in both wf_game and harness" as a follow-up. The plan's smoke tests covered qbert_practice only.

## Reproducing

```bash
# CMake-built harness on snowgoons (cycles=2 — the originally-suspect case):
DISPLAY=:0 ./cmake-build-linux/wf_host_gl_e2e_test \
    --cycles=2 \
    --level=wflevels/snowgoons-blender/snowgoons-standalone.iff
# Pre-fix: SIGSEGV at frame ~2, in DrainDoneSounds().
```

Confusing initial signal: the makefile-built `engine/wf_game` exited 0 on `--cycles=2/5` against snowgoons. Same source tree. Different build systems.

## Build-system divergence (red herring path, ~30 min)

| | `task build` (`engine/build_game.sh`) | `cmake --build cmake-build-linux` |
|---|---|---|
| Optimization | `-O0 -g` | `-O0` (no `CMAKE_BUILD_TYPE`) |
| `NDEBUG` | NOT defined → `assert()`s active | defined via `target_compile_definitions(Jolt PUBLIC NDEBUG)` from yesterday's Jolt ODR fix → `assert()`s compiled out |
| `DESIGNER_CHEATS` | defined | not defined |
| `DO_TEST_CODE` | `=1` | `=0` |
| Engines enabled | zforth + lua54 only | all defaults (fennel, quickjs, wamr, wren, zforth, lua54) |

The NDEBUG difference turned out to be the key — but counter-intuitively: makefile-build has asserts ON, which means `assert(x = -1)` AT LINE 101 DOES WRITE `-1` past the end of `cubeFaceList[12]`. That write happens to land on benign padding/alignment in the makefile-build's static layout. cmake-build with asserts OFF skips that write entirely — but the *read* at line 83 still happens, and reads garbage that hits memory layouts further downstream.

## The actual bug — caught by ASan + UBSan

Re-ran the harness with `-DWF_ASAN=ON`. After suppressing a separate `new-delete-type-mismatch` (a `IteratorWrapper<BaseObject, BaseObjectIterator>` non-virtual-dtor-through-base — orthogonal, see [TODO follow-up](../../TODO.md)), ASan flagged:

```
==88114==ERROR: AddressSanitizer: global-buffer-overflow on address 0x58725086b136
READ of size 2 at 0x58725086b136 thread T0
    #0 RenderObject3D::Render(ViewPort&, Matrix34 const&) [glpipeline/rendobj3.cc]
    #1 RenderCamera::RenderObject(RenderObject3D&, Matrix34 const&)
    #2 RenderActor3D::Render(RenderCamera&, PhysicalObject const&, Clock const&)
    #3 Camera::Render(Actor&, Clock const&)
    #4 Level::RenderScene()
    #5 WFGame::StepFrame(bool, Scalar*)
0x58725086b136 is located 6 bytes after global variable 'cubeFaceList'
    defined in 'wfsource/source/renderassets/rendacto.cc:147:16' (0x58725086b040) of size 240
```

`cubeFaceList` is a `static TriFace cubeFaceList[12]` (240 = 12 × `sizeof(TriFace)`=20). ASan's flagged read is at offset +246, which is offset 6 within the past-end TriFace — exactly where `materialIndex` lives.

### Bug A — short-circuit order at line 83

[`gfx/glpipeline/rendobj3.cc:83`](../../wfsource/source/gfx/glpipeline/rendobj3.cc):

```cpp
while(currentMaterial == globalRendererVariables.currentRenderFace->materialIndex
      && faceIndex<_faceCount)
```

Inner-loop iteration N=`_faceCount-1`: body runs, then `faceIndex++` → `_faceCount`, `currentRenderFace++` → `&_faceList[_faceCount]` (one past end). C++'s `&&` evaluates the **left** operand first → reads `_faceList[_faceCount].materialIndex` (past-end) before noticing `faceIndex<_faceCount` is false. ASan catches the read.

Fix: swap operands so the bounds check runs first.

### Bug B — single `=` in assert at line 101

```cpp
assert(_faceList[_faceCount].materialIndex = -1);  // single = !
```

A typo from way back. With asserts enabled (`task build` / no NDEBUG), this WRITES -1 to past-end memory each frame. With NDEBUG (cmake build), the whole expression is compiled out (assertion macro becomes `((void)0)`). The author probably meant `assert(_faceList[_faceCount].materialIndex == -1)` — a sentinel check — but neither the assertion nor the sentinel exists anywhere else, so the line had no real purpose. Deleted.

## Why dormant

The for-loop at line 71 (`for(int faceIndex=0; faceIndex<_faceCount; )`) controls the OUTER iteration but the inner `while` increments `faceIndex` itself. On the last inner iteration the inner-while reads one past the end via the left operand of `&&`. Standard C++ would order this correctly in defensive code as `while(idx<n && something(arr[idx]))`. The author wrote it the other way, by hand-rolled material-batching style, and it worked in practice because:

- Reading 2 bytes past a `static const`-ish array is silent on most platforms unless the page boundary lands in the wrong spot or a sanitizer is checking.
- The assert's past-end write landed in a static-layout slot the engine happened not to read again. Specific to the makefile-build's static-data layout.

The CMake build's NDEBUG-disabled asserts + different engine set (extra translation units = different .bss/.data layout) shifted the static layout so the past-end read landed near `static std::atomic<PlayInstance*> sDoneHead` in [`audio/linux/buffer.cc`](../../wfsource/source/audio/linux/buffer.cc). Garbage read into the loop condition occasionally — depending on what else was running on the page — flowed downstream into `sDoneHead`'s memory location via miniaudio's `on_sound_end` callback handler which dereferences `(char*)pSound - offsetof(PlayInstance, snd)`. With `sDoneHead = 0xffff000000000000` (non-canonical address), `DrainDoneSounds`'s `list->next` read crashed.

That's the "Snowgoons crashes in multi-cycle" report that wasn't multi-cycle at all — it was a frame-2 single-cycle crash in the cmake build that was misattributed to the multi-cycle path.

## Fix

[`gfx/glpipeline/rendobj3.cc`](../../wfsource/source/gfx/glpipeline/rendobj3.cc):

```diff
-        while(currentMaterial == globalRendererVariables.currentRenderFace->materialIndex && faceIndex<_faceCount)
+        while(faceIndex<_faceCount && currentMaterial == globalRendererVariables.currentRenderFace->materialIndex)
```

```diff
-    assert(_faceList[_faceCount].materialIndex = -1);
 //    cout << "RenderObject3D::Render: done" << std::endl;
 }
```

## Verification

```bash
cmake --build cmake-build-linux -j
cd cmake-build-linux && ctest --output-on-failure -R cycle
# Pre-fix: wf_host_gl_e2e_snow_cycle1 + _snow_cycle2 SEGV.
# Post-fix:
#   wf_game_smoke_cycle1 / cycle2 / snow_cycle1 / snow_cycle2 ............. PASS
#   wf_host_gl_e2e_cycle1 / cycle2 / snow_cycle1 / snow_cycle2 ............ PASS
# 8/8 in ~23 s.
```

## Open follow-ups

These ASan/UBSan findings are in scope for a separate sweep, NOT this fix:

- `IteratorWrapper<BaseObject, BaseObjectIterator>` deletes through base pointer without a virtual destructor — `Room::ListIter` → `ActiveRooms::InitActiveRoom`. ASan "new-delete-type-mismatch" — size 8 (parent) vs 32 (concrete `BaseObjectIteratorFromInt16List`).
- Dozens of misaligned-access UBSan warnings throughout the HAL pool allocators (`lmalloc.cc`, `dmalloc.cc`, `mempool.cc`, plus `WFGame`, `Actor`, `Room` ctors on those pools). Engine custom allocators don't round to 8-byte alignment for the C++ types they hand out. Probably benign on x86 but a Real Bug for SSE / `std::atomic` consumers.
- `IteratorWrapper` issue and the alignment issues likely contributed to historical "weird crashes on Linux Release" but never with a clear repro before. ASan run was 7 m wall-clock to build + 12 s to run — cheap enough to wire as a periodic full-game soak target if needed.

## Related

- Yesterday's [host-gl e2e plan](../plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) noted "multi-cycle snowgoons crashes" — that was this bug, mis-bucketed as multi-cycle.
- Catalogue entry in [docs/BUGS.md](../BUGS.md).
