# Host-GL end-to-end harness + UnloadLevel crash fix + cycle stability tests

**Status:** Done 2026-05-18 — ~5 h end-to-end. All five phases shipped; `task test-cycle` runs 4/4 green. Phase B uncovered a deeper chain of dormant LIFO bugs than the plan anticipated (six instead of three), plus a Jolt ODR violation across TUs that gated Phase C for ~1 h. Original "~half a day" estimate from `TODO.md:87` was off by ~10×; recalibrate.

**Commits:** `3094acf` (Phase A: platform.cc split), `254c1d4` (Phase B: six LIFO bugs + Array<T> allocator-misuse), `f174840` (Phase B.2: --cycles=N CLI flag), `622fd81` (Phase C: harness scaffolding), `7a9ff31` (Phase C: Jolt ODR fix — unblocks harness), `e5e3975` (Phase D: CTest + Taskfile registrations), `6a13cd6` (Phase E: doc sync — TODO.md, wf-status.md, this plan's Status).

## Context

[`TODO.md`](../../TODO.md):87 tracks an editor Phase 0b follow-up: an end-to-end host-GL-context integration test that constructs a real `WFGame` against a host-supplied GLX context, drives ~60 `StepFrame(false)` ticks, and `glXSwapBuffers` the host window. Today the smoke test at [`engine/wf_host_gl_test/`](../../engine/wf_host_gl_test/) only exercises the registry in isolation via a `mesa_stub.cc` shim — it never instantiates `WFGame` or links `libwfengine.a`.

The TODO claims the blocker is `game/main.cc` defining `main()` inside `libwfengine.a`. **That claim is wrong** — verified by direct inspection:

- Phase 0a (the `libwfengine.a` + thin `wf_game` shell split) is already done — [`CMakeLists.txt`](../../CMakeLists.txt):435–581 with a 2026-05-18 comment block describing the split.
- [`wfsource/source/game/main.cc`](../../wfsource/source/game/main.cc) defines `PIGSMain` (a plain C function), **not** `main()`. The actual Linux `main()` lives at [`wfsource/source/hal/linux/platform.cc`](../../wfsource/source/hal/linux/platform.cc):166 and is **already** in `WF_PLATFORM_SHELL_SOURCES`, i.e. already outside the library.

The real obstacle: [`hal/linux/platform.cc`](../../wfsource/source/hal/linux/platform.cc) bundles `main()` together with engine-needed helpers (`_PlatformSpecificInit`, `_PlatformSpecificUnInit`, `FatalError`, `FPEHandler`, `ParseWindowSwitches`, the `_halWindow*` globals). Because the *whole file* sits in `WF_PLATFORM_SHELL_SOURCES`, an external host harness linking only `libwfengine.a` would get unresolved-symbol errors for those helpers. A custom harness today has to either re-implement them or compile `platform.cc` itself — at which point the harness's own `main()` collides with the bundled one.

This plan splits the Linux platform file into two pieces, with the helpers moving INTO `libwfengine.a` and only `main()` staying in the shell. Mobile (Android / iOS) is deferred — the host-GL harness is desktop-only.

**Second problem — unload must stop crashing.** [`TODO.md`](../../TODO.md):56 tracks an LMalloc accounting assert that fires inside `UnloadLevel()`: `(_currentFree - fl->_size) == mem` at [`wfsource/source/memory/lmalloc.cc`](../../wfsource/source/memory/lmalloc.cc):308. Surfaced 2026-05-18 by `wf_game --frame-step-smoke=N -L<standalone.iff>`. The standalone `wf_game` historically never returned cleanly from `RunLevel` in practice (window close / SIGTERM killed the process before `UnloadLevel` ran), so the smoke harness is the first caller to exercise the full `LoadLevel → UnloadLevel` cycle in-process. The end-to-end test harness this plan adds will hit the same assert on its very first run — fixing it is a hard prerequisite for the harness to pass.

[`WFGame::UnloadLevel`](../../wfsource/source/game/game.cc) (game.cc:313–335) already encodes the correct top-level ordering (PageFlip×2 → RestApi/DebugServer/Music/Sfx stop → `delete Level` BEFORE `delete _gameMailboxes`). The bug is downstream inside `Level::~Level` ([`wfsource/source/game/level.cc`](../../wfsource/source/game/level.cc):636–699) — likely a free-order or size mismatch.

**Third problem — multi-cycle stability.** The editor will eventually need to load level A, unload, load level B. Surface this as a first-class gate now. Step 5b and Step 7 cover it via a `--cycles=N` CLI flag (on both `wf_game` and the harness) and CTest registrations.

## Approach

### Phase A — Split `hal/linux/platform.cc` (Steps 1–3) — commit `3094acf`

1. `git mv hal/linux/platform.cc hal/linux/platform_init.cc` (preserves blame for the bulk).
2. Delete `main()` (lines 165–187) from `platform_init.cc`.
3. Create `hal/linux/platform_main.cc` (new, ~30 lines) with just `main()` plus extern decls.
4. Update [`CMakeLists.txt`](../../CMakeLists.txt):455 — swap `platform.cc` → `platform_main.cc`. `platform_init.cc` gets picked up by the existing `hal/linux` glob.
5. Verify: `task build`, `task snowgoons`, symbol audit (`nm libwfengine.a | grep " T main$"` must be empty).
6. Commit.

### Phase B — Fix UnloadLevel LMalloc assert + `--cycles=N` CLI (Step 4) — commits `254c1d4`, `f174840`

1. Reproduce: `./build/wf_game --frame-step-smoke=10 -L wflevels/snowgoons-blender/snowgoons-standalone.iff`.
2. Diagnose using existing `DBSTREAM1(cprogress << ...)` markers in `Level::~Level`. LMalloc is a stack/bump allocator — `(_currentFree - fl->_size) == mem` means freeing out of LIFO order.
3. Suspects:
   - Scratch mailboxes: [`Level::~Level`](../../wfsource/source/game/level.cc):680 has a commented-out free with a "kts kludge since _actors doesn't get destructed yet" comment.
   - Actor array storage: `_actors` is iterated and freed individually but the backing storage may be freed by `Vector<Actor*>` destructor at a later LIFO-violating position.
4. Fix the root cause — reorder frees to restore LIFO, or move offender to `DMalloc`. Do NOT widen the assert.
5. Extend `WFGame::SmokeRunFrameStep(int frames)` → `SmokeRunFrameStep(int frames, int cycles = 1)`, wrap `LoadLevel → loop → UnloadLevel` in an outer cycles loop.
6. Add `--cycles=N` flag in [`game/main.cc`](../../wfsource/source/game/main.cc):172–308 (`ParseCommandLine`).
7. Verify: `./wf_game --frame-step-smoke=30 --cycles=2 -L <small-level>` exits 0.
8. Commit.

### Phase C — Host-GL e2e harness with multi-cycle (Steps 5 + 5b) — commits `622fd81` (scaffolding), `7a9ff31` (Jolt ODR fix)

Create `engine/wf_host_gl_test/host_gl_e2e_test.cc`:
1. Parse `--cycles=N` (default 2).
2. Open X11 Display + Window + GLX context (mirror existing smoke test).
3. `SetHostGLContext({dpy, win, ctx, true})`.
4. HALStart-equivalent setup (call `_PlatformSpecificInit` directly + open AssetAccessor + construct WFGame).
5. For each cycle: `LoadLevel(test_level)` → `StepFrame(false)×30` → `glXSwapBuffers` → `UnloadLevel`.
6. Destroy WFGame, `ClearHostGLContext`, tear down X11.

CMake target (gated `NOT ANDROID AND NOT IOS`):
```cmake
add_executable(wf_host_gl_e2e_test
    engine/wf_host_gl_test/host_gl_e2e_test.cc)
target_link_libraries(wf_host_gl_e2e_test PRIVATE wfengine)
target_compile_options(wf_host_gl_e2e_test PRIVATE -fpermissive -w)
```

Multi-cycle fragility checklist if cycle 2 crashes:
- Static singletons not reset by `UnloadLevel` (gMusicPlayer, SfxLibrary caches, debug-bridge gWatches/gMailboxPrev, REST-API server thread, mailbox storage).
- Asset-cache stale pointers — Forth dictionary capturing asset addresses.
- Mailbox watch state — per [`TODO`](../../TODO.md), already fragile.
- Jolt physics statics — `JoltRuntimeShutdown` is called by `~WFGame`, not `UnloadLevel`. Confirm `JoltBackendInit` is per-level.
- `_DiskFile` re-seek between cycles.

Commit.

### Phase D — Register tests + Taskfile target (Step 7) — commit `e5e3975`

CTest registrations in [`CMakeLists.txt`](../../CMakeLists.txt) (gated `NOT ANDROID AND NOT IOS`):
```cmake
enable_testing()

add_test(NAME wf_game_smoke_cycle1
    COMMAND $<TARGET_FILE:wf_game>
        --frame-step-smoke=30 --cycles=1
        -L ${CMAKE_SOURCE_DIR}/wflevels/qbert_practice/qbert_practice-standalone.iff)

add_test(NAME wf_game_smoke_cycle2
    COMMAND $<TARGET_FILE:wf_game>
        --frame-step-smoke=30 --cycles=2
        -L ${CMAKE_SOURCE_DIR}/wflevels/qbert_practice/qbert_practice-standalone.iff)

add_test(NAME wf_game_smoke_cycle5
    COMMAND $<TARGET_FILE:wf_game>
        --frame-step-smoke=20 --cycles=5
        -L ${CMAKE_SOURCE_DIR}/wflevels/qbert_practice/qbert_practice-standalone.iff)

add_test(NAME wf_host_gl_e2e_cycle1
    COMMAND $<TARGET_FILE:wf_host_gl_e2e_test> --cycles=1)

add_test(NAME wf_host_gl_e2e_cycle2
    COMMAND $<TARGET_FILE:wf_host_gl_e2e_test> --cycles=2)

set_tests_properties(wf_host_gl_e2e_cycle1 wf_host_gl_e2e_cycle2
    PROPERTIES LABELS "gl" ENVIRONMENT "DISPLAY=:0")
```

[`Taskfile.yml`](../../Taskfile.yml):
```yaml
test-cycle:
  desc: "Run Load/Unload cycle stability tests (CTest)"
  cmds:
    - cd build && ctest --output-on-failure -R "cycle"

test-cycle-headless:
  desc: "Cycle tests, skipping GL/X11 tests (CI-safe)"
  cmds:
    - cd build && ctest --output-on-failure -R "cycle" -LE gl
```

Rationale for cycle counts (1, 2, 5):
- `cycle1` — basic unload regression gate (Phase B fix).
- `cycle2` — "second-cycle uses stale static state" — most common multi-cycle bug.
- `cycle5` — slow accumulation (one-entry-per-cycle leaks).

Commit.

### Phase E — Documentation sync — commit `6a13cd6`

- Update [`TODO.md`](../../TODO.md):56 → DONE with root-cause + fix commit sha.
- Update [`TODO.md`](../../TODO.md):87 → DONE with retrospective (Phase 0a + main lift already done; real blockers were platform.cc bundling + LMalloc LIFO).
- Update [`docs/plans/2026-05-18-engine-external-gl-context.md`](2026-05-18-engine-external-gl-context.md) with new Step 8 entry and Status flip.
- Update `wf-status.md` row.
- Flip this plan's Status to Done.

Commit.

## Verification gates

```bash
# Gate 1 — Phase A: wf_game unchanged
task build
task snowgoons

# Gate 2 — Phase B: clean unload
./build/wf_game --frame-step-smoke=10 -L wflevels/qbert_practice/qbert_practice-standalone.iff; echo $?    # 0
./build/wf_game --frame-step-smoke=60 -L wflevels/snowgoons-blender/snowgoons-standalone.iff; echo $?     # 0
./build/wf_game --frame-step-smoke=30 --cycles=2 -L wflevels/qbert_practice/qbert_practice-standalone.iff; echo $?   # 0

# Gate 3 — Phase C: host-GL harness, single cycle
DISPLAY=:0 ./build/wf_host_gl_e2e_test --cycles=1; echo $?    # 0

# Gate 4 — Phase C: multi-cycle
DISPLAY=:0 ./build/wf_host_gl_e2e_test --cycles=2; echo $?    # 0
valgrind --leak-check=summary ./build/wf_host_gl_e2e_test --cycles=2 2>&1 | tail -20
# definitely-lost must equal --cycles=1 baseline

# Gate 5 — Phase D: CTest
task test-cycle    # ctest -R "cycle"
# 5 green: wf_game_smoke_cycle1/2/5 + wf_host_gl_e2e_cycle1/2
```

Symbol audit:
```bash
nm build/libwfengine.a 2>/dev/null | grep -E " T _Z21_PlatformSpecificInit"   # 1 match
nm build/libwfengine.a 2>/dev/null | grep -E " T main$"                        # 0
nm build/wf_game 2>/dev/null         | grep -E " T main$"                      # 1
nm build/wf_host_gl_e2e_test 2>/dev/null | grep -E " T main$"                  # 1
```

## Scope explicitly excluded

- Android `hal/android/native_app_entry.cc` + iOS `hal/ios/native_app_entry.mm` splits — deferred. TODO entry: "Editor Phase 0b mobile follow-up".
- Refactor of `game/main.cc` (`PIGSMain`) — already library-resident, harness doesn't need it.
- Lifting `_halWindow*` globals into a struct — separate cleanup, not a blocker.
- Rewriting `LMalloc` into a free-list allocator. Stack-discipline is load-bearing for fixed-pool semantics on real-target. Fix the caller-side LIFO violation; do not change the allocator.
