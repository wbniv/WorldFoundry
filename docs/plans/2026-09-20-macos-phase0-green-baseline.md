# macOS Phase 0 — actually reaching a green headless baseline

**Status:** ✅ Done — Phase 0's exit criterion is green on Codemagic
(build `6aafcf69903254faf05d7835`, commit `18188fd1`). Live-debugged directly against Codemagic,
one real failure at a time. Continues [2026-09-20-macos-metal-renderer.md](2026-09-20-macos-metal-renderer.md)'s
Phase 0, which a prior agent pass left **BLOCKED — not run** for lack of a Codemagic API token.
That credential gap is closed (`task setup`, see `docs/SETUP.md`); this plan picks up exactly
where that left off and carries Phase 0 the rest of the way to green.

## Context

Once `task setup` supplied a working Codemagic token + app id, triggering
`macos-desktop-debug` on `2026-new-level` surfaced a sequence of **real, previously
unverified** build breaks — exactly what Phase 0 exists to find. Each was fixed and
re-verified against a fresh Codemagic run before moving to the next. No mockup bundle: this is
a headless CI build gate, no visible surface.

## Fixes landed, in the order Codemagic surfaced them

### 1. Missing Jolt-extraction step (`87cdf90d`)

`macos-desktop-debug`'s own `cache_paths` comment claimed the Jolt vendor tarball was
extracted and cached, but no such script step existed — `CMakeLists.txt:633`'s
`include(${JOLT_DIR}/Jolt/Jolt.cmake)` failed outright since `engine/vendor/jolt-physics-5.5.0/`
was never unpacked on the build machine. Added an "Extract Jolt vendor archive" step mirroring
iOS's existing one verbatim.

### 2. Jolt PCH vs `-fno-rtti` mismatch under every Clang family (`310e83ad`)

Jolt's own CMake unconditionally enables a precompiled header, but the project applies
`-fno-rtti` to Jolt's sources via `set_source_files_properties` (`CMakeLists.txt:661-663`) —
flags that don't propagate into the PCH compile. GCC silently tolerates the resulting
flag/PCH mismatch; every Clang family (upstream Clang, AppleClang) hard-errors:
`run-time type information was enabled in precompiled file ... but is currently disabled`.
A fix already existed for this — `set_target_properties(Jolt PROPERTIES
DISABLE_PRECOMPILE_HEADERS ON)` — but was scoped to `if(EMSCRIPTEN)` only. Broadened the guard
to `if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")`, which catches "Clang" and "AppleClang" alike
while leaving GCC (and thus the Linux build) untouched.

### 3. `codemagic-budget.sh` timestamp parsing (`5c366761`)

Side quest, surfaced by Will's "keep track of minutes" request while this was in flight: the
first *real* (non-stub) Codemagic API response used
`"...T10:18:27.746000+00:00"` — fractional seconds **and** a numeric UTC offset, a shape the
budget script's stub-API testing never exercised. Its `epoch` jq function only stripped the
fraction when followed by `Z`; broadened to strip the fraction unconditionally and normalize a
trailing `+00:00` to `Z`.

### 4. macOS scripting roster scoped to Forth-only (`30db733e`)

Will's call, mid-debug, on hitting the next failure (an AppleClang narrowing-conversion error
in the auto-generated `fennel_source.cc`, embedding Fennel's UTF-8 source as a `char[]`):
rather than patch that one symptom, scope macOS's scripting roster down to match
Android/iOS/Emscripten — zForth only. `WF_LUA_ENGINE=none`, `WF_ENABLE_FENNEL=OFF`,
`WF_JS_ENGINE=none`, `WF_ENABLE_WREN=OFF`, `WF_PILOT_ENGINE=none` added to the `elseif(APPLE)`
block. `WF_DEBUG_BRIDGE`/`WF_REST_API` left untouched — a separate, deliberately-enabled
desktop feature (`04061deb`) unrelated to which script languages compile.

