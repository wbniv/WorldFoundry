# Plan — A → E → B: audit follow-up, mailbox-999 fix, shared cursors

> Three sequential pieces from today's "what's next" menu: a one-liner audit follow-up
> (A), the mailbox-999 crash long known in the backlog (E), then shared cursors / better
> presence on the existing transport (B). Each commits independently.

## Context

- **A** is a follow-up the [2026-05-30 exception-usage audit](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-30-cpp-exceptions-audit.md) surfaced: `engine/stubs/debug_server.cc` calls `std::stod` inside a `try { … } catch (...)` that lives in the `-fno-exceptions` `wfengine` target. Clang accepts `catch(...)` under `-fno-exceptions` with a warning, so the catch has been silently no-op'd — `std::stod` failures bypass the guard and would have aborted the engine instead. Fix: switch to `std::strtod` (`errno`-based, doesn't throw), delete the try/catch.

- **E** closes [`project_followup_mailbox_999_crash`](../projects/-home-will-WorldFoundry/memory/project_followup_mailbox_999_crash.md): writing or watching mailbox `EMAILBOX_GLOBAL_USER_MAX` (1900 today, was 999 when the memory was written) aborts with `terminate called`. Exploration confirms it's an **off-by-one in allocation**: `mailbox.inc:104` makes `EMAILBOX_GLOBAL_SYSTEM_START = 1901` (so 1900 IS a valid user index — non-overlapping), but `wfsource/source/game/mailbox.cc:30` allocates `MAX − START` = 1900 slots (indices 0..1899). The bounds check at `mailbox.cc:81,98` (`mailbox < Size + Base`) then rejects 1900 and falls through to `AssertMsg(0, …)` at line 108 → `abort` → libstdc++'s `terminate called` print. Tests work around with `SENTINEL_MBX = 950` ([`tests/test_phase_b2.py:12`](../../WorldFoundry.2026-new-level/tests/test_phase_b2.py)). The new [`TerminateHandler`](../../WorldFoundry.2026-new-level/engine/wf_edit/main.cc) ships **today** — this fix is also the first end-to-end exercise of that diagnostic ladder on a real `terminate`.

- **B** extends the existing presence wire (CH_PRESENCE = 0x02, JSON passthrough, see [`relay.rs`](../../WorldFoundry.2026-new-level/wftools/wf_collab/src/bin/relay.rs)) to carry each peer's camera pose + selected-actor reference, then renders peer cursors in the 3D viewport (selection rings on the actor each peer is looking at, plus a small camera frustum) and upgrades the Chat-sidebar "presence dots" to per-peer tiles. **No new transport, no Yrs Awareness FFI work** — the relay already passes presence as opaque JSON; we widen the payload. The Yrs Awareness module exists in [`wftools/y-crdt/yrs/src/sync/awareness.rs`](../../WorldFoundry.2026-new-level/wftools/y-crdt/yrs/src/sync/awareness.rs) but isn't wrapped in yffi; that wrapping is bigger than the value of using it for ephemeral presence, and the JSON-on-CH_PRESENCE approach matches how chat already works (`CH_CHAT = 0x03`).

## A — `debug_server.cc` `std::stod` → `std::strtod` (~15 min including rebuild)

Two functions in [`engine/stubs/debug_server.cc`](../../WorldFoundry.2026-new-level/engine/stubs/debug_server.cc) use `std::stod`:

- `parse_jnum` at `:130` — bare call, no guard. A bad input would have thrown in a non-`-fno-exceptions` build and aborted today; in our `-fno-exceptions` `wfengine` target, `std::stod` may instead abort directly when failure-mode-via-exception is impossible. Either way, swap to `std::strtod` so failure is an `errno=ERANGE` / `endptr==start` outcome that returns 0.
- `parse_jvec3` at `:141-149` — wrapped in `try { … } catch (...) { return false; }`. The catch has been silently no-op under `-fno-exceptions`. Swap to `std::strtod` driven by an `endptr` chain, and return `false` if any leg fails to advance. Delete the try/catch.

Drop-in helper:

```cpp
static bool parse_double_at(const char* s, double* out, char** endp) {
    errno = 0;
    char* end = nullptr;
    double v = std::strtod(s, &end);
    if (end == s || errno == ERANGE) return false;
    *out = v;
    if (endp) *endp = end;
    return true;
}
```

