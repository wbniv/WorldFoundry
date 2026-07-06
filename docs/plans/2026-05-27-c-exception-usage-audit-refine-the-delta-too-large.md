# Plan — C++ exception-usage audit + refine the delta-too-large plan

> **Note:** the recovered text in this slot before this rewrite was the *VPN-robustness*
> plan, which already shipped as `03dc866c` on 2026-05-27. The current pending work is
> different — the audit the user asked for ("you just added `<exception>` — is that the
> first time? is it only in the editor?") plus the matching refinements to the
> in-flight delta-too-large plan.

## Context

The in-flight plan `docs/plans/2026-05-30-delta-too-large.md` (engine resilience +
self-diagnosing `terminate`) added a `std::set_terminate` handler in
`engine/wf_edit/main.cc`, which required `#include <exception>`. Before committing, the
user asked: is this the **first** `<exception>` include in the codebase, and is it
**editor-only** (which it should be, given WF's MCU-target constraints — exceptions are
heavy and historically forbidden in engine code, parallel to the `-fno-rtti` policy).

This plan captures the audit's findings, the (small) follow-up items it surfaced, and
the matching tweaks to the delta-too-large plan. It blocks the commit of the
delta-too-large fix.

## Audit findings (read-only sweep already done)

### Direct `<exception>` / `<stdexcept>` / `<system_error>` includes — first-party WF code

| File | Notes |
|---|---|
| `engine/wf_edit/main.cc` | The one I just added for `std::set_terminate`. |
| `engine/vendor/cpp-httplib-v0.20.0/httplib.h` | Vendored 3rd-party library, not first-party. |
| `wftools/y-crdt/tests-ffi/include/doctest.h` | y-crdt's C-side doctest harness — test-only, not shipped. |

→ **Yes, this is the first explicit `<exception>` include in first-party WF code.**

### `try` / `catch` / `throw` usage — first-party WF code

| Area | Hits | Linked into |
|---|---|---|
| `engine/wf_edit/main.cc`, `webrtc_session.cc`, `level_doc.cc` | many (`identity.json` parse, libdatachannel send guards, Doc load) | **editor only** (`wf-edit` target) |
| `engine/stubs/debug_server.cc:141` | one `try { … } catch (...) { return false; }` for `std::stod` | `wfengine` via `WF_SOURCES` at `CMakeLists.txt:583`, gated on `WF_DEBUG_BRIDGE` (default ON desktop) |
| `engine/pilot/host_bridge.cc:85` | one `try { std::stod(…) } catch (...) { return 0.0; }` | pilot (host tooling); not the wf_game ship build |
| `wfsource/source/` (engine source proper) | **zero** | n/a |

→ Engine source proper (`wfsource/source/`) is **completely exception-free**, as expected.
→ Editor (`engine/wf_edit/`) uses exceptions liberally — consistent with its host-only role
   and the JSON / WebRTC libraries it pulls in.
→ Two stray try/catches sit in non-editor host-side code (`debug_server.cc`, `host_bridge.cc`).
   Both use `catch(...)` without `std::exception&`, so neither *includes* `<exception>` —
   they compile under default exception support. See the policy-tension item below.

### `-fno-exceptions` scope

| Target | Flag in Release+Clang |
|---|---|
| `wfengine` | `-fno-exceptions -fno-unwind-tables -fno-asynchronous-unwind-tables` (`CMakeLists.txt:701`) |
| `wf_game`  | same (`CMakeLists.txt:767`) |
| `Jolt` (Android only) | same (`CMakeLists.txt:783`) — comment explicitly notes "Jolt has no `throw` in its source" |
| `engine/wf_edit/*` (editor app) | **no flag** — exceptions enabled (uses them) |
| `engine/stubs/*`, `engine/pilot/*` | **no flag** as a directory; `debug_server.cc` is in `wfengine` so it inherits the flag |

→ The `debug_server.cc` `try { std::stod } catch (...)` at line 141 is inside a target that
   gets `-fno-exceptions` in Release-Clang. Either (a) Release-Clang isn't the default for
   the bridge-enabled desktop build path that uses it, (b) it has compiled silently because
   compilers are lenient with `catch(...)` in `-fno-exceptions` (clang emits a warning, not
   an error), or (c) it would break a Release-Clang+bridge build that nobody has run. Worth
   a one-line follow-up — out of scope for this commit.

## Conclusions

1. **The `<exception>` include in `engine/wf_edit/main.cc` is editor-only and is the first
   first-party use of the header.** That matches the policy and is the right place for it
   — the editor app is the only WF binary built with exception support enabled by default.
2. **The `std::set_terminate` handler is correctly scoped.** It lives in `wf_edit`'s `main.cc`
   and only runs in the editor binary; `wf_game` is untouched and stays exception-free.
3. **The pre-existing `engine/stubs/debug_server.cc` try/catch is a latent policy-tension item**
   — it lives in `wfengine` (which carries `-fno-exceptions` in Release-Clang). Filing as a
   separate TODO; not blocking the editor change.
4. **No changes needed to the delta-too-large code edits themselves.** The audit *validates*
   them rather than redirecting them.

## Deliverables

### 1) Audit report

Write `docs/investigations/2026-05-30-cpp-exceptions-audit.md` containing the tables above,
the conclusions, the `-fno-exceptions` scope analysis, and links to the relevant
`CMakeLists.txt` lines + the memory `project_no_rtti_architectural_constraint` (the
same cost-on-MCU-not-ideology logic applies to exceptions as it does to RTTI).

### 2) Refinements to `docs/plans/2026-05-30-delta-too-large.md`

- Add a one-line note under §2 that the `<exception>` include is the first first-party
  use of the header, validated by the audit (link the report).
- Note that the `typeid(e).name()` originally planned for the handler was dropped (would
  break `-fno-rtti`) — fall back to `e.what()` + the backtrace, which is what's actually
  implemented.
- Add the TODO follow-up: investigate `engine/stubs/debug_server.cc:141` try/catch under
  Release-Clang + `WF_DEBUG_BRIDGE=ON`.

### 3) Smoke + commit (already-implemented code)

- `task build-wf-edit` → confirm `✓ wf-edit built` (already green from background build
  `breapkyo1` exit 0 after the RTTI fix).
- Synthetic stall test: `kill -STOP <pid>` 6 s, `kill -CONT`; editor must survive with a
  single "editor: large frame stall, clamping" warning instead of asserting.
- Commit `display.cc` + `engine/wf_edit/main.cc` + the audit report + the updated plan
  in one logical commit (docs land with the code per the standing convention).
- Add a `wf-status.md` History entry + flip the plan's Status to DONE.

## Critical files

- `wfsource/source/gfx/gl/display.cc` (the `gEditorMode`-gated assert clamp — already edited)
- `engine/wf_edit/main.cc` (the `TerminateHandler` + `std::set_terminate` — already edited)
- `docs/plans/2026-05-30-delta-too-large.md` (refine per §2 above)
- `docs/investigations/2026-05-30-cpp-exceptions-audit.md` (new — write per §1 above)
- `wf-status.md` (one History entry)

No `CMakeLists.txt` changes — the audit confirmed the scope is already correct.

## Verification

Same as in the parent plan, plus: the audit report exists, the `<exception>` include
appears only in `engine/wf_edit/main.cc` (grep), and the editor binary survives the
`STOP`/`CONT` synthetic stall.

## Notes

- Sizing: ~30 min for the audit write-up + plan refinement + commit; the code edits are
  already done and the build is already green.
- The audit doubles as a precedent for future C++-feature questions ("is X editor-only?")
  — keep the same table format if it comes up again.
