# Plan — Fix `wf-edit --relay --frames N` `ReadActorNames` crash, unblock the b2 two-editor screenshot

**Date:** 2026-05-31
**Status:** Planned (not started)
**Parent:** §2 of [B-leftovers plan](2026-05-31-shared-cursors-b-leftovers.md)

## Context

The B-leftovers verification step needed `wf-edit --relay=ws://127.0.0.1:PORT --room=R --frames N --screenshot <PPM> <level>` to run cleanly so [`tests/screenshot_two_peer_b2.sh`](../../tests/screenshot_two_peer_b2.sh) could capture two editors mid-call. Running it (including on a baseline checkout) aborts deterministically with:

```
yarray_get  ← Rust non-unwinding panic
  ... wfcrdt::Array::get(i)                @ engine/crdt/wfcrdt.cpp:372
  ... wfedit::ReadActorNames               @ engine/wf_edit/level_doc.cc:582
  ... main                                 @ engine/wf_edit/main.cc:2927
```

The relevant sequence in [`main.cc:2918-2929`](../../engine/wf_edit/main.cc):

```cpp
ctx.relay_client.send(ctrl.data(), ctrl.size());          // CONTROL join
// Wait up to 1 s for the relay's initial full-state SYNC.
std::vector<uint8_t> frame;
const double deadline = glfwGetTime() + 1.0;
while (glfwGetTime() < deadline && !ctx.relay_client.poll(frame))
    pump(connecting_msg.c_str());
if (!frame.empty() && frame[0] == 0x01 && frame.size() > 1) {
    auto txn = doc.beginRemote();
    txn.apply(wfcrdt::ByteView{frame.data() + 1, frame.size() - 1});
    ctx.actor_names = wfedit::ReadActorNames(doc);   // ← crash here
    ctx.actor_eids  = wfedit::ReadActorEids(doc);
}
```

`ReadActorNames` calls `content.get(i)` for each `i in [0, content.len())`. yrs's `yarray_get` panics even though `i < len()`, which means **`content.len()` and the array's actual storage disagree** — strongly suggesting a stale `_branch` handle or txn lifetime issue in the [`wfcrdt`](../../engine/crdt/wfcrdt.cpp) RAII wrapper, surfacing only on this specific path because: (a) interactive use stays in the program past this point and the issue is masked by later txns, (b) prior screenshot tests used `WF_EDIT_FAKE_PEER` and never connected to the relay.

The crash is **not** caused by the B-leftovers changes — reproduces on a baseline checkout (verified during the leftovers turn by stashing local work and rebuilding). It's a pre-existing latent bug that only surfaces with `--relay + --frames N`.

## Phase 1 — Reproduce + isolate (~20 min)

A reliable headless repro using the script already shipped in [`6737cbcc`](.):

```sh
bash tests/screenshot_two_peer_b2.sh   # currently fails: both editors abort
```

Or even simpler — single editor connecting to a relay, no peers:

```sh
wftools/wf_collab/target/release/wf-relay --port 9991 >/tmp/r.log 2>&1 &
XDG_CONFIG_HOME=/tmp/x DISPLAY=:0 ./build-editor/wf-edit \
    --relay=ws://127.0.0.1:9991 --room=test --frames 60 \
    --screenshot /tmp/x.ppm wflevels/qbert_practice/qbert_practice.iff
```

This aborts in the same place — proves it's the apply-SYNC path, not multi-peer interaction.

### Diagnostics to add

Around the apply at [`main.cc:2927`](../../engine/wf_edit/main.cc) (`if (!frame.empty() && frame[0] == 0x01...)`), wrap with a `fprintf(stderr, …)` triple:

1. **Before apply** — `frame.size()`, first 32 bytes hex, and (already-loaded-locally) `txn.array("content").len()` (open a short read txn just for this — `auto t = doc.begin(); fprintf(stderr, "[crash-investigation] pre-apply content len=%d", t.array("content").len());`).
2. **After apply** — same len read in a fresh read txn.
3. **Inside `ReadActorNames`** — temporary fprintf the len, then on each iteration print `i` before calling `content.get(i).asMap()`. The frame just before the panic identifies whether it's index 0 (`len=N, attempting get(0) → panic` would mean the branch handle is bogus) or some specific later index (some kind of mid-array corruption).

Diagnostic-only commit; reverted at the end of the plan per [`feedback_debug_instrumentation_teardown`](../../../../home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_debug_instrumentation_teardown.md).

## Phase 2 — Identify (~20 min)

Three concrete hypotheses, in increasing-fix-complexity order; Phase 1 logs narrow which is right:

### H1: Empty SYNC from a fresh room corrupts `content`

The relay's first frame to a new joiner of an empty room may be a zero-length update or a header-only update. `txn.apply(ByteView{ptr, 0})` or applying garbage might still set internal flags on the Doc that leave `content` in a half-state where `len()` says one thing and `get()` says another.

**If H1 confirmed (logs show len > 0 but get(0) panics, and the frame is suspiciously small):** guard the apply call so a < 2-byte SYNC frame is treated as a no-op. ~3 lines.

### H2: Local-load and remote SYNC create two `content` arrays

