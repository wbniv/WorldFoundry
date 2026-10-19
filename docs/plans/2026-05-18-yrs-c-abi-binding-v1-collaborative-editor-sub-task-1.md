# Plan — Yrs C ABI binding (v1 collaborative editor, sub-task #1)

**Status:** DONE — submodule + `WF_ENABLE_CRDT` CMake integration landed; see parent [yrs C ABI binding](2026-05-18-yrs-c-abi-binding.md).
**Scope:** Yrs C ABI binding via cbindgen — the first v1 milestone after Phase 0b shipped.
**Estimate:** ~1 focused week (matches the [design doc estimate](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md)).

---

## Context

Phase 0b ([engine embed-readiness](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md)) shipped 2026-05-18 — `WFGame::StepFrame` / `LoadLevel` / `UnloadLevel`, externally-supplied GL context, input injection, de-globaled `WFGame`. The engine is now drop-in linkable into a host process (`libwfengine.a`). The collaborative-editor v1 work item list opens with **Yrs C ABI binding via cbindgen** — the binding that the IFF↔Y.Doc translator, the WebSocket relay (Rust, lives separately), and the direct-read engine bridge all depend on.

The decision driving this plan's shape: **editor owns the Y.Doc; engine exposes a plain C++ mutation API.** Editor observes Yrs ops and translates them into engine API calls. The engine stays Rust-free — `libwfengine.a`, `wf_game`, Android APK, iOS .app, and Codemagic CI builds all unaffected.

The mutation API is not deferred design uncertainty — it's a **planned project deliverable** that this binding's split-shape forces into existence early, on purpose. Concrete consumers waiting on it:

- **Collaborative editor** (v1 direct-read bridge) — the immediate consumer.
- **DAP / step debugger** (per [project_followup_dap_phase_c](../../.claude/projects/-home-will-WorldFoundry/memory/project_followup_dap_phase_c.md) and [project_followup_lua_remote_debugger](../../.claude/projects/-home-will-WorldFoundry/memory/project_followup_lua_remote_debugger.md)) — explicit user-requested follow-ups; the debug bridge needs to read + mutate the same scene state the editor does.
- **Journal / replay UI** (v2 line item in the design doc) — same mutation surface, driven by a recorded event stream instead of live CRDT ops.
- **Headless test harness** — the SMB walkthrough log uses scripted button injection today; a real mutation API enables direct scene assertions instead of screenshot diffs.

Calling these "speculative future requirements" was wrong on my part during planning — they're the design doc's [editor + debugger convergence](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) direction, time-deferred but explicitly committed. Building the API once, well, as a first-class engine artifact serves all of them.

Secondary benefits (consequences, not drivers):
- Shipped game binaries (iOS, Android, `wf_game`) don't carry dead Rust code (~1–3 MB of yffi).
- Engine ABI stays stable C++ — no Yrs version churn touching the engine.
- "Fresh clone, `task build`, run `wf_game`" onboarding stays single-toolchain.
- Codemagic 500 min/mo budget protected.

---

## Architectural shape

```
libwfengine.a   ← engine. No Yrs. No Rust dep. Unchanged.
libwfcrdt.a     ← yffi + thin C++ wrapper. ONLY this needs Rust.
wf_editor       ← (future) links libwfengine.a + libwfcrdt.a + ImGui.
wf_game         ← links libwfengine.a only. Unchanged.
Android APK     ← links libwfengine.a only. Unchanged.
iOS .app        ← links libwfengine.a only. Unchanged.
```

New CMake option `WF_ENABLE_CRDT` defaults **OFF**. When OFF, zero impact on existing builds — Corrosion / Cargo / rustc never enter the build graph. When ON, builds `libwfcrdt.a` and the smoke test. Linux dev uses `cmake -DWF_ENABLE_CRDT=ON` (or a new `task build-editor` task).

---

## Open decisions resolved this phase

| Decision | Choice | Reason |
|---|---|---|
| Vendor mode | **Git submodule of y-crdt** | Cleanest provenance; pin to tagged release. Matches how upstream y-crdt wants vendoring done. |
| Cargo invocation | **Corrosion (CMake-Rust)** | First-class CMake integration. Single `corrosion_import_crate` call. Better than `ExternalProject_Add` for dependency tracking + incremental builds. |
| CRDT ownership | **Editor owns Y.Doc** | Engine stays Rust-free. Engine exposes plain C++ mutation API. Editor's CRDT bridge translates Yrs ops to engine calls. |
| Wrapper scope this phase | **FFI link + smoke test only** | Defer the C++ RAII wrapper until the editor shell phase, when its consumer shape is clearer. ~1-wk estimate stays honest. |
| Build artefact | **Static lib (`libyffi.a`)** | Cleanest link; avoids ELF runtime path issues. Both static and cdylib are upstream-supported. |

---

## File layout