Then `parse_jvec3` becomes three sequential `parse_double_at` calls, advancing past the comma between each, returning `false` on the first failure. `parse_jnum` becomes one call (with a 0.0 default on failure to match its current contract).

**Verification:**
- Build the `wfengine` target with **Release + Clang** *and* `WF_DEBUG_BRIDGE=ON` to confirm the changed file compiles without the previous silent warning. (`cmake --preset release -DWF_DEBUG_BRIDGE=ON` if a preset exists; else `cmake -B build-release-clang -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ -DWF_DEBUG_BRIDGE=ON`.) This is the configuration the audit flagged as latently broken.
- Build the normal Debug + bridge config (`task build` after `touch engine/stubs/debug_server.cc`) and confirm a debug-bridge test still passes — e.g. `tests/test_phase_b2.py` (already exists, exercises `set_mailbox` with numeric JSON).
- Flip `TODO.md`'s BUILD SYSTEM row from `[ ]` to `[x]` linking the commit, leave the `[investigated]` audit row in place.

## E — Mailbox-999/1900 off-by-one (~1 h including regression test)

### Root cause

Three files, three lines:

| File | Line | Today | Intent |
|---|---|---|---|
| `wfsource/source/mailbox/mailbox.inc` | `:8` | `EMAILBOX_GLOBAL_USER_START = 0` | First valid user index = 0 |
| `wfsource/source/mailbox/mailbox.inc` | `:96` | `EMAILBOX_GLOBAL_USER_MAX = 1900` | Last valid user index = 1900 (system starts at 1901, no overlap) |
| `wfsource/source/game/mailbox.cc` | `:30` | `MailboxesWithStorage(START, MAX - START, …)` | Allocate `1900` slots — **wrong, want 1901 to include index 1900** |

The `_MAX` constant is **inclusive** (the comment at `:101` says "Must remain strictly less than GLOBAL_SYSTEM_START to avoid overlap" — i.e. 1900 < 1901 → 1900 is user). Allocation should be `MAX − START + 1`. Same shape for whichever sibling MailboxesWithStorage call sizes the system range.

### Fix

```cpp
// wfsource/source/game/mailbox.cc:30
MailboxesWithStorage(EMAILBOX_GLOBAL_USER_START,
                     EMAILBOX_GLOBAL_USER_MAX - EMAILBOX_GLOBAL_USER_START + 1,
                     parent),
```

Plus the same `+ 1` for the system MailboxesWithStorage if its sizing is parallel — confirm at edit time.

Add a one-line comment at `mailbox.inc:96` cementing the inclusive interpretation so this doesn't drift again:

```
Comment(" *Inclusive* last valid index — user range is [START, MAX]. Storage allocator must use MAX - START + 1. ")
```

The `AssertMsg(0, …)` at `mailbox.cc:108` stays — it's now correct behaviour for genuinely out-of-range writes (e.g. an off-by-one in a *script*, not the engine). Improve its message to print the offending index and the valid range so the next bounds violation is self-diagnosing.

### Regression test

Add `tests/test_mailbox_global_bounds.py` (Python bridge test, same shape as the existing `tests/test_phase_b2.py`) that:

1. Boots the engine on any level (snowgoons is smallest).
2. Sets `EMAILBOX_GLOBAL_USER_MAX` (1900) via `set_mailbox`, reads it back, asserts equal.
3. Sets `EMAILBOX_GLOBAL_USER_MAX + 1` (1901, the system region), expects either a bounds error in the bridge response or — if the system region is fully writable — a write that doesn't crash.
4. Sets `EMAILBOX_GLOBAL_USER_MAX + 100` (deep into invalid space), expects a bounds error and the engine to **stay alive** (no abort).

If the bridge currently has no "bounds error" return code, the test asserts engine-still-alive (the `TerminateHandler` would print a backtrace if not). The 950 sentinel in `test_phase_b2.py` can stay as a defensive habit but the comment-rationale changes.

### Verification

