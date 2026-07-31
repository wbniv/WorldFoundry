# Plan: Build Jolt physics on iOS (remove the forced legacy-physics fallback)

## Context

iOS is the **only** WorldFoundry target still on legacy physics. This is not an
iOS limitation and not a Jolt limitation — Jolt 5.5.0 officially supports iOS
ARM64 (NEON/FP16, `engine/vendor/jolt-physics-5.5.0/README.md`). It's a CMake
**generator** quirk:

- iOS configures with `-G Xcode` (`codemagic.yaml:130`); Linux/macOS/Android use
  Ninja/Make.
- The engine modifies the vendored `Jolt` target after creating it:
  `target_compile_options(Jolt …)` and `target_compile_definitions(Jolt …)`
  (`CMakeLists.txt:512,528`). Under `-G Xcode` these error with *"Cannot specify
  compile options for target 'Jolt' which is not built by this project"* because
  Jolt's own cmake deliberately avoids global per-target flags under Xcode
  (multi-arch builds — `Jolt/Jolt.cmake:637-638`).
- The current workaround force-flips iOS to legacy physics
  (`CMakeLists.txt:497-500`).

**Why now:** legacy `physics/wf/` is slated for deletion. The force-legacy block
selects the `else()` branch that depends on `physics/wf/` sources
(`CMakeLists.txt:530-531`); once those are deleted, the iOS build would select a
backend that no longer exists and break. **This fix is a hard prerequisite for
the legacy-physics deletion.** (That deletion stays separately gated on Jolt
parity on a second level — it is *not* part of this plan.)

**Outcome:** iOS keeps the Xcode generator (preserving the planned Phase-4
`ios-device-release` signed-IPA path, `codemagic.yaml:6`) **and** builds Jolt,
via a generator-safe mechanism. All platforms share one code path.

## Root-cause fix: per-source-file properties instead of `target_*(Jolt …)`

Apply Jolt's build modifiers through `set_source_files_properties` on Jolt's own
source list (`JOLT_PHYSICS_SRC_FILES`, populated by the included fragment and
still in scope after `include()`), instead of mutating a target the project
doesn't own. Source-file properties are honored by **every** generator including
Xcode (it writes per-file build settings), and stay scoped to Jolt's TUs only —
no leak onto `wfengine`/`wf_game` (which keep Debug `-O0 -g`). This is an
established pattern in this file (pforth `CMakeLists.txt:465`, wfmut `:584`).

What each modifier needs (verified):

| Modifier | Verdict |
|---|---|
| `NDEBUG` | **Load-bearing.** Jolt auto-defines `NDEBUG` only in Release configs (`Jolt.cmake:515`); in Debug, Jolt TUs would build without it while wfengine TUs (NDEBUG via `WF_DEFS`, `CMakeLists.txt:507`) build with it → ODR mismatch around `JPH_ENABLE_ASSERTS`/`ConstraintManager` → SIGTRAP in `BodyManager::Init`. Must reach Jolt's TUs on every generator. Consumer side already has NDEBUG via `WF_DEFS`, so per-file (not `PUBLIC`) is sufficient. |
| `-w` | Cosmetic (silence vendored warnings; engine already uses `-w`). |
| `-O2` | Perf-only — keep Jolt fast in Debug. Per-file scope means it does **not** displace wfengine/wf_game `-O0 -g`. |
| `-fno-rtti` | Size-only (Jolt uses its own RTTI macros, `Jolt/Core/RTTI.h`; no C++ rtti). |

### The edit — `CMakeLists.txt`

1. **Delete** the force-legacy comment + block (`:492-500`). iOS then keeps the
   cache default `WF_PHYSICS_ENGINE=jolt` (`:29`) and takes the jolt branch.

2. **Replace** the two `target_*(Jolt …)` calls (`:510-528`) with:

