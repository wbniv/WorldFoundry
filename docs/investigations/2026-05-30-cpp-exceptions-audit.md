# Investigation — C++ exception usage in WorldFoundry

**Date:** 2026-05-30
**Trigger:** [`docs/plans/2026-05-30-delta-too-large.md`](../plans/2026-05-30-delta-too-large.md) added `#include <exception>` to `engine/wf_edit/main.cc` for a `std::set_terminate` handler. Before committing, audit whether that include is the first first-party use of `<exception>` and whether it's properly scoped to the editor only — exceptions on WF's fixed-point MCU targets carry the same cost story as RTTI (flash + unwinding tables + uneven toolchain support), so engine code stays exception-free as a matter of policy, parallel to the `-fno-rtti` constraint.

## Summary

- The new `<exception>` include in [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) is the **first explicit `<exception>` include in first-party WF code**. (Two prior hits exist, both non-first-party: a vendored library and a Rust crate's C-side test harness — see below.)
- Engine source proper (`wfsource/source/`) is **completely exception-free** — zero `try` / `catch` / `throw` statements. Enforced by `-fno-exceptions` on the `wfengine` and `wf_game` Release-Clang builds ([`CMakeLists.txt:701`](../../CMakeLists.txt), [`:767`](../../CMakeLists.txt)).
- Editor code (`engine/wf_edit/`) uses exceptions liberally — consistent with its host-only role and the libraries it consumes (nlohmann/json, libdatachannel).
- The `std::set_terminate` handler is therefore correctly scoped: it lives in the `wf_edit` target only; `wf_game` is untouched and stays exception-free.
- One latent policy-tension item surfaced: [`engine/stubs/debug_server.cc:141`](../../engine/stubs/debug_server.cc) contains a `try { std::stod(…) } catch (...)` inside the `wfengine` target, which carries `-fno-exceptions` in Release-Clang. Filed as a one-line TODO; see § Follow-up.

## Method

Three greps, applied across `engine/`, `wfsource/source/`, `wftools/`:

```
grep -rln '^#include <exception>\|^#include <stdexcept>\|^#include <system_error>'
grep -rnE '\bthrow [a-zA-Z_]|^[[:space:]]*try[[:space:]]*\{|^[[:space:]]*\}[[:space:]]*catch[[:space:]]*\('
grep -rn 'fno-exceptions\|-fexceptions' CMakeLists.txt
```

Vendored dirs (`_deps/`, `vendor/`, `target/`, `3rdparty/`) filtered out for the second sweep so the picture is "what WF compiles from its own sources." The first sweep deliberately left them in to see the full picture of who pulls the headers in transitively.

## Direct `<exception>` / `<stdexcept>` / `<system_error>` includes

| File | First-party? | Notes |
|---|---|---|
| [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) | ✓ yes | Added 2026-05-30 for `std::set_terminate` (this audit's trigger). |
| `engine/vendor/cpp-httplib-v0.20.0/httplib.h` | no — vendored | `cpp-httplib` is a header-only HTTP library; the engine pulls it in for the editor's local relay piece. Not WF source. |
| `wftools/y-crdt/tests-ffi/include/doctest.h` | no — vendor + test | The `doctest` single-header test framework shipped inside the y-crdt Rust crate's C-FFI test scaffolding. Not built into any WF ship binary. |

→ **First explicit `<exception>` include in first-party WF code: yes.**

## `try` / `catch` / `throw` usage — first-party code

| Area | Count | Linked into | Compile-flag context |
|---|---|---|---|
| [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) — `identity.json` parse, recent-rooms parse, save round-trip, `TerminateHandler` rethrow | 6 try-blocks | `wf-edit` only | Exceptions ON (no `-fno-exceptions` flag on the editor target) |
| [`engine/wf_edit/webrtc_session.cc`](../../engine/wf_edit/webrtc_session.cc) — signalling-JSON parse + RTP send safety | 3 try-blocks | `wf-edit` only | Same. |
| [`engine/wf_edit/level_doc.cc`](../../engine/wf_edit/level_doc.cc) — Doc load JSON | 1 try-block | `wf-edit` only | Same. |
| [`engine/stubs/debug_server.cc:141`](../../engine/stubs/debug_server.cc) — `std::stod` guard | 1 try-block | `wfengine` (via `WF_SOURCES` at [`CMakeLists.txt:583`](../../CMakeLists.txt)), gated on `WF_DEBUG_BRIDGE` (default ON desktop) | `wfengine` Release-Clang carries `-fno-exceptions` ← **policy tension** |
| [`engine/pilot/host_bridge.cc:85`](../../engine/pilot/host_bridge.cc) — `std::stod` guard | 1 try-block | pilot host-side tooling | Not in `wf_game` ship build |
| `wfsource/source/**` | **0** | `wfengine` / `wf_game` | `-fno-exceptions` enforced in Release-Clang |

→ Engine source proper is exception-free, as the policy demands. The editor is the only place exceptions cross from third-party libraries into WF code. ✓

## `-fno-exceptions` scope

| Target | Flag in Release+Clang | Source |
|---|---|---|
| `wfengine` | `-fno-exceptions -fno-unwind-tables -fno-asynchronous-unwind-tables` | [`CMakeLists.txt:701`](../../CMakeLists.txt) |
| `wf_game`  | same | [`CMakeLists.txt:767`](../../CMakeLists.txt) |
| `Jolt` (Android) | same — comment notes "Jolt has no `throw` in its source" | [`CMakeLists.txt:783`](../../CMakeLists.txt) |
| `engine/wf_edit/*` (editor) | **no flag** — exceptions enabled (uses them) | n/a |
| `engine/stubs/*` (as a directory) | **no flag** as a directory — files inherit whatever target they're linked into. `debug_server.cc` ends up in `wfengine`, so it inherits the flag. | n/a |
| `engine/pilot/*` | **no flag** as a directory — `pilot_core.cc` goes into `wfengine` ([`CMakeLists.txt:432`](../../CMakeLists.txt)); `host_bridge.cc` is host tooling. | n/a |

The flag's purpose is explicit in the surrounding comment on `Jolt` ([`CMakeLists.txt:783`](../../CMakeLists.txt)):

> Jolt has no `throw` in its source, so `-fno-exceptions` is a drop-in win — removes all the `.eh_frame` / `.gcc_except_table` entries that C++ template-heavy code generates by default.

So it's a code-size optimisation, exactly as `-fno-rtti` is a code-size optimisation. The same cost-on-MCU-not-ideology logic from `project_no_rtti_architectural_constraint` applies: it's expensive on the fixed-point MCU targets, negligible on dev hosts. Editor binaries run on dev hosts only, so exceptions are fine there.

## Conclusions

1. **The `<exception>` include in `engine/wf_edit/main.cc` is the first explicit first-party use of the header.** That's correct — the editor is the right host for it; engine code stays exception-free.
2. **The `std::set_terminate` handler is correctly scoped.** It lives in the `wf_edit` target only; `wf_game` is untouched. The handler runs only inside the editor binary.
3. **The `typeid(e).name()` originally planned for the handler body was dropped** during implementation — it would have broken `-fno-rtti` on the editor's own build (the editor inherits `-fno-rtti` because it compiles against the same engine headers). The handler now logs `e.what()` + a backtrace; that's strictly less information per failure, but the backtrace alone has been enough to triangulate `terminate`-class bugs in practice.
4. **One pre-existing policy-tension item:** [`engine/stubs/debug_server.cc:141`](../../engine/stubs/debug_server.cc) has a `try { std::stod(…) } catch (...) { return false; }` and links into `wfengine`, which carries `-fno-exceptions` in Release-Clang. One of three things is true:
   - the desktop bridge build path doesn't go through Release-Clang (most likely — bridge users tend to run Debug/RelWithDebInfo so ASan/debugger work, where `-fno-exceptions` doesn't apply);
   - Clang accepts `catch(...)` under `-fno-exceptions` with a warning rather than an error, so it has silently compiled (Clang's actual behaviour — `-fno-exceptions` turns `throw` and `catch` into warnings, not errors);
   - a Release-Clang build with `WF_DEBUG_BRIDGE=ON` is broken in a way nobody has hit.

   Worth running `cmake --preset release -DWF_DEBUG_BRIDGE=ON && task build` once to confirm, and either guard the try/catch on `WF_DEBUG_BRIDGE` + a separate "exceptions OK here" carve-out, or replace the `std::stod` with `std::strtod` (which doesn't throw — uses `errno`). Filed in `TODO.md`.

## Follow-up (filed in `TODO.md`)

- `engine/stubs/debug_server.cc:141` `try { std::stod } catch (...)` lives in a `-fno-exceptions` Release-Clang target. Verify the build path or rewrite to `std::strtod`. One-liner.

## Policy decision (confirmed 2026-06-02)

The question "should we allow exceptions in the editor code?" came up again. The build
map makes the answer concrete, so recording it here once:

1. **`-fno-exceptions` is Release+Clang-only** ([`CMakeLists.txt`](../../CMakeLists.txt):706/772
   on `wfengine`/`wf_game`, generator-gated). It's a code-size optimisation, paralleling
   `-fno-rtti` — **not** a blanket ban. `wf-edit`, `wf_game-dev`, and every Debug/GCC build
   compile with exceptions **on**.
2. **The editor/dev code is `#ifdef`-gated out of the shipped lean build** (`WF_ENABLE_EDITOR`
   / `WF_DEBUG_BRIDGE` / `WF_REST_API`). So `engine/wf_edit`, `engine/crdt`, `engine/mutation`,
   and the bridge stubs aren't even compiled into the one build that has `-fno-exceptions`.
3. **Therefore: exceptions are *already* allowed where the editor runs.** No flag to flip.
   - **Pure-host UI (`engine/wf_edit/*`):** may use exceptions freely (it already does —
     nlohmann, libdatachannel, `std::set_terminate`). Catch at the entry points.
   - **Engine-straddling stubs (`engine/stubs/debug_server.cc`, `rest_api.cc`, `engine/mutation/*`):**
     these link into `wfengine` and **inherit its flags**, so a Release+Clang build with the
     bridge enabled would make a throw abort. **Keep these no-throw** (`strtof`/`strtod`,
     error-returns, asserts) so they're correct under either setting. Cheap, robust.
4. **Escape hatch (deferred):** if the no-throw discipline ever chafes, lift the bridge/dev
   stubs out of `wfengine` into a host-only `-fexceptions` static lib linked only by dev
   hosts — makes the partition explicit. Small CMake refactor; not needed today.

The audit's `try { std::stod }` follow-up is now **fully closed**: `debug_server.cc` moved to
`std::strtod` (2026-05-30), and `rest_api.cc`'s sibling `std::stof` moved to `std::strtof`
(2026-06-02, [editor-fail-clean-nuggets plan](../plans/2026-06-02-editor-fail-clean-nuggets.md)).

## Related

- [`project_no_rtti_architectural_constraint`](../../../.claude/projects/-home-will-WorldFoundry/memory/project_no_rtti_architectural_constraint.md) memory — the parent policy. Same cost-on-MCU logic; `-fno-exceptions` follows the same shape as `-fno-rtti`.
- [`docs/plans/2026-05-30-delta-too-large.md`](../plans/2026-05-30-delta-too-large.md) — the parent plan; this audit validates its scope.