- Run the new test: `python3 tests/test_mailbox_global_bounds.py` — passes.
- Existing bridge tests still pass (`task test-bridge` or whichever umbrella exists).
- Confirm the original symptom is gone by writing `set_mailbox 1900 42` through the bridge interactively and reading it back.

### Mark the memory

Update [`project_followup_mailbox_999_crash`](../projects/-home-will-WorldFoundry/memory/project_followup_mailbox_999_crash.md) with the resolution (fix commit + constant=1900 today not 999), and remove or convert the `[ ]` TODO line to `[x]`.

## B — Shared cursors / better presence on CH_PRESENCE (~1 day)

### What ships

1. **Each peer broadcasts their camera pose + selected actor every ~10 Hz**, in the existing CH_PRESENCE (0x02) JSON. No relay or protocol change.
2. **The 3D viewport draws each remote peer's selection** as a coloured outline ring (peer's stable colour) on the actor whose EID matches their `selected_eid`.
3. **The 3D viewport draws each remote peer's camera frustum** as a small coloured wireframe pyramid in world space — see-at-a-glance "where is each peer looking from".
4. **The Chat sidebar's presence list upgrades from dots to tiles** — colour swatch, name (from `identity.display_name`, currently hardcoded "Editor"), what they're looking at ("→ Mario.001"), and a "Jump to view" button that teleports the local editor camera to their pose.

### Payload extension (CH_PRESENCE JSON)

Today (`main.cc:1156-1177`):
```json
{ "peer_id": "...", "name": "Editor", "colour": [r,g,b], "selected_eid": "..." }
```

After:
```json
{
  "peer_id": "...", "name": "Alice", "colour": [r,g,b],
  "selected_eid": "...",
  "cam_pos": [x,y,z],
  "cam_fwd": [x,y,z],
  "cam_up":  [x,y,z]
}
```

`cam_fwd` + `cam_up` is full orientation (right is the cross product), avoids a quaternion library and matches WF's existing matrix-row conventions. Older peers drop the unknown fields silently — the parser at `main.cc:509-598` already tolerates absent keys.

### Code touchpoints (all in `engine/wf_edit/`)