```cmake
    include(${JOLT_DIR}/Jolt/Jolt.cmake)   # populates JOLT_PHYSICS_SRC_FILES, add_library(Jolt ...)

    # Apply Jolt's build modifiers via SOURCE-FILE properties, not
    # target_compile_*(Jolt ...). Under -G Xcode + iOS the target_* form errors
    # ("...target 'Jolt' which is not built by this project") because Jolt's cmake
    # avoids global per-target flags under Xcode (Jolt.cmake:637). Source-file
    # properties work on every generator and stay scoped to Jolt's TUs — no leak
    # onto wfengine/wf_game (Debug -O0 -g).
    #
    # NDEBUG is LOAD-BEARING: Jolt.cmake only auto-defines it in Release configs,
    # so in Debug Jolt's TUs would build without it while wfengine's TUs (NDEBUG
    # via WF_DEFS) build with it — an ODR mismatch (JPH_ENABLE_ASSERTS /
    # ConstraintManager) that SIGTRAPs in BodyManager::Init. Consumers already
    # get NDEBUG from WF_DEFS, so per-file (vs PUBLIC) suffices.
    # -O2: keep Jolt fast in Debug. -w: silence vendored warnings.
    # -fno-rtti: Jolt uses its own RTTI macros, no C++ rtti.
    set_source_files_properties(${JOLT_PHYSICS_SRC_FILES} PROPERTIES
        COMPILE_DEFINITIONS "NDEBUG"
        COMPILE_OPTIONS     "-O2;-w;-fno-rtti"
    )
```

   Leave the `else()` legacy branch and the rest of the jolt branch
   (`WF_SOURCES`/`WF_INCLUDES`/`WF_DEFS`/`list(APPEND WF_LINK_LIBS Jolt)`)
   unchanged. The Linux/macOS/Android Jolt flags come out identical to today
   (`NDEBUG -O2 -w -fno-rtti`), so this is a no-op for them.

   Untouched: the separate Android/Linux Release `target_compile_options(Jolt …)`
   tweaks (`CMakeLists.txt:739-740`) only run under Ninja/Make, never Xcode —
   still valid.

### Why not the alternatives

- **Directory-scope `add_compile_definitions`/`add_compile_options` before the
  include:** works for reachability but leaks onto every later target. Harmless
  for `NDEBUG`/`-w`, but `-O2` would land on wfengine/wf_game (which want Debug
  `-O0 -g`) and rely on fragile flag-ordering to be overridden. Rejected.
- **Jolt cache vars (`USE_ASSERTS`):** the included fragment is lib-only; the
  rich `option()` set lives in Jolt's top-level CMakeLists (not included).
  Setting `USE_ASSERTS=OFF` wouldn't define `NDEBUG` on Jolt's TUs. Rejected.

## Alternative (documented, not recommended): switch iOS to Ninja

Configure iOS with `-G Ninja` like macOS; then the original `target_*(Jolt …)`
calls work and **no CMakeLists change is needed**. Requires `codemagic.yaml`
edits: `-G Ninja` (`:130`), build via `cmake --build` instead of `xcodebuild`
(`:142-149`), and update the `.app` path for `xcrun simctl install` to the
single-config Ninja layout (`$CM_BUILD_DIR/engine/wf_game.app` vs the Xcode
per-config `engine/Debug/…`, `:165`). **Tradeoff:** loses Codemagic's
Xcode-native code-signing automation that the planned signed-IPA workflow
(`codemagic.yaml:6`) and the staged `XCODE_ATTRIBUTE_CODE_SIGN_*` properties
(`CMakeLists.txt:891-893`) depend on — signing would become manual `codesign`/
`xcrun`. This is why the source-file-property fix (keeps Xcode) is preferred.

## Verification

1. **Linux gate (fast, primary):** `task build`. Then the e2e/cycle harness
   (`wf_host_gl_e2e_test`) — it's the test that originally tripped the NDEBUG
   SIGTRAP, so it's the most sensitive regression check.
2. **No flag drift:** in `cmake-build-linux/compile_commands.json`, confirm a
   Jolt TU (e.g. `BodyManager.cpp`) carries `-DNDEBUG -O2 -w -fno-rtti` and a
   wfengine TU still has `-O0 -g` (not displaced by `-O2`).
3. **iOS (only Codemagic can exercise the Xcode-generator failure):** a single
   targeted push to `2026-ios` runs `ios-simulator-debug` — configure must no
   longer error on the `Jolt` target, `xcodebuild` must link `libJolt.a` into
   `wf_game.app`, and the `xcrun simctl` screenshot/log step must still show the
   `viewDidLoad` NSLog signal. Mac minutes are metered — rely on the Linux gate
   for iteration and spend one Mac build to confirm. Triggering is currently
   manual.

## Critical files

- `CMakeLists.txt` — remove force-legacy `:492-500`; replace `target_*(Jolt …)`
  at `:510-528` with `set_source_files_properties(${JOLT_PHYSICS_SRC_FILES} …)`.
- `engine/vendor/jolt-physics-5.5.0/Jolt/Jolt.cmake` — reference only
  (`JOLT_PHYSICS_SRC_FILES`/`add_library` `:469`; NDEBUG `:515`; Xcode `:637`).
- `codemagic.yaml` — iOS verification workflow (not edited by recommended fix).
- `Taskfile.yml` — Linux verification gate (`build`, e2e/cycle).

## Notes

- Per the docs/plans convention, on approval I'll author the canonical plan doc
  at `docs/plans/2026-05-26-ios-jolt-physics-xcode-safe.md` and commit it with
  the CMake change.
- Scope is the iOS-Jolt fix only. Legacy `physics/wf/` deletion remains a
  separate, separately-gated task (Jolt parity on a second level).