```
wftools/y-crdt/                  ← NEW submodule (pinned tag)
  yffi/Cargo.toml                ← upstream's cbindgen-backed staticlib
  yffi/tests-ffi/include/libyrs.h  ← pre-generated header (upstream-committed)
  ...

engine/crdt/                     ← NEW directory
  CMakeLists.txt                 ← Corrosion import + libwfcrdt target
  wfcrdt_smoke.c                 ← C smoke test (Doc/Map/Array round-trip)

cmake/                           ← NEW directory (if not present)
  Corrosion/                     ← submodule, OR FetchContent_Declare
  FindYrs.cmake                  ← optional convenience module

CMakeLists.txt                   ← root. Add WF_ENABLE_CRDT option, add_subdirectory(engine/crdt) when ON.

Taskfile.yml                     ← add `build-editor` task that flips WF_ENABLE_CRDT=ON
.gitmodules                      ← register y-crdt + corrosion submodules
```

No changes to `libwfengine.a` sources, `wf_game`, Android, iOS, Codemagic, or existing Rust tools (`iffcomp-rs` etc.).

---

## Implementation steps

Each step is its own commit per [feedback_commit_after_each_phase](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md).

1. **Vendor y-crdt as submodule.** `git submodule add https://github.com/y-crdt/y-crdt wftools/y-crdt`. Pin to the latest tagged release (currently `v0.x` — check at submodule-add time). Smoke: `cargo build --release -p yffi --manifest-path wftools/y-crdt/Cargo.toml` produces `target/release/libyffi.a` + the pre-generated `libyrs.h`.

2. **Vendor Corrosion.** `git submodule add https://github.com/corrosion-rs/corrosion cmake/Corrosion`. Pin to latest stable tag. (Alternative: `FetchContent_Declare` — submodule is more deterministic for offline builds.)

3. **Root CMakeLists wiring.** Add `option(WF_ENABLE_CRDT "Build CRDT support library" OFF)` near the top. Add `if(WF_ENABLE_CRDT)`-guarded `add_subdirectory(cmake/Corrosion)` + `add_subdirectory(engine/crdt)`. Default OFF — verify `task build` still works with no Rust installed (rename `cargo` temporarily on dev machine to simulate, or test in a Docker container).

4. **`engine/crdt/CMakeLists.txt`.** Single file:
   - `corrosion_import_crate(MANIFEST_PATH ${CMAKE_SOURCE_DIR}/wftools/y-crdt/yffi/Cargo.toml CRATE_TYPES staticlib)`
   - `add_library(wfcrdt STATIC wfcrdt_stub.c)` (one-file stub to get a real target; smoke test will replace stub later)
   - `target_link_libraries(wfcrdt PUBLIC yffi)` (Corrosion exposes `yffi` as a CMake target)
   - `target_include_directories(wfcrdt PUBLIC ${CMAKE_SOURCE_DIR}/wftools/y-crdt/yffi/tests-ffi/include)`

5. **Smoke test executable.** `engine/crdt/wfcrdt_smoke.c` — minimal C program that exercises:
   - `ydoc_new()` + `ydoc_destroy()` round-trip
   - `ytransaction_state_vector_v1` / `ytransaction_state_diff_v1` (Yjs-compatible `encodeStateAsUpdate` / `applyUpdate` shape) — two Docs, one applies the other's diff, verify state vectors match
   - `ymap_insert` + `ymap_get` on a top-level Y.Map (the `meta` map per the [CRDT schema](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md))
   - `yarray_insert` + `yarray_len` on a top-level Y.Array (the `content` array)
   - Observer registration on the array — insert an item, verify the callback fires with the right op
   - Returns 0 on success, non-zero on any failed assertion.
   - Single CMake target: `add_executable(wfcrdt_smoke wfcrdt_smoke.c)` + `target_link_libraries(wfcrdt_smoke PRIVATE wfcrdt)`.

6. **CI / Codemagic verification.** No Codemagic changes needed — `WF_ENABLE_CRDT=OFF` by default, Codemagic's existing `cmake` invocations don't pass the flag, nothing changes. Add a comment in `codemagic.yaml` noting the toggle exists but is deliberately off for shipped builds. Manual local check: `task build && ./engine/wf_game` works without Rust (rename cargo or use `PATH= cmake ...` to confirm).

7. **Taskfile addition.** New `build-editor` task:
   ```yaml
   build-editor:
     desc: Build wf_game + libwfcrdt.a (requires Rust toolchain)
     cmds:
       - cmake -S . -B build -DWF_ENABLE_CRDT=ON
       - cmake --build build --target wfcrdt_smoke
       - ./build/engine/crdt/wfcrdt_smoke
   ```

8. **Docs.** Update [design doc](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) Tier 2 entry to reflect the locked-in "editor owns Y.Doc" decision and link this plan. Update [wf-status.md](../../WorldFoundry.2026-new-level/wf-status.md) per [feedback_wf_status_rolling_summary](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_wf_status_rolling_summary.md). Add a TODO entry per [feedback_log_discoveries_in_todo](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_log_discoveries_in_todo.md) noting that `libwfcrdt.a` should NOT be linked into `libwfengine.a` unless the architectural decision is explicitly revisited.

---

## Verification

1. **Default build unchanged.** `task build` on a clean checkout produces `wf_game` identical to pre-binding state. No `cargo` invocation in the build log. `ldd ./engine/wf_game` shows no Rust artefacts.

