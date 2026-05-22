# Plan: Promote `DO_CD_IFF` to a togglable build flag

## Context

`DO_CD_IFF` is the toggle that distinguishes "engine loads its asset bundle
from `cd.iff` via `DiskTOC`" from "engine loads a single level file directly
via the `-L<path>` dev bypass." Today it's a file-local `#define` at
`wfsource/source/game/game.cc:26` — has been since the 2010 first git commit;
git history shows no earlier build-flag form, so if it was a Makefile flag in
the pre-2010 SourceForge CVS era, that's beyond `git log`'s reach.

Two things motivate promoting it now:

1. **Semantics of the disktoc.cc assert.** The earlier (2026-05-10) fix for
   the `ValidPtr(_toc)` crash gated the assert with `#if defined(DO_CD_IFF)`
   on the explicit user direction "assert() if CD_IFF." That gate is
   currently *inert* in `disktoc.cc` because the macro isn't visible across
   translation units. The gate's intent — "this assert is only meaningful in
   builds that committed to cd.iff loading" — can only be honored if
   `DO_CD_IFF` is visible build-wide.
2. **Distinct build modes.** With a togglable flag, two configurations are
   possible from one source tree:
   - **Cd.iff build (DO_CD_IFF on):** game loads `cd.iff` at startup;
     `_gameTOC.LoadTOC` runs; `~DiskTOC()`'s assert correctly enforces that
     LoadTOC ran. `-L<path>` is unsupported / not the design.
   - **Non-cd.iff build (DO_CD_IFF off):** game requires `-L<path>` to point
     at a level file; no `cd.iff` open; `_gameTOC._toc` stays NULL by design;
     the assert is compiled out; the null-guard handles the destructor.

The current qbert/snowgoons dev workflow runs entirely under `-L`, so a
non-cd.iff build mode is the right home for that work going forward.

