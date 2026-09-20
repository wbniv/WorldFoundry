# macOS Phase 0 — actually reaching a green headless baseline

**Status:** In progress — live-debugged directly against Codemagic, one real build failure at a
time. Continues [2026-09-20-macos-metal-renderer.md](2026-09-20-macos-metal-renderer.md)'s
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

3. **Fix 5 (REST_API off / debug-bridge GL stubs)**: `macos-desktop-debug` run after landing —
   *(pending — implementing now)*

4. **Phase 0 exit criterion** (from the parent plan): `wf_game.app/Contents/MacOS/wf_game
   --frame-step-smoke=30 --cycles=1` exits 0 on the shipped headless backend — *(pending, blocked
   on step 3 above)*