2. **Editor build green.** `task build-editor` on Linux produces `libwfcrdt.a` + `wfcrdt_smoke`. The smoke binary runs to completion and prints a one-line success message.

3. **Round-trip parity check.** The smoke test's two-Doc scenario: Doc A inserts 3 array items, encodes state diff, Doc B applies it, verifies its array length is 3 and item values match. Confirms wire-format compatibility with the upstream Yjs protocol.

4. **Observer fires.** Smoke test asserts the array-change callback was invoked exactly once during the test run with the expected op type. Confirms the C ABI's observer registration works — load-bearing for the future direct-read engine bridge.

5. **Codemagic builds unchanged.** Push the branch with `WF_ENABLE_CRDT=OFF` default; confirm Codemagic iOS + Android builds succeed with no cargo step in the log. ([Codemagic is manual-trigger](../../.claude/projects/-home-will-WorldFoundry/memory/project_codemagic_manual_trigger.md), so this is a single explicit run.)

6. **Submodule cleanliness.** `git submodule status` shows both y-crdt and Corrosion pinned to tagged commits. Fresh clone with `git clone --recurse-submodules` works.

---

## Next-phase work this enables

This binding is sub-task #1. The work it unblocks, in dependency order:

- **C++ RAII wrapper** (`wfcrdt::Doc`, `wfcrdt::Map`, etc.) — thin shim over yffi for ergonomics. Lands when the editor shell needs callers that don't want to manage raw C handles. Probably ~2–3 days when triggered.
- **IFF↔Y.Doc translator** — separate v1 line item (~2–3 wk). Needs iffcomp-rs reshaped as a Rust library (it's a CLI today). Builds on top of `libwfcrdt.a`. Wire format: round-trip `.iff.txt` ↔ Y.Doc per the [CRDT schema](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md).
- **Engine mutation API** (`WFEngine::SetActorField`, `SpawnActor`, `RemoveActor`, `ApplyPatch`) — first-class engine deliverable, not "deferred API design uncertainty." Surface drives editor's direct-read bridge AND debugger AND replay AND headless test harness. Estimate ~1–2 wk; the operations already exist as engine internals (`Actor::SetFromOAS`, level loading, actor spawn/despawn) — this exposes them as a stable callable boundary.
- **WebSocket relay** (Rust binary, ~200 LOC over Yrs) — separate v1 line item; doesn't touch C++ engine. Independent workstream.
- **Editor shell** (ImGui, viewport, panels) — separate v1 line item; first C++ consumer of both `libwfcrdt.a` and the new engine mutation API.
- **DAP / step debugger reuse** ([project_followup_dap_phase_c](../../.claude/projects/-home-will-WorldFoundry/memory/project_followup_dap_phase_c.md), [project_followup_lua_remote_debugger](../../.claude/projects/-home-will-WorldFoundry/memory/project_followup_lua_remote_debugger.md)) — when triggered, hooks into the same engine mutation API the editor uses. The split shape here is what makes that reuse mechanical instead of a re-architecting job.

---

## Critical files

- [`/home/will/WorldFoundry.2026-new-level/CMakeLists.txt`](../../WorldFoundry.2026-new-level/CMakeLists.txt) — root; add `WF_ENABLE_CRDT` option.
- [`/home/will/WorldFoundry.2026-new-level/Taskfile.yml`](../../WorldFoundry.2026-new-level/Taskfile.yml) — add `build-editor` task.
- [`/home/will/WorldFoundry.2026-new-level/codemagic.yaml`](../../WorldFoundry.2026-new-level/codemagic.yaml) — comment only (no functional change).
- [`/home/will/WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md`](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) — update Tier 2 entry with the locked decision.
- [`/home/will/WorldFoundry.2026-new-level/wf-status.md`](../../WorldFoundry.2026-new-level/wf-status.md) — add status row.
- [`/home/will/WorldFoundry.2026-new-level/TODO.md`](../../WorldFoundry.2026-new-level/TODO.md) — note the "don't link wfcrdt into wfengine" constraint.
- `engine/crdt/CMakeLists.txt` — new, Corrosion glue.
- `engine/crdt/wfcrdt_smoke.c` — new, smoke test.

---

## Cross-references

- [project_tools_language](../../.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md) — Rust is the project's tools language; this binding is the first Rust artefact linked into a C++ binary.
- [project_ios_port_blocker](../../.claude/projects/-home-will-WorldFoundry/memory/project_ios_port_blocker.md) — Codemagic 500 min/mo budget; preserved by `WF_ENABLE_CRDT=OFF` default.
- [feedback_no_giant_vendor](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_no_giant_vendor.md) — y-crdt submodule (small) and Corrosion submodule (small) both fit under the 40 MB cap.
- [feedback_commit_after_each_phase](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md) — each of the 8 steps is its own commit.
- [Editor design doc § Tier 2 Engine↔CRDT bridge](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) — the bridge architecture this binding enables.
- External: [y-crdt repo](https://github.com/y-crdt/y-crdt), [Corrosion (CMake-Rust)](https://github.com/corrosion-rs/corrosion), [Yjs document-updates API](https://docs.yjs.dev/api/document-updates).