`LoadLevelTreeIntoDoc` ([`level_doc.cc`](../../engine/wf_edit/level_doc.cc)) creates `content` as a yrs Array via `txn.array("content")`. The remote SYNC carries its *own* `content` array (also created via `txn.array("content")`). Yrs's CRDT merge for arrays-of-Maps under the same root key may not be what we want — yrs creates the array on first access keyed by name, so both peers should see the same logical array, but a stale `_branch` handle in the local `wfcrdt::Array` wrapper might point at the pre-merge version.

**If H2 confirmed (logs show pre-apply len = N from local load, post-apply len = M ≠ N, then get(i) panics):** invalidate / re-open the `content` wrapper after `beginRemote().apply()` — likely a fix in `wfcrdt::Doc::beginRemote()` to drop cached branch handles, or in `level_doc.cc::ReadActorNames` to open `content` *after* a synchronization point.

### H3: `_branch` cache lifetime bug in `wfcrdt::Array`

The wfcrdt RAII wrapper caches a `_branch` pointer ([`engine/crdt/wfcrdt.{hpp,cpp}`](../../engine/crdt/)) but yrs's underlying branch pointer may be invalidated by a transaction that mutates the Doc structurally. The yrs C ABI's `yarray_get` likely consumes the branch pointer and txn raw; a stale branch → undefined behaviour → assertion / panic.

**If H3 confirmed (logs show the panic always at `get(0)`, len is sane, but a fresh `doc.begin().array("content")` works while the cached one panics):** drop the `_branch` cache in `wfcrdt::Array` for the txn-bound paths; re-resolve on each access. A few lines in [`engine/crdt/wfcrdt.cpp`](../../engine/crdt/wfcrdt.cpp).

## Phase 3 — Fix + verify (~30 min)

Apply the fix matching whichever hypothesis Phase 2 confirmed. The fix lands in either:

- `engine/wf_edit/main.cc:2927` (H1) — guard the SYNC apply.
- `engine/crdt/wfcrdt.cpp` (H2 or H3) — invalidate / rebuild branch handles around `beginRemote`.

Strip the Phase 1 fprintfs in the same commit (debug instrumentation teardown — keep the file changes coherent).

### Verification

1. **The simple repro** — single editor + relay + `--frames` exits cleanly with a PPM, no abort.
2. **`tests/screenshot_two_peer_b2.sh`** — produces `tests/screenshots/wfedit_shared_cursors_b2_live_{A,B}.png`. Inspect B's PNG: should contain Alice's orange selection ring and frustum overlaying the qbert pyramid. Replace the B-leftovers screenshot link in [`wf-status.md`](../../wf-status.md) with the live one.
3. **Backwards compat** — make sure the existing `WF_EDIT_FAKE_PEER` solo screenshot still works (it doesn't go through the relay; should be unaffected).
4. **Unit tests** — existing `task wf_edit_undo` ctest still passes. If H3 fix changes the branch-caching contract, this is the gate that'd catch it.
5. **Interactive use** — Open `wf-edit` on snowgoons, click around — no regression in the property panel, gizmo, or outliner.

## Phase 4 — Close out (~10 min)

- Update [B-leftovers plan](2026-05-31-shared-cursors-b-leftovers.md): item (2) status flipped from "blocked on a separate yrs crash (TODO)" → "DONE, screenshot at …".
- Update [`TODO.md`](../../TODO.md) — flip the `wf-edit --relay --frames N` crash row from `[ ]` to `[x]` with the fix commit.
- Prepend a [`wf-status.md`](../../wf-status.md) history entry: "B leftovers item (2) unblocked — yrs `ReadActorNames` crash on apply-SYNC fixed, two-editor live verification screenshot landed."
- If the fix touched wfcrdt's branch caching, consider whether [`project_yrs_upgrade_decision`](../../../../home/will/.claude/projects/-home-will-WorldFoundry/memory/project_yrs_upgrade_decision.md) needs an update.

## Critical files

- `engine/wf_edit/main.cc` (apply-SYNC site `:2927`) — diagnostic instrumentation in Phase 1; possibly the fix in Phase 3 (H1).
- `engine/wf_edit/level_doc.cc` (`ReadActorNames` `:582`) — temporary diagnostic instrumentation in Phase 1.
- `engine/crdt/wfcrdt.cpp` (`Array::get` `:371`, `Doc::beginRemote`) — Phase 2 / 3 fix site for H2 or H3.
- `tests/screenshot_two_peer_b2.sh` — re-runs unchanged once the fix lands.
- `tests/screenshots/wfedit_shared_cursors_b2_live_{A,B}.png` (new) — the canonical live screenshot the leftovers plan promised.
- `docs/plans/2026-05-31-shared-cursors-b-leftovers.md` — flip (2) to DONE.
- `TODO.md` — flip the crash row.
- `wf-status.md` — history entry.

## Sizing

~1 h average-programmer scale: 20 min reproduce + diagnostic, 20 min identify, 30 min fix + verify, 10 min close-out. Could stretch to ~2 h if H3 turns out to require non-trivial wfcrdt RAII surgery (the wfcrdt wrapper is small but every yrs FFI interaction is its own foot-shaped puzzle).

## Out of scope

- Multi-peer voice/video, screen share, dedicated Peers panel (still §B umbrella deferrals).
- Improving the relay protocol — the panic is on the editor side; the relay's frame is normal yrs v1 wire bytes.