Intended outcome: a one-source, two-binary world. `task build` keeps building
the cd.iff binary by default (matches today's behavior). A `WF_CD_IFF=0`
override produces a -L-only dev binary where the assert is silent. The
`disktoc.cc` gate stops being decorative and starts doing real work.

## Current uses of `DO_CD_IFF`

- `wfsource/source/game/game.cc:26` — the `#define`.
- `wfsource/source/game/game.cc:85, 106, 165, 222, 238` — five `#if
  defined(DO_CD_IFF)` blocks gating cd.iff file open, close, header load,
  level lookup.
- `wfsource/source/iff/disktoc.cc:46` — the gated destructor assert from the
  earlier fix.

No other code references the macro.

## Change

### 1. Remove the file-local `#define`

`wfsource/source/game/game.cc:26`:

```diff
-// if defined, loads meta-script (and all levels) from cd.iff, otherwise, loads level1.iff
-#define DO_CD_IFF
-
+// DO_CD_IFF is a build-wide flag (see engine/build_game.sh and CMakeLists.txt).
+// When defined, the engine loads its meta-script and all levels from cd.iff
+// via DiskTOC; otherwise it requires `-L<path>` to point at a level file
+// directly. Build with WF_CD_IFF=0 ./engine/build_game.sh to produce a
+// non-cd.iff binary.
 //#define DO_PROFILE
```

### 2. Add a togglable build flag in `engine/build_game.sh`

Near the existing `WF_*` env-var defaults (around line 38 for
`WF_ENABLE_WREN`, line 81 for `WF_LUA_ENGINE`):

```bash
WF_CD_IFF="${WF_CD_IFF:-1}"
```

Then in the base CXXFLAGS block (currently lines 127–136, where
`-DBUILDMODE_DEBUG` and friends are appended), append a conditional:

```bash
if [[ "$WF_CD_IFF" == "1" ]]; then
    CXXFLAGS+=(-DDO_CD_IFF)
fi
```

Validate the value alongside the other engine-choice validators
(`build_game.sh:86-89` style):

```bash
case "$WF_CD_IFF" in
    0|1) ;;
    *) echo "error: WF_CD_IFF must be 0 or 1 (got: '$WF_CD_IFF')" >&2; exit 1 ;;
esac
```

### 3. Mirror in CMake

`CMakeLists.txt:65-69` (the `WF_DEFS` list):

```diff
 list(APPEND WF_DEFS
     BUILDMODE_DEBUG DO_ASSERTIONS=1 DO_DEBUGGING_INFO=1
     DO_IOSTREAMS=1 SW_DBSTREAM=1 DEBUG=1 DEBUG_VARIABLES=1
     DO_VALIDATION=0 DO_TEST_CODE=0 DO_DEBUG_FILE_SYSTEM=0
 )
+
+set(WF_CD_IFF ON CACHE BOOL "Build the cd.iff loader path; off = -L<path> only")
+if(WF_CD_IFF)
+    list(APPEND WF_DEFS DO_CD_IFF)
+endif()
```

### 4. Update `disktoc.cc:39-50` comment

The earlier "this assert compiles out here; marker for if/when the macro is
promoted" comment is now stale — the macro *is* promoted. Replace with:

```cpp
DiskTOC::~DiskTOC()
{
    // _toc is NULL when LoadTOC was never called — happens in non-cd.iff
    // builds (-DDO_CD_IFF off / WF_CD_IFF=0) where -L<path> is the only
    // entry point. In cd.iff builds, LoadTOC must have run by the time we
    // destruct, so a NULL _toc is a bug worth catching.
#if defined(DO_CD_IFF)
    assert(ValidPtr(_toc));
#endif
    if (_toc) {
        HALLmalloc.Free(_toc);
    }
}
```

### 5. Documentation touch-ups

- `docs/compile-time-switches.md:87` — change "Defined in `game/game.cc:26`"
  to "Build flag in `engine/build_game.sh` / `CMakeLists.txt`; defaults on".
- `docs/level-building.md:666` — update the `#### DO_CD_IFF` section to
  reference the build flag, not the file-local define.
- `docs/reference/2026-04-14-compile-time-switches.md:402` — update the
  `DO_CD_IFF` table row's "Where" column from `source/game/game.cc` to the
  build files.
- `docs/reference/wf-viewer.md:24, 116` — change "in game.cc" to "via
  `WF_CD_IFF=0`".

## Files Touched

- `wfsource/source/game/game.cc` — remove `#define`, update top comment.
- `engine/build_game.sh` — add `WF_CD_IFF` env default + validator + conditional `-DDO_CD_IFF` append.
- `CMakeLists.txt` — add `WF_CD_IFF` cache option + conditional `WF_DEFS` append.
- `wfsource/source/iff/disktoc.cc` — refresh the comment above the assert (the assert itself stays).
- `docs/compile-time-switches.md`, `docs/level-building.md`,
  `docs/reference/2026-04-14-compile-time-switches.md`,
  `docs/reference/wf-viewer.md` — point at the build flag instead of the
  file-local define.

## Files Deliberately Not Touched

- `Taskfile.yml` — `task build` keeps its current defaults (no env change),
  which means it still builds the cd.iff binary (just via the build flag
  now). Wiring `task qbert` / `task run-level` / `task snowgoons` to set
  `WF_CD_IFF=0` before invoking the engine is a *follow-up* concern: each of
  those tasks today only *runs* a prebuilt binary, doesn't rebuild. Whether
  they should rebuild-on-demand, or rely on the user to run
  `WF_CD_IFF=0 task build` once, is a workflow question best resolved in a
  separate plan after this lands.
- Pre-2010 CVS history forensics — out of scope; the user asked what
  happened, and the answer is "git import in 2010 started life with the
  file-local `#define`." Pre-2010 form (if any) doesn't change today's plan.

## Behavioral Consequences (post-landing)

1. Default `task build`: behaves exactly as today — cd.iff binary, `-L`
   still works at runtime but `~DiskTOC()` assert fires on clean shutdown
   under `-L`. **This is now the *intended* semantics** ("you built the
   cd.iff binary; `-L` is unsupported"), not a bug.
2. `WF_CD_IFF=0 task build`: produces a -L-only binary. `_gameFile = nullptr`
   at startup. `-L<path>` is mandatory. `~DiskTOC()` exits cleanly because
   the assert is compiled out and the null-guard takes the NULL path.
3. CMake mirrors the same behavior via `-DWF_CD_IFF=OFF`.
4. Mobile (Android/iOS) builds are unaffected — `WF_DEFS` already contains
   the right things for those targets; this just adds `DO_CD_IFF` to the
   already-on baseline.

## Verification

1. **Default cd.iff build matches today:**
   - `task build` — succeeds.
   - `objdump -d engine/wf_game | grep -c "cd.iff"` — at least one match
     (the `ConstructDiskFile("cd.iff", ...)` literal at `game.cc:89`).
   - Run with a level that has cd.iff present (or accept the cd.iff-open
     failure on stderr — that's the existing pre-condition, not regression).
2. **Non-cd.iff build skips cd.iff path:**
   - `WF_CD_IFF=0 task build` — succeeds.
   - `objdump -d engine/wf_game | grep -c "cd.iff"` — zero matches
     (literal compiled out by the `#if defined(DO_CD_IFF)` block).
   - `engine/wf_game -Lwflevels/qbert_practice-standalone.iff` — boots,
     runs, **exits cleanly with no assert** (the exact failure mode that
     started this thread, now correctly silenced because the assert is
     compiled out under `WF_CD_IFF=0`).
3. **Validator rejects bad values:**
   - `WF_CD_IFF=2 task build` — fails fast with the validator message,
     same shape as the existing `WF_LUA_ENGINE` validator at
     `build_game.sh:86-89`.
4. **CMake parity:**
   - `cmake -S . -B cmake-build-linux -DCMAKE_BUILD_TYPE=Debug -DWF_CD_IFF=OFF
     && cmake --build cmake-build-linux -j` — succeeds, same behavior as
     `WF_CD_IFF=0` under build_game.sh.

## Open Question (deferred to follow-up plan)

How `task qbert` / `task run-level` / `task snowgoons` / `task run-debug`
should produce the right binary. Three viable shapes:

(a) Each `-L`-using task rebuilds with `WF_CD_IFF=0` before running.
(b) A new `task build-dev` produces the `-L` binary; users invoke it once,
    then `task qbert` etc. reuses it.
(c) Default `task build` flips to `WF_CD_IFF=0` since the current dev
    workflow is exclusively `-L`; users who want the cd.iff binary
    explicitly set `WF_CD_IFF=1`.

Not part of this plan — landing the build-flag promotion is mechanical and
self-contained. Workflow wiring is a separate decision once the flag exists.