| Piece | File:Line | Change |
|---|---|---|
| `PresenceState` struct | `main.cc:331-351` | Add `float cam_pos[3]`, `cam_fwd[3]`, `cam_up[3]` |
| Broadcast | `main.cc:1156-1177` | Pull pose from `theLevel->camera()->GetRenderCamera().GetPosition()` (a `Matrix34`; pos = row 3, fwd = row 0 or -row 2 per engine convention — confirm against `gizmo.cc:73-114`'s `BuildGizmoMats`), serialize into the JSON |
| Parse | `main.cc:509-598` (`CollabDrain`) | Read `cam_pos` / `cam_fwd` / `cam_up` if present |
| Viewport draw — selection rings | new function called from the same place `gizmo.cc` draws its rings (`ImGui::GetForegroundDrawList()` after `ImGuizmo::BeginFrame`) | For each peer with a non-empty `selected_eid`, find the engine ActorIdx via the existing EID↔ActorIdx map (`engine_bridge.h:32-128`), look up the actor's world position, project to NDC with the same view+proj used by ImGuizmo, draw a coloured ring |
| Viewport draw — frustums | same place | Build 8-vertex wire pyramid in world (cam_pos + scaled fwd/up/right) → project each vertex → `AddLine` |
| Sidebar tiles | `main.cc:1706-1713` | Replace the `TextColored("● %s", …)` block with a per-peer `BeginGroup` showing swatch + name + selected actor name + "Jump to view" `ImGui::SmallButton` |
| "Jump to view" handler | new helper called from the sidebar button | Write the peer's `cam_pos` / `cam_fwd` / `cam_up` into the editor's own camera state (same mutation path the gizmo uses for the engine cam) |
| Personalised name | `main.cc:~1167` | Use `identity.display_name` if set, else fall back to "Editor" or the first 8 chars of `peer_id`; surface a one-line `Settings → Display name` ImGui input next to the existing identity fields |

### Reused, not built

- **Colour assignment:** `PeerColourFromId` (`main.cc:482-489`) — stable hash → colour, already deterministic, no change.
- **Camera matrix construction:** `BuildGizmoMats` (`gizmo.cc:73-114`) — already extracts pos+orientation from the engine camera each frame; the broadcast can call the same path, no new math.
- **Selection lookup:** the existing EID↔ActorIdx map (`engine_bridge.h:32-128`) maps peer's `selected_eid` to a live actor — no new index needed.
- **Foreground drawlist:** ImGuizmo already uses `ImGui::GetForegroundDrawList()` for its handles; selection rings + frustums sit on top with no extra overlay setup.
- **CH_PRESENCE channel:** unchanged on the relay side (`wftools/wf_collab/src/bin/relay.rs:33-45`) — it passes 0x02 frames opaquely; the wider JSON flows through.

### ASCII mockup of the sidebar after the change

```
┌─ Peers (3) ────────────────────┐
│ ●  Alice     → Mario.001       │
│    cam: (-3.2, 12.0, 4.5)      │
│    [Jump to view]              │
│ ●  Bob       → Coin.014        │
│    cam: ( 8.1,  1.2, 6.0)      │
│    [Jump to view]              │
│ ●  you       → Goomba.002      │
│    (this editor)               │
└────────────────────────────────┘
```

Coloured dots become coloured tiles; existing chat panel stays in the same window below.

### Verification

- **Headless smoke:** start two `wf-edit` instances against the local `task quick-tunnel` link (the existing two-editor recipe in [`docs/wf-edit-manual.md`](../../WorldFoundry.2026-new-level/docs/wf-edit-manual.md)) with distinct `XDG_CONFIG_HOME`. Move the camera in one, watch the other render a moving frustum. Select an actor in one, watch the other render a coloured ring around it.
- **Screenshot proof** per `feedback_screenshots_for_proof`: capture both editor windows side-by-side showing peer A's view + peer B's frustum visible inside it, plus the upgraded sidebar.
- **Behaviour with no remote peer:** sidebar shows only the local "(this editor)" tile; no frustums; no rings.
- **Backwards compat:** an older peer (pre-this-change) joining still gets parsed correctly — the missing `cam_pos` etc. cause that peer to show name + selection but no frustum + no jump button.
- **Jump-to-view:** click "Jump to view" on a peer tile, confirm local cam snaps to that pose (within rounding).

### Out of scope (explicit non-goals)

- **Yrs Awareness via yffi.** The Rust crate has `awareness.rs` ready, but adding the C-FFI wrapping for an ephemeral feature is more work than the JSON-on-CH_PRESENCE approach already in place. If a later feature needs true awareness semantics (durable cursor-replay-on-join, conflict-aware presence merging), wrap then.
- **Shared mouse-hovered actor** (lighter signal than selection). Could be added cheaply on the same payload later if peers ask for it.
- **Audio/video tile-attach.** Voice/video calls already work; the peer tile is a natural future home for a per-peer mute toggle, but that's a separate small plan.
- **Screen share** as a third media track. Mentioned in the menu as a different next-arc option; not in this plan.

## Order + commit gates

1. **A** — one PR-shaped commit: `fix(debug-bridge): replace std::stod with std::strtod under -fno-exceptions`. Update `TODO.md`. Verify Release-Clang+bridge-on build is now warning-clean.
2. **E** — one commit: `fix(mailbox): allocate MAX - START + 1 slots so EMAILBOX_GLOBAL_USER_MAX is writable`. Includes the new bridge test + the inclusive-comment + the AssertMsg message upgrade + the memory file flip. **The TerminateHandler shipped today is the first-time tool that would have made root-causing this trivial — note that in the commit body as the diagnostic-handler's first win.**
3. **B** — likely 2 commits to stay reviewable: (b1) payload + broadcast + parse + sidebar tiles; (b2) viewport rings + frustums + Jump-to-view + display-name plumbing. Plan doc + manual update + screenshot land with b2.

## Notes

- Sizing, *average-programmer scale*: A ≈ 15 min; E ≈ 1 h; B ≈ 1 day (b1 ≈ ½ day, b2 ≈ ½ day).
- Each piece is independent — A can ship even if E surfaces something unexpected; B doesn't depend on either.
- Doc lands with code per `feedback_commit_docs_with_code`.
- B's screenshots land alongside the b2 commit per `feedback_screenshots_for_proof` and `feedback_proactive_mockups`.
