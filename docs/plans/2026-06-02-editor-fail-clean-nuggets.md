# Plan — Fix 5 "fail-clean" nuggets from the editor-codebase review

## Context

A review of the editor/dev codebase (prompted by a `rest_api.cc` comment that
*documented* a `std::terminate` hazard next to code that didn't prevent it)
surfaced a recurring **pattern**: code that aborts via `terminate()` / Rust
`panic` / a swallowed throw instead of failing with a legible diagnostic. The
debug-bridge thread-terminate was one instance, fixed + verified in
[`15801ebc`](https://github.com/wbniv/WorldFoundry/commit/15801ebc). This plan
fixes the remaining five — all the same "fail clean, not violently" spirit.

All five use **policy-agnostic** idioms (no-throw parses / asserts / a
non-poisoning mutex), so they're correct regardless of the exceptions decision
recorded below.

## The five fixes

1. **[HIGH] `SpawnActor` terminate()s on un-spawnable template classes.** Spawning a
   Room/Tool/StatPlat template hard-aborts in the OAS-generated constructor
   (`wfsource/source/oas/objects.c`) instead of failing cleanly. Added a class-kind
   pre-check in `wfmut::SpawnActor` (`engine/mutation/wfmut.cpp`): probe
   `Level::FindTemplateObjectData(idx)->objectData->type` and `failopt<>` for
   `Actor::Room_KIND` / `Tool_KIND` / `StatPlat_KIND` before `ConstructTemplateObject`.
   One guard covers every caller (the bridge observer + `RunSpawnConfirmTest`).
2. **[HIGH] CRDT nested write-txn → NULL → yffi panic across the FFI.** A nested
   `doc.begin()` made `Transaction::raw()` (`engine/crdt/wfcrdt.cpp`) return `nullptr`,
   which flowed into yffi and panicked in Rust with no context. Now: if a valid Doc
   still yields no txn, `fprintf` the real cause + `abort()` at the call site.
3. **[HIGH] `rest_api.cc` `std::stof` → no-throw `strtof`.** `std::stof` throws on a
   malformed REST body and aborts in the exception-free stub. Replaced with a
   `strtof` + endptr check (NaN on failure) — the lingering instance of the
   [2026-05-30 exceptions audit](../investigations/2026-05-30-cpp-exceptions-audit.md)
   fix that landed in `debug_server.cc` but was missed here.
4. **[HIGH] Relay `Mutex` poison → whole-relay crash.** One panicking handler
   poisoned the rooms `std::sync::Mutex`, so every later `.lock().unwrap()` panicked
   and dropped all rooms (a DoS). Swapped to `parking_lot::Mutex` (no poison; all
   lock sites are synchronous) and dropped the `.unwrap()`s. Same fix area: startup
   `.expect()`s (port/bind/snapshot-dir) now `eprintln!` a reason + `exit(1)` instead
   of panicking. `wftools/wf_collab/{Cargo.toml,src/bin/relay.rs}`.
5. **[MED] WebRTC `catch (...) {}` swallows all signaling errors silently.**
   `WebrtcSession::OnSignal` (`engine/wf_edit/webrtc_session.cc`) now logs the dropped
   malformed signal (`catch (const std::exception&)` + a `catch(...)` fallback)
   instead of silence, so signaling failures are debuggable.

## Exceptions policy (decided: status quo)

The build map: `-fno-exceptions` is applied **only** to `wfengine`/`wf_game` on
**Release+Clang** (CMakeLists.txt:706/772, a code-size optimization). `wf-edit`,
`wf_game-dev`, and all Debug/GCC builds have exceptions **on**, and the editor/dev
code is `#ifdef`-gated *out* of the shipped lean build. So exceptions are already
allowed where the editor actually runs. Decision (user): **no build refactor** —
fix 1-5 with the no-throw idioms; keep exceptions in pure-host UI (`engine/wf_edit`);
keep the no-throw discipline in the engine-straddling stubs (they inherit `wfengine`'s
flags). The policy is recorded in the
[exceptions audit](../investigations/2026-05-30-cpp-exceptions-audit.md). The escape
hatch, if it ever chafes: lift the bridge/dev stubs into a host-only `-fexceptions`
static lib (small CMake refactor; deferred).

## Verification

- **Build:** `cargo build` the relay (#4 ✓); `task build-editor` for `wf_game-dev`
  (#1/#2/#3, re-runs `wfcrdt_wrapper_test` + `connect_retry_test`); `task build-wf-edit-fast`
  for `wf-edit` (#5).
- **#1:** via the bridge, attempt to spawn a Room/StatPlat template → clean
  `lastError()` ("not runtime-spawnable") instead of terminate; a normal template
  still spawns.
- **#2:** open a write txn, attempt a nested `doc.begin()` → the clear abort message,
  not a raw yffi panic.
- **#3:** a REST body with a malformed numeric returns the default (no abort).
- **#4:** `wf-relay --port nope` / a port-in-use prints a reason + exits 1; a
  panicking handler no longer cascades (parking_lot has no poison).
- **#5:** a malformed signal logs `webrtc: dropped malformed signal: …`.
- Commit by area (C++ bridge/crdt/stubs together; the Rust relay separately; the
  webrtc log with the editor build). Re-run editor ctests for no regression.

## Status — DONE (2026-06-02)

All five fixed and committed: [`19e95a86`](https://github.com/wbniv/WorldFoundry/commit/19e95a86)
(C++ #1/#2/#3/#5 + docs), [`e6e031c3`](https://github.com/wbniv/WorldFoundry/commit/e6e031c3)
(relay #4), [`c4eceaa1`](https://github.com/wbniv/WorldFoundry/commit/c4eceaa1) (`Cargo.lock`).
Predecessor: the debug-bridge terminate fix
[`15801ebc`](https://github.com/wbniv/WorldFoundry/commit/15801ebc). ~1 h.

**Verified:**
- Builds clean: `wf_game-dev` (#1/#2/#3), `wf-edit` (#5), `cargo` relay (#4).
- No regression: `wfcrdt_wrapper_test` 14/14, `connect_retry_test` 6/6.
- **#3** behavioural: a malformed-float REST body (`"x":"notanumber"`) creates the box
  and the process stays alive (pre-fix `std::stof` threw → abort).
- **#4** behavioural: `wf-relay --port nope` and a bind-permission error both print
  `[relay] error: …` + exit instead of a panic backtrace.
- **#1 / #2 / #5** are compile-verified + correct-by-construction (a pre-check returning
  `failopt` before the terminating call / an abort-with-cause guard / a logged catch).

**Deferred → [TODO.md](../../TODO.md):**
- **#1** behavioural test: there's no bridge spawn op, and `RunSpawnConfirmTest` was parked
  *because* spawning terminate'd — now that the guard makes it safe, un-deferring it into a
  real spawn regression test pairs with the deeper engine-side fix (make
  `ConstructTemplateObject` return NULL on *any* unmet prerequisite, covering all kinds).
- The exceptions **host-only dev-lib** refactor (escape hatch), per the
  [exceptions audit](../investigations/2026-05-30-cpp-exceptions-audit.md) § Policy decision.
