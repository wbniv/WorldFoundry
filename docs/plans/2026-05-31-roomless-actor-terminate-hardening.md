# Roomless-actor → `terminate` hardening (PARKED)

**Status:** **Parked / not started — 2026-05-31.** The specific trigger is already
prevented (gold-room sense-box fix, commit `8fff914e`). This documents a *latent*
engine fragility and a recommended fix for if/when it's prioritized. Open question:
whether it's worth fixing at all, given the trigger is gone.

## Context

While building the full W1-1 playthrough, the engine `terminate`d on a run where the
player got stranded outside every room: a failed pipe-warp left Mario at ≈`(70.5, −4.7,
−12.4)` — below the surface room's Z floor *and* beyond the coin room's X — so no room's
bbox contained him.

Two things were initially conflated and are worth separating:

- **The "post-flagpole crash" is NOT a crash.** Reaching the flagpole sets `END_OF_LEVEL`
  → `_curLevel->done() = 1` → the main loop exits and the engine shuts down *cleanly*
  (`rest_api: server stopped`, `Tasker shutting down`). The playthrough harness just
  didn't expect the engine to exit on level completion and reported the closed socket as
  a `BrokenPipe`. That's a harness expectation gap, not an engine bug.
- **The real latent bug** is the roomless-actor path below.

## The traced chain (all verified in-tree)

1. An actor at a position contained by no room → `Room::UpdateRoomContents`
   ([room.cc:266-291](../../wfsource/source/room/room.cc)) logs "fell out of room … re-adding",
   does `RemoveObject` then `LevelRooms::AddObjectToRoom`.
2. `LevelRooms::AddObjectToRoom` ([rooms.cc:128-192](../../wfsource/source/room/rooms.cc)):
   no room contains it → `roomnum < 0` → `_roomCallbacks->SetPendingRemove(object)`
   (lines 185-189) — "left all rooms, kill it." Correct for a stray collectible;
   **catastrophic for the player.**
3. `Level::SetPendingRemove` ([level.cc:1337-1381](../../wfsource/source/game/level.cc)):
   already refuses to remove the **camera** (1348-1352) but **not the player**; also
   `assert(_numToBeRemovedObjects < 99)` at 1363.
4. Any assert here → `_sys_assert` → **bare libc `exit(-1)`** (`assert.cc:34` — *not*
   `sys_exit`, so `sys_atexit`-registered stops do **not** run) → static `std::thread`
   (`engine/stubs/debug_server.cc` `gListenerThread`, `engine/stubs/rest_api.cc`
   `gServerThread`) destroyed while still **joinable** → `std::terminate` (SIGABRT). The
   thread destructor is a *misleading* top-of-stack that masks the real assert — same
   footgun as [docs/BUGS.md:42](../BUGS.md) (2026-05-20) and
   [docs/investigations/2026-05-25-wf-edit-statplat-move-abort.md](../investigations/2026-05-25-wf-edit-statplat-move-abort.md).

Room geometry note: surface room `X[−8,327.5] Z[−10,25]`, coin room `X[−4,28] Z[−58,−10]`
— **contiguous at Z=−10 (no gap)**. The roomless region is the *corner*: surface-X ∧
below-surface-Z, beyond the coin room's X. So this is a thin transient sliver, not a hole
under normal play.

## Recommended fix (layered; ~0.5–1 day for an average dev incl. a regression test)

**L1 — root cause (essential).** In `LevelRooms::AddObjectToRoom` (rooms.cc:185-189), when
`roomnum < 0`, for the player / `Moves Between Rooms` actors **re-add to the nearest room**
(by bbox distance to `po`'s position; fallback `_rooms[0]`) instead of `SetPendingRemove`,
and emit a `cerror` warning so the underlying geometry/warp bug stays visible. Non-permanent
actors keep despawning (intended). Predicate (both locals already in scope at the site):
`object->kind() == BaseObject::Player_KIND || po->GetMovementBlockPtr()->MovesBetweenRooms`.
Mirrors the camera-refusal (level.cc:1348) and the `gEditorMode` softening gate (rooms.cc:147).
Keeping the actor *in a room* avoids orphaning it (it would otherwise be removed from its old
room by `UpdateRoomContents` and added to none → no updates); physics/warp pulls it back into
the right room within a frame or two.

**L2 — defensive (essential).** In `Level::SetPendingRemove` (level.cc:1363), replace
`assert(_numToBeRemovedObjects < 99)` with a guarded early-return + `DBSTREAM1(cwarn …)`
(mirror the camera early-return at 1348-1352), gated on the true `_toBeRemovedObjects`
capacity (confirm in `level.hp`). Removes the last `exit(-1)` on this path if a cascade ever
fills the queue.

**L3 — symptom / recurring footgun (essential).** **Detach** the static listener threads —
`gListenerThread` (`debug_server.cc`; drop the join in `DebugServer_Stop`) and `gServerThread`
(`rest_api.cc`; drop the join in `RestApi_Stop`) — so any *future* `exit(-1)`/assert prints
the real message instead of a masked `terminate`. Safe: both loops block in `accept`/`recv`
(no level-state access on teardown) and per-frame state mutation runs on the game thread; the
clean-shutdown `*_Stop()` still closes the socket (SO_REUSEADDR already set). **Note:** because
`_sys_assert` → `exit(-1)` bypasses `sys_atexit`, "register the stop earlier" is a non-fix —
detach is the correct prevention. Optional (diagnostics only): also install
`std::set_terminate(TerminateHandler)` in `wfsource/source/game/main.cc`, mirroring
`engine/wf_edit/main.cc:2219-2246`.

## Verification

New headless bridge test (mirror `tests/verify_wfmut_bridge.py` + `tests/debug_bridge_client.py`):
launch `engine/wf_game -L wflevels/smb_w1_1-standalone.iff --debug-port …`, discover the player
idx, teleport the player **and** a `Moves Between Rooms` actor to a roomless point (e.g.
`X=200, Z=−20`, or `X=70.5, Z=−12`), step ~30-60 frames, then assert:
- process still alive; log has no `"terminate called without an active exception"` / no `"ASSERTION FAILED"`;
- the new L1 "pinning to nearest room" warning is present (proves the repro stranded the actor and the guard caught it);
- the player keeps receiving `state` broadcasts (proves it wasn't orphaned).
Inverse check: a teleported **non-permanent** collectible still despawns ("Removing object … not in any room"). Add as a CTest (mirror `CMakeLists.txt` `wfmut_bridge`).

## Files

| File | Layer |
|---|---|
| `wfsource/source/room/rooms.cc` (`AddObjectToRoom` ~185-189) | L1 |
| `wfsource/source/game/level.cc` (`SetPendingRemove` ~1363) | L2 |
| `engine/stubs/debug_server.cc`, `engine/stubs/rest_api.cc` (detach listeners) | L3 |
| `wfsource/source/game/main.cc` (`set_terminate`) | L3 (optional) |
| `tests/verify_roomless_actor.py` (new) + `CMakeLists.txt` (CTest) | verification |

## Out of scope but noted

- **Harness fix (separate, tiny):** `tests/run_smb_w1_1_playthrough.py` should treat the
  engine exiting on flagpole touch (`END_OF_LEVEL` → level done) as *expected completion*
  and stop gracefully, rather than surfacing the closed socket as a `BrokenPipe`.
- `rest_api.cc` `json_float` uses `std::stof` (throws under `-fno-exceptions`) — a separate
  latent input-validation issue surfaced during the investigation; harden if the REST API
  is ever exposed to untrusted callers.