Config-only, fully reversible, nothing deleted. The real root cause of the Fennel bug was
diagnosed anyway (for whenever it's re-enabled) and logged as a Parked TODO item:
`scripts/gen_fennel_source.sh`'s `sed` step rewrites `xxd -i`'s safe `unsigned char[]` output to
`char[]`, which is what Clang narrows-and-errors on for UTF-8 bytes ≥128. The actual generator
+ consumer fix (keep `unsigned char`, cast to `const char*` at the one `luaL_loadbuffer` call
site) was implemented in the same pass as a correctness fix, independent of whether macOS ships
it enabled.

### 5. Next, agreed with Will — REST API off, debug-bridge GL calls stubbed

The next build (with fixes 1–4 in place) got to 286/289 files before two more real breaks,
both in code that survived the Forth-only trim because `WF_REST_API`/`WF_DEBUG_BRIDGE` were
deliberately left on:

- `engine/stubs/rest_api.cc:15` — unconditional `#include <GL/gl.h>` (Linux/Mesa path; doesn't
  exist on macOS) used for **real legacy immediate-mode GL calls**
  (`glBegin`/`glVertex3f`/`glEnd`/`glPushAttrib`/`glDisable`/`glLineWidth`/`glColor4f`/`glPopAttrib`)
  drawing debug wireframe boxes — none of which are among the 6 symbols
  `hal/macos/gl_stubs.cc` already stubs for macOS's headless no-op GL layer. Fixing the header
  alone isn't enough; it would fail to *link* next.
- `engine/stubs/debug_server.cc:42-46` — same header problem (its `#ifdef __ANDROID__`/`#else`
  branch lumps macOS in with Linux's `GL/gl.h`), calling `glGetIntegerv`/`glPixelStorei`/
  `glReadPixels` for its screenshot feature — also not in the stubbed 6.

**Decision (Will, 2026-09-20):** disable `WF_REST_API` on macOS — it's explicitly labeled a PoC
in its own header comment, already off on every mobile platform, and its debug-draw code has no
window/render context to draw into on macOS today regardless. For the debug bridge — the
feature `04061deb` deliberately turned on for macOS — add the 3 missing no-op GL stubs
(`glGetIntegerv`, `glPixelStorei`, `glReadPixels`) to `hal/macos/gl_stubs.cc`, matching the
existing pattern (dead code today, real once the Metal renderer lands), rather than disabling
the bridge outright.

### 6. The arm64 array-cookie bug — `MEMORY_DELETE_ARRAY` freeing 8 bytes into the block

With fixes 1–5 in, the build went green and the binary ran: the whole level loaded, the
zForth scripts ran, Jolt optimised the broad phase, the audio and debug-bridge subsystems came
up — and then the engine died on its own heap guard.

```
[debug] listening on :7777
+- ASSERTION FAILED ----------------------------------------------------------+
|_cookie == ALLOCATED_COOKIE                                                  |
|in file "/Users/builder/clone/wfsource/source/memory/dmalloc.hpi" on line 148|
+-----------------------------------------------------------------------------+
```

A completely different class of problem from 1–5: not a build break, a **runtime memory
corruption** report from `DMalloc::AllocatedChunk::Validate()`. Not reproducible on Linux — the
same level, flags and command line run clean on x86_64/GCC, with and without ASan.

#### Getting a usable postmortem (`a5694c38`)

`expr/file/line` is worthless for an assert that lives in shared leaf code; every DMalloc
allocation in the engine reports the same three lines. So before guessing, the engine was
taught to say who called:

- `_sys_assert` now prints a `backtrace_symbols_fd()` dump before exiting. `<execinfo.h>` ships
  with both glibc and Darwin libSystem; Emscripten (non-fatal asserts) is guarded out.
- `DMalloc::AllocatedChunk` gained `HeaderLooksValid()`/`DumpHeader()`, and `DMalloc::Free`
  now names the pool, the bad chunk's offset within it, the relevant `sizeof`s and the whole
  free list. Failure path only — free on a healthy run.

One Codemagic run with that in place produced the answer outright:

```
DMalloc::Free: corrupt allocation header
  pool          = "Level DMalloc"
  pool range    = [0x458034420,0x45804cac0)  size = 100000
  freeing mem   = 0x458037630 (chunk 0x458037628, offset 12808 into pool)
  sizeof(FreeChunk) = 16, sizeof(AllocatedChunk) = 8, WF_POINTER_ALIGN = 8
  free[00] 0x4580376b0 size=32 end=0x4580376d0
  ...
DMalloc::AllocatedChunk @ 0x458037628: sizeof(AllocatedChunk)=8 _size=24 _cookie=0x00000000 (expected 0xdeadbeef)
  header+payload bytes [0..47]: 18 00 00 00 00 00 00 00 05 00 00 00 00 00 00 00 d8 76 03 58 04 00 00 00 ...
+- BACKTRACE (16 frames) ------------------------------------------------------+
1   wf_game   _ZNK7DMalloc14AllocatedChunk8ValidateEv
2   wf_game   _ZN7DMalloc4FreeEPKv
3   wf_game   _ZN4RoomD2Ev
5   wf_game   _ZN10LevelRoomsD2Ev
7   wf_game   _ZN5LevelD2Ev
10  wf_game   _ZN6WFGame11UnloadLevelEv
11  wf_game   _ZN6WFGame17SmokeRunFrameStepEii
```

#### Root cause

`Room::~Room` frees `_objectLists` with `MEMORY_DELETE_ARRAY`, whose implementation was

```c
long* count = ((long*)classptr)-1;   /* ← assumes an 8-byte array cookie */
...
(memory).Free(count);
```

`Room::Construct` allocated that array with `new (memory) Int16List[n]`. Because `Int16List`
has a non-trivial destructor, the compiler reserves a hidden **array cookie** in front of the
block, and the size of that cookie is **ABI-defined**:

| ABI | Targets | Cookie |
|---|---|---|
| generic Itanium C++ ABI | x86_64 Linux, x86_64 macOS | **8 bytes** — one `size_t` element count |
| ARM C++ ABI (IHI0041) | **every AArch64 target**: Apple arm64, Android arm64‑v8a, aarch64 Linux | **16 bytes** — two words, `{ element size, element count }` |

The hex dump is that ARM cookie, verbatim: `18 00 00 00 00 00 00 00` = **24** = `sizeof(Int16List)`,
then `05 00 00 00 00 00 00 00` = **5** = `_checkListEntries`, then the first `Int16List` at +16.
The arithmetic closes exactly against the free list:

```
real chunk header   0x458037620   _size = 16 + 5*24 = 136
user pointer        0x458037628   ← the 16-byte ARM cookie starts here
_objectLists        0x458037638
chunk end           0x4580376b0   == free[00] start ✓
MEMORY_DELETE_ARRAY passed  0x458037630   (8 bytes too high)
DMalloc::Free read header at 0x458037628  → _size=24, _cookie=0
```

So the macro handed `Free()` a pointer 8 bytes past the real allocation base, `Free()` read the
middle of the cookie as an allocation header, and the guard fired. Correct on x86_64 by
coincidence of the cookie size; wrong on **every** arm64 target.

This is a **dormant pre-2026 bug**, not a regression from this port: the macro is in the
2010‑05‑01 first commit (`a2784f6e`) and `memory.hp` carries a 1998–2003 copyright. Authored
1998–2003 → reachable only once the arm64 ports landed (2026‑04) → first hit on macOS,
2026‑09‑20. Full provenance, including why the mobile arm64 ports didn't surface it first, is
logged in [`docs/BUGS.md`](../BUGS.md) per that file's eligibility rule.

#### Fix (`18188fd1`)

Rejected: teaching `MEMORY_DELETE_ARRAY` the per-ABI cookie size. That bakes an ABI table into
a macro, and it would still be wrong for 32-bit ARM (two 4-byte words) and for any `T` with
`alignof(T) > 8` under Itanium, where the cookie grows to `alignof(T)`.

Taken: **remove the compiler from the arithmetic.** New `MEMORY_NEW_ARRAY` allocates raw from
the pool and placement-constructs each element, so the pointer handed out *is* the allocation
base on every ABI, and `MEMORY_DELETE_ARRAY` frees exactly what it was given. This is the same
trade `Array<T>::SetMax` already makes (`cpplib/array.hpi`, which hit the sibling of this bug
from the other direction — a *missing* cookie). Both call sites moved over:
`room.cc` (`Int16List[]`, per-level DMalloc) and `rooms.cc` (`Room[]`, HALLmalloc).

#### Regression guard

`memory/pooltest.cc` + `wf_game --memory-test` (ctest `memory_pool_arrays`, and run first in
the macOS Codemagic smoke step). It pins the invariant that makes the pair ABI-independent —
*the pointer `MEMORY_NEW_ARRAY` returns is the pool allocation base* — by spying on the pool's
`Allocate()`. That is checkable on any host, so **it fails on x86_64 too** if anyone
reintroduces `new (pool) T[n]`; it does not need an arm64 box to bite.

## What this plan does NOT cover

Actually building a Metal renderer (that's `2026-09-20-macos-metal-renderer.md`'s Phase 1+).
This plan is scoped to Phase 0's own exit criterion: a green headless `macos-desktop-debug`
run, nothing more.

## Verification

1. **Every fix above is verified against a real Codemagic `macos-desktop-debug` run**, not a
   local approximation (AppleClang-specific errors can't be reproduced with the GCC available
   locally) — each commit's build log is quoted inline above at the point it was diagnosed.

2. **Local regression check after every CMake/source change**: `task build` (Linux/GCC) stays
   green throughout, confirming no change scoped to `APPLE`/`Clang` leaks onto the Linux build.

```
$ task build
...
Built: /home/will/WorldFoundry-wbniv/engine/wf_game
```

**PASS** — re-run after fixes 2 and 4 above (the two that touch shared `CMakeLists.txt` logic
rather than macOS-only files); both times exit 0, target still links.

3. **Fix 5 (REST_API off / debug-bridge GL stubs)**: `macos-desktop-debug` run after landing.

```
$ python3 ~/.claude/skills/codemagic-build/codemagic.py build \
    --app-id 6aafa6886ab3f21cf431a6cb --workflow macos-desktop-debug --branch 2026-new-level
build 6aafc55534287724ed0de23e
    Extract Jolt vendor archive                        success
    Configure CMake for macOS desktop (arm64, Ninja)    success
    Build wf_game                                       success
    Run headless frame-step smoke                       failed
```

**PASS for fix 5** (compile + link are green; `Build wf_game` succeeds, and the binary runs far
enough to load the whole level and start the debug bridge). The `Run headless frame-step smoke`
red is a *different* defect — the runtime memory corruption diagnosed as fix 6 above — not a
regression of fix 5.

4. **Regression guard for fix 6 fails on the pre-fix code, on x86_64** — proving the guard does
   not need an arm64 box to bite. Done once, by temporarily restoring the
   `new (pool) Int16List[n]` form in `memory/pooltest.cc` behind a `-D` and rebuilding that TU:

```
$ engine/wf_game --memory-test
FAIL: pool array has a 8-byte hidden compiler array cookie — MEMORY_NEW_ARRAY returned
0x58b9923d8f18 but the pool allocated 0x58b9923d8f10. MEMORY_DELETE_ARRAY frees the pointer it
is given, so the block would be freed at the wrong offset (this is the arm64 crash).
DMalloc::Free: corrupt allocation header
  pool          = "PoolArrayTest"
  pool range    = [0x58b9923d8f08,0x58b9923e0c08)  size = 32000
  freeing mem   = 0x58b9923d8f18 (chunk 0x58b9923d8f10, offset 8 into pool)
+- ASSERTION FAILED ----------------------------------------------------------+
|_cookie == ALLOCATED_COOKIE                                                  |
+-----------------------------------------------------------------------------+
TEST-EXIT=255
```

**PASS** — the guard reproduces the macOS corruption signature locally and exits non-zero.

> That `-D` was **not kept**. A second compilation mode that no build ever selects is dead code
> that rots, and it needed a hand-written `-D` plus a manual TU rebuild, so it would never have
> been run again. It was also unnecessary: the thing it demonstrated is *measurable*. The test
> now allocates a `new (pool) CookieProbe[n]` unconditionally, measures the prefix against the
> same spy, and prints it — one code path, compiled and run in every build on every host, which
> puts the ABI's actual cookie size in the log of every CI run. Step 5 below shows it.

5. **Linux regression check after fix 6** — the allocator self-check and the full smoke, both on
   the canonical `task build` config (ASan on, Jolt, zForth, Lua/REST_API/debug-bridge on):

```
$ task build
BUILD-EXIT=0
Built: /home/will/WorldFoundry-wbniv/engine/wf_game

$ cd wfsource/source/game && wf_game --memory-test
memory pool-array test: this ABI's compiler array cookie = 8 bytes (8 = generic Itanium / x86_64, 16 = ARM C++ ABI / arm64)
memory pool-array test: 0 failure(s)
MEMTEST-EXIT=0

$ wf_game --frame-step-smoke=30 --cycles=1 -L .../snowgoons-standalone.iff
rest_api: listening on http://127.0.0.1:8765
[debug] listening on :7777
rest_api: server stopped
Tasker shutting down
SMOKE-EXIT=0
```

**PASS** — Linux unaffected; the same teardown path that crashes on arm64 still completes.

6. **Phase 0 exit criterion** (from the parent plan): `wf_game.app/Contents/MacOS/wf_game
   --frame-step-smoke=30 --cycles=1` exits 0 on the shipped headless backend.

```
$ python3 ~/.claude/skills/codemagic-build/codemagic.py build \
    --app-id 6aafa6886ab3f21cf431a6cb --workflow macos-desktop-debug --branch 2026-new-level
build 6aafcf69903254faf05d7835 (18188fd1)   status: finished
    Preparing build machine                            success
    Fetching app sources                               success
    Restoring cache                                    success
    Toolchain versions                                 success
    Extract Jolt vendor archive                        success
    Configure CMake for macOS desktop (arm64, Ninja)   success
    Build wf_game                                      success
    Run headless frame-step smoke                      success
    Publishing                                         success
    Cleaning up                                        success
```

`macos-smoke.log`, head — the arm64 allocator self-check, then the smoke's own startup:

```
wf_game v0.4.1, Built:Sep 20 2026,12:21:58 by kts
--memory-test
DMalloc of 402 not 8-byte aligned, rounding up
DMalloc of 404 not 8-byte aligned, rounding up
DMalloc of 406 not 8-byte aligned, rounding up
memory pool-array test: 0 failure(s)
```

…and tail — it now runs past the point that used to assert, all 30 frames and the
`UnloadLevel` teardown, exiting 0 (the smoke step uses `set -o pipefail`, so a non-zero
`wf_game` fails the step — which is exactly how the previous run went red):

```
jolt: OptimizeBroadPhase done (15 static bodies)
audio: MusicPlayer — soundfont not found: florestan-subset.sf2
audio: sfx[0..6] not found: wflevels/qbert_practice/sfx/*.wav
[debug] listening on :7777
```

**PASS.** (No `Tasker shutting down` line on macOS because `PIGSExit`'s printf is
`#if DO_TEST_CODE`, which CMake's `WF_DEFS` sets to 0 — Linux's `build_game.sh` sets it to 1.
Absence of that line is a build-config difference, not a truncated run.)

**Phase 0 is green.** `macos-desktop-debug` builds, links and runs the headless frame-step
smoke to completion on `mac_mini_m2` / AppleClang 21 / arm64.

7. **The ABI claim behind fix 6, measured on both hosts rather than cited.** After the
   `WF_POOLTEST_USE_OLD_ARRAY_NEW` switch was replaced by the always-on measurement, the same
   shipped binary reports the cookie size it actually observes. Build
   `6aafd50924494f8afe051661` (`41510bae`), `Run headless frame-step smoke: success`:

```
# x86_64 / GCC 15, local
memory pool-array test: this ABI's compiler array cookie = 8 bytes (8 = generic Itanium / x86_64, 16 = ARM C++ ABI / arm64)
memory pool-array test: 0 failure(s)

# arm64 / AppleClang 21, Codemagic mac_mini_m2
memory pool-array test: this ABI's compiler array cookie = 16 bytes (8 = generic Itanium / x86_64, 16 = ARM C++ ABI / arm64)
memory pool-array test: 0 failure(s)
```

**PASS** — 8 vs 16 on the same source, confirming the root cause by direct measurement rather
than by inference from the crash dump. Every future macOS CI log carries this line, so the
divergence stays visible instead of living only in a comment.
