# Plan — "delta too large" + post-connect `terminate`: engine resilience + self-diagnosing crashes

**Date:** 2026-05-30
**Status:** **DONE 2026-05-30** — `gEditorMode`-gated clamp in `display.cc` + `set_terminate` handler in `engine/wf_edit/main.cc`, STOP/CONT smoke verified survival. Audit refinements landed alongside.
**Related:** open follow-up from [VPN-robustness plan](2026-05-27-quick-tunnel-vpn-robustness.md); [exception-usage audit](../investigations/2026-05-30-cpp-exceptions-audit.md) validates the include scope of the `set_terminate` handler.

## Context

During a long `wf-edit` collab session (Phase 1 verification, ASan Debug build, on Surfshark VPN, with a third "mover" peer pushing CRDT updates), the host editor logged a long run of *"delta too large: 1.01…"* frame deltas at ~1 s each, then died with:

```
terminate called without an active exception
```

The session connected fine and demonstrated the feature; the death came later, under load. It's a stability / observability problem, not a blocker for the feature itself — but it's worth fixing because (a) the engine can be killed by long stalls today, and (b) the actual `terminate` source is opaque, so the next time we won't know what to fix without diagnostics already in place.

## Root cause (what the log lines actually mean)

In [`wfsource/source/gfx/gl/display.cc:785–822`](../../wfsource/source/gfx/gl/display.cc) the per-frame delta-time path does **three** things, separately:

1. `assert(deltatime.tv_sec < 5);` — a hard `abort()` if the frame gap is ≥ 5 s (prints "Aborted", no `terminate` message).
2. If `delta > 1/5 s`, print *"delta too large: …"* and **clamp** to 0.2 s — purely a warn-and-clamp, **benign**.
3. If `delta < 1/1200 s`, clamp to 1/1200 — fps cap.

So the *"delta too large"* lines themselves are the engine recovering gracefully from ~1 s frame stalls. The killer is the separate `terminate called without an active exception`, which libstdc++ prints when `std::terminate` runs — i.e. an unhandled exception, a `noexcept` violation, or a joinable `std::thread` destroyed without `join()`. We don't know which path triggered it because the runtime doesn't print details.

The 1 s frame stalls themselves are the **symptom** (something blocking the main thread); the `terminate` is what actually killed the process, and its cause is currently invisible.

## Fixes

### 1) Engine resilience: in **editor mode only**, clamp the 5 s frame gap instead of asserting

In `display.cc` (the function that ends at `:822`), gate the existing `assert(deltatime.tv_sec < 5)` on the same `gEditorMode` flag the rest of the engine uses for editor-vs-game divergence (e.g. the StatPlat-move guards in `wfsource/source/room/rooms.cc` `AddObjectToRoom` and `wfsource/source/game/level.cc` `SetPendingRemove`):

- **Game mode (unchanged):** keep `assert(deltatime.tv_sec < 5)` — a >5 s stall during actual gameplay genuinely *is* catastrophic (the world would advance huge amounts while the player stared at a frozen screen; better to abort loudly than silently continue into broken state).
- **Editor mode:** drop the assert; print a warning ("editor: large frame stall, clamping") and clamp `delta` to 5 s, matching the warn-and-clamp idiom already used 14 lines below for the > 0.2 s case. The editor survives stalls of any length instead of being killed when one crosses 5 s.

~10 lines, one `if (gEditorMode) { … } else { assert(…); }`. The existing 0.2 s clamp keeps the per-frame delta sensible in both modes.

This removes the editor's hardest failure mode under load while keeping the game's loud failure on real bugs. It does not, on its own, explain or fix the `terminate` we saw — those are different code paths.

### 2) Make the next `terminate` self-diagnosing

In [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) `main()` (very top, alongside the existing `RunTurnTest` / `WF_EDIT_HOST_TUNNEL_TEST` early returns) install a `std::set_terminate` handler that, before letting the process die:

- rethrows `std::current_exception()` inside a `try/catch(std::exception&)` and prints `e.what()` (or "no active exception" if none) — captures the *kind* of failure libstdc++ would have hidden;
- prints a backtrace via `<execinfo.h>` `backtrace()` + `backtrace_symbols_fd(STDERR_FILENO)` — captures *where* it fired;
- calls `std::abort()` so ASan / cores still trigger normally.

> Implementation note (2026-05-30): the `typeid(e).name()` originally listed here was dropped during implementation — it breaks `-fno-rtti`, which the editor inherits from the engine. Backtrace + `e.what()` carry enough signal in practice. The `#include <exception>` this needs is the *first* explicit first-party `<exception>` include in WF code — see the [exception-usage audit](../investigations/2026-05-30-cpp-exceptions-audit.md) for why that's correctly scoped (editor only, parallel to the `-fno-rtti` policy).

Tiny — one function plus the `set_terminate` call. Zero runtime cost when nothing terminates. The *next* time `terminate` fires we get the real cause for free instead of investigating from scratch.

### 3) Deferred: investigate the 1-FPS stall once #2 has spoken

Don't speculate now. Once #1 and #2 are in place:
- if the editor stops dying under load (just stutters), we're done for this report;
- if it dies again, the new handler tells us the cause; from there we instrument the suspected hot path. Candidates I'd look at first (in order): the main-loop `CollabDrain` → `Doc.apply(remote update)` on the main thread (under ASan, a large remote update could plausibly take ~1 s and a chain of them could pile up), libdatachannel send/recv backpressure, ASan shadow-memory thrashing on the engine's large allocations.

## Critical files

- `wfsource/source/gfx/gl/display.cc` — gate the `assert(deltatime.tv_sec < 5)` at line 791 on `gEditorMode`: editor → clamp+warn matching the pattern at 805-812; game → unchanged. ~10 lines. Needs the `gEditorMode` extern already used by `rooms.cc` / `level.cc`.
- `engine/wf_edit/main.cc` — add `InstallTerminateHandler()` (small free function near `RunTurnTest`) and call it at the top of `main()`. ~30 lines including the backtrace logic. Needs `<execinfo.h>` (already used by ASan's runtime; pull it directly).

No build-system changes; both files are already in the `wf_edit` target. The `display.cc` change leaves `wf_game` behaviour untouched (the assert still fires in game mode).

## Verification

- **Smoke / regression:** rebuild via `task build-wf-edit`, confirm the `✓ wf-edit built` marker, then `--host-tunnel` connects normally (no change to the happy path). The `task wf_edit_undo` / `wf_edit_add` / `wf_edit_turn` CPU-only ctest set must still pass (no GL, but they exercise the engine's frame step a little — make sure nothing changed there).
- **Engine resilience:** synthetic test — `kill -STOP <wf_edit pid>` for ~6 s then `kill -CONT`, observe a single *"delta too large"*-style warning + a 5 s clamp; editor must keep running. (Pre-fix this would abort.)
- **Terminate handler:** small test under env `WF_EDIT_TERMINATE_TEST=1` that calls `std::terminate()` from `main` after setup — confirm we see the backtrace + "no active exception" line on stderr before exit. (Don't ship this as a permanent test mode; remove or guard with `#ifndef NDEBUG`.)
- **Real follow-up:** rerun the two-editor + mover scenario that exhibited the original symptom. With both fixes in, either it survives, or the new terminate handler prints something we can act on. Either outcome closes this plan.

## Notes
- Engine change is intentionally minimal and pattern-matches existing code in the same function — no new behaviour, just relax the hardest cliff.
- The terminate-handler is pure diagnostic; it doesn't suppress crashes, it makes them legible. Worth keeping permanently.
- Estimated effort: ~half a day, *average-programmer scale* (fix + handler + manual smoke). The deferred root-cause investigation in #3 is open-ended and gated on whether the symptom recurs.
