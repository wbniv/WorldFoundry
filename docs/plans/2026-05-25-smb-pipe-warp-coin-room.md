# SMB pipe warp → underground coin room

**Status:** Phase A DONE 2026-05-25 (cross-room warp + room switch + per-room light + camera-follow, bridge-verified [tests/verify_smb_pipe_warp.py](../../tests/verify_smb_pipe_warp.py) ALL PASS); Phase B (coins + exit Warp) remaining. Camera pan-settle is real-time-fps-dependent — polish tracked in TODO.

### Implementation notes (2026-05-25)

Five bugs found and fixed during Phase A, all now captured in
[level-design-troubleshooting.md § Multi-room levels](../level-design-troubleshooting.md#multi-room-levels--cross-room-warps-the-smb-pipe-warp):

1. Player lacked `Moves Between Rooms` → vanished on the switch.
2. Coin room rendered black → each room needs its own light.
3. Camera froze at the surface pose on a hard switch → rooms must be **mutually adjacent** so both stay active (the camera is updated only via the active room's update list).
4. `EMAILBOX_CAMSHOT` is **1921**, not 1021 (the doc table was wrong) → ActBoxOR was writing a junk slot.
5. The "ActBoxOR doesn't fire with scripting disabled" doc claim is false (it fires via C++ overlap) — verified and corrected.
**Date:** 2026-05-25
**Level:** `wflevels/smb_w1_1/`
**Touches:** `wflevels/smb_w1_1/blender_create_smb.py` (level authoring), `wfsource/source/mailbox/mailbox.inc` (one new mailbox), build pipeline. **No C++ logic changes** — pure composition of live actor classes.

> **Standing directive (level-authoring):** the moment a gotcha, technique, or hack
> surfaces during this work, write it to
> [docs/level-design-troubleshooting.md](../level-design-troubleshooting.md) (or
> [docs/level-building.md](../level-building.md)) — mid-execution, not batched at the
> end. This is the first genuinely multi-room WF level; the room-transition gotchas
> found here are the whole point and must be captured for the levels that follow.

---

## Goal

Add an SMB-faithful **pipe warp**: Mario stands on a surface pipe, presses **Down**,
and descends into a separate **underground coin room**; he collects coins and walks
into an **exit pipe** that warps him back up to the surface, deposited just past the
entry pipe.

W1-1 is small enough to live in one room — it does *not* technically need WF's
room-streaming machinery. We build the coin room as a **genuine second `room` actor**
anyway, because the real deliverable is to **exercise and prove the room-to-room
transition path** that every later, bigger level needs. This is a training ground.

---

## What was verified in the engine (so the plan doesn't hedge)

| Claim | Evidence |
|-------|----------|
| **Cross-room warp works** — teleporting the player into a *disjoint* room's bbox triggers a real room switch | `ActiveRooms::UpdateRoom()` ([actrooms.cc:293](../../wfsource/source/room/actrooms.cc)) checks `!_activeRooms[0]->CheckCollision(watchObject)`, then loops **all** rooms (`for roomIndex 0..numRooms`) and `ChangeActiveRoom()` to the first whose bbox contains the player. **Not** adjacency-gated. |
| The switch follows the **player** | `UpdateRoom` is called with `_camera->GetWatchObject()` ([level.cc:942](../../wfsource/source/game/level.cc)); the SMB camera tracks `Player`. |
| The player **survives** the switch frame | `Room::UpdateRoomContents` ([room.cc:266](../../wfsource/source/room/room.cc)) removes the fallen-out player and calls `levelRooms.AddObjectToRoom()`, which re-homes it to whatever room now contains it. Prints one harmless `fell out of room … re-adding` line per transition. Only crashes if **no** room contains the player ([rooms.cc:166](../../wfsource/source/room/rooms.cc)). |
| Room capacity is sufficient with **zero engine change** | `MAX_ACTIVE_ROOMS = MAX_ADJACENT_ROOMS + 1 = 3` ([assets.hp:39](../../wfsource/source/asset/assets.hp)); AssetManager pre-allocates all 3 slots regardless (see parked [per-level-max-active-rooms plan](2026-05-17-per-level-max-active-rooms.md)). |
| Multi-room + adjacency is **already supported by the toolchain** | `levcomp-rs` resolves `Adjacent Room 1/2` OAD fields by name into room indices ([rooms.rs:121-148](../../wftools/levcomp-rs/src/rooms.rs)); sorts actors into rooms by bbox-center containment. |
| The player already **moves between rooms** | `coin_template` sets `Moves Between Rooms = True` ([blender_create_smb.py:605](../../wflevels/smb_w1_1/blender_create_smb.py)); the player must too (see Risks). |
| **Two Jolt-safe teleport paths exist** | (1) script `X/Y/Z_POS` mailbox write — already proven by the respawn at [blender_create_smb.py:755-757](../../wflevels/smb_w1_1/blender_create_smb.py); (2) the `Warp` actor's `SetPredictedPosition` — committed via `PhysicalAttributes::Update()` which **explicitly lists "warps"** as a WF-authoritative mutation pushed to `JoltCharacterSetPosition` ([jolt/physical.hpi:10-35](../../wfsource/source/physics/jolt/physical.hpi)). |

### The one nuance, explained: why entry ≠ exit

The `Warp` class is **collision-only**. `Warp::update()` ([warp.cc:75-95](../../wfsource/source/game/warp.cc)) teleports *any* actor that overlaps its activation volume — there is **no input gate**. So:

- **Exit pipe** (walk-into, no button): a **pure `Warp` + `Target`**. Mario walks into the exit pipe's mouth → teleport. Exactly the user's "both classes are live, pure composition" case, and it validates the `Warp` class's Jolt teleport.
- **Entry pipe** (must press Down): the `Warp` can't gate on Down, so the entry uses a co-located **`ActBox` sensor + a Down-press check in the player's existing per-tick script**, reusing the proven respawn teleport. This *is* the "press-down at the rim" nuance the brief named.

---

## Layout (side view, camera looks +Y; screen plane is X-Z)

```
  SURFACE ROOM  (existing, world  X[-66..134]  Z[-10..25])
  ───────────────────────────────────────────────────────────────────────────
                         ┌──┐  entry pipe (statplat, X≈18, top Z=3)
                         │  │  ← ActBox "pipe_entry_sense" at the mouth
   ███████████████████████  ██████  ground_0/1/2 (Z top = 0)
   Mario ▶                ▲ press DOWN
                          ┊
        (player-script Down-gate teleport — X/Y/Z_POS write)
                          ┊
                          ▼
  ════════════════ disjoint Z gap (-38 .. -10) ═══════════════════
                          ┊
  UNDERGROUND COIN ROOM  (NEW room, world  X[-2..26]  Z[-58..-38])
  ───────────────────────────────────────────────────────────────────────────
        ● ● ● ● ●  coins (collect → GOLD/HUD_SCORE)              ┌──┐ exit pipe
                                                          ▶ walk │  │ ← Warp vol
   ██████████████████████████████████████████████████████████████  CR floor (Z top=-48)
        ▲ land here (entry Target, X≈3)         Warp Target ───────┘
                                                (surface return, X≈24, Z=1.5)
```

Two **disjoint** bboxes (the Z ranges never overlap → the room switch fires). The
coin room sits straight below; because the surface camera's Z is **Absolute** it
will *not* follow Mario down — so the coin room gets its **own** CamShot.

### Camera framing — two shots, switched by an ActBoxOR zone

```
  cs_side  (existing): Track=Player, X=Relative (Director scroll), Y/Z=Absolute
           → side-scroll over the surface

  cs_coin  (NEW):      static shot framing the whole coin room
           pos (12,-30,-45), Target = coin-room look-at
           activated by ActBoxOR "abor_coin" whose volume fills the coin room
           (same pattern as the existing actboxor → cs_side)
```

When Mario is in the coin room he's continuously inside `abor_coin`'s volume, which
re-writes `EMAILBOX_CAMSHOT` (1021) to `cs_coin` every frame. Back on the surface the
existing `actboxor` re-asserts `cs_side` and the Director's scroll resumes.

---

## Coordinates (all derived from `T = 1.5`, `GROUND_TOP_Z = 0`, `CAM_Y = -30`)

| Thing | World position / extent | Notes |
|-------|------------------------|-------|
| Entry pipe (statplat) | centre X=18 (tile 12), occupies X[16.5,19.5], Z[0,3] | 2 tiles wide × 2 tall, on `ground_0` before pit 1; green |
| `pipe_entry_sense` (ActBox) | centre (18, 0, 3.4), half (1.5, GROUND_Y, 0.6) | thin lid over the pipe mouth; `Activated By Actor=Player`, `MailBox=1809`, `MailBoxValue=1`, `ClearOnExit=1`/exit value 0, `Activated Actor Mailbox=4005` (scratch — see ActBox gotcha) |
| Coin-room floor (statplat) | top Z=-48, slab X[-2,26], Z[-49.5,-48], Y±GROUND_Y | brown |
| Coin-room walls + ceiling | enclose X[-2,26], Z up to ≈-40 | keep Mario contained; statplat |
| Entry landing `Target_cr_entry` | (3, 0, -46.5) | feet -48 + T drop-in, mirrors surface spawn |
| Coins | row at Z≈-46, X = 6,9,12,15,18 | collectibles (see coin sub-decision) |
| Exit pipe (statplat) | centre X=22.5 (right side), X[21,24], Z[-48,-45] | green |
| `pipe_exit_warp` (Warp) | volume at exit-pipe mouth, centre (22.5, 0, -46), half (1.0, GROUND_Y, 1.0) | `Activated By Actor=Player`, `Target=Target_surface_return` |
| `Target_surface_return` | (24, 0, 1.5) | surface, ~4 units right of the entry pipe → no instant re-trigger |
| Coin-room `room` actor | centre (12,0,-48), bbox rel (-14,-35,-10, 14,10,10) → world X[-2,26] Y[-35,10] Z[-58,-38] | **disjoint** from surface room in Z |
| `cs_coin` (CamShot) | pos (12,-30,-45), Track=Player or static, Target=coin-room look-at | frame the whole room |
| `Target_cr_lookat` | (12, 0, -46.5) | cs_coin look-at |
| `abor_coin` (ActBoxOR) | volume filling coin room interior, `Object=cs_coin`, `Activated By Actor=Player` | camera-zone switch |
| **Surface room** | extend Z-min only if needed; it is `Z[-10,25]` today | **must not** overlap coin room — it doesn't (gap -38..-10) ✓ |
| Rooms adjacency | surface `Adjacent Room 1=<coin room>`, coin `Adjacent Room 1=<surface>` | mutually adjacent → both stay loaded, hitch-free transition, within the 3-slot budget. (Alternative for true streaming: leave non-adjacent so the far room unloads — documented for big levels.) |

### New mailbox

```
MAILBOXENTRY( SMB_AT_PIPE, 1809 )  Comment("entry ActBox sets 1 while player is on the pipe mouth; player script + Down -> warp to coin room")
```

Added to [mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) after `SMB_TIMER_START` (1808).
> Note the verbose `INDEXOF_` prefix the scripting side still requires
> ([`feedback_indexof_prefix_wanted_gone`]) — following the convention here, flagged
> for the eventual migration, not silently propagated as ideal.
> **Build gotcha:** editing only `mailbox.inc` relinks a *stale* `scripting_stub.o`;
> `touch engine/stubs/scripting_stub.cc wfsource/source/mailbox/mailbox.cc` then
> `task build`, and confirm `strings engine/wf_game | grep INDEXOF_SMB_AT_PIPE`.

### Player-script Down-gate (appended to the existing player `Script` body)

The existing player script is one `if/then` body with no `:`/`;`, so the whole thing
is wrapped in the auto-generated `: _wfsN … ;` (compile mode) — `if/then` is legal
here. Append:

```forth
( pipe-enter: standing on a pipe mouth + Down pressed -> drop into the coin room )
INDEXOF_SMB_AT_PIPE read-mailbox 0<> if
  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox 4096 & 0<> if   ( DOWN = EJ_BUTTONF_DOWN = 0x1000 = 4096 )
    3 INDEXOF_X_POS write-mailbox
    0 INDEXOF_Y_POS write-mailbox
    -46.5 INDEXOF_Z_POS write-mailbox
    0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox 0 INDEXOF_ZSPEED write-mailbox
  then
then
```

(zForth: `&` not `and`; `4096` literal, not `0x1000`, to be safe with the tokenizer.)

---

## Phases

### Phase A — second room + cross-room warp proven (core training deliverable)

1. Add `SMB_AT_PIPE = 1809` to `mailbox.inc`; rebuild engine (touch + `task build`; verify `strings`).
2. In `blender_create_smb.py`: build the **coin-room** geometry (floor + 4 walls + ceiling statplats), the **entry pipe** statplat, the **`pipe_entry_sense` ActBox**, the **second `room` actor** (disjoint bbox), wire **`Adjacent Room 1`** both ways, and add the **`Target_cr_entry`** marker.
3. Add the **cs_coin** CamShot + **`Target_cr_lookat`** + **`abor_coin`** ActBoxOR for camera framing.
4. Append the **Down-gate** block to the player script.
5. Build (`build_level_binary.sh smb_w1_1`) + standalone; run under the bridge.
6. **Verify:** press Down on the pipe → Mario appears in the coin room, `cs_coin` frames it, exactly one `fell out of room … re-adding` line, no crash, no `not in any room`. Bridge `--debug-print-actors` to map indices; screenshot surface-before and coin-room-after.

### Phase B — coins + exit warp back to surface

7. Place collectible coins in the coin room (sub-decision below) and confirm `GOLD`/`HUD_SCORE` increments on pickup.
8. Add the **exit pipe** statplat + **`pipe_exit_warp` Warp** + **`Target_surface_return`**.
9. **Verify:** collect coins (score rises), walk into the exit pipe → warp to the surface ~4 units right of the entry pipe, camera returns to `cs_side` scroll, no re-trigger loop. Screenshot the full round trip.

**Coin sub-decision (Phase B):** the actor inventory lists `Gold` as *template-only —
spawned, not placed directly*. First try **pre-placed `gold` actors** in the room; if
the proximity-pickup/`kind()` path misbehaves for a directly-placed `Gold`, fall back
to a one-shot `Generator` per coin (the proven `?`-block path). Flagged as a risk, not
assumed solved.

---

## Risks & gotchas (watch list)

1. **Player needs `Moves Between Rooms = True`.** Verify the player sets it; without it the player's assets unbind when `ChangeActiveRoom` swaps the surface room out → invisible/crash. (`coin_template` already sets it; the player is the one that *must*.)
2. **Bboxes must stay disjoint.** The surface room is huge in X/Y; only the **Z gap (-38..-10)** keeps them apart. Don't let the coin room creep above Z=-10, and don't extend the surface room's Z-min below -10.
3. **One-frame "fell out of room" print** is expected and harmless on each transition (the re-add succeeds). Only a `not in any room` line means the destination coords missed the coin-room bbox — fix the coords, not the engine.
4. **Camera-zone overlap during transition.** For the handful of frames where both ActBoxOR volumes might briefly claim the player, `EMAILBOX_CAMSHOT` may flicker. Keep the two ActBoxOR volumes spatially disjoint (they are — different rooms) so only one is ever active.
5. **`?`-block coins live in the surface room** (`coin_template` parked at X=-50, inside the surface bbox) — leave them; the coin-room coins are separate actors.
6. **Actor indices shift.** Adding ~12 actors renumbers everything; never hand-count — read `--debug-print-actors` before trusting any `write-actor-mailbox` literal (none planned here, but the Director/camshot bootstrap is index-sensitive).
7. **Re-export name overrides.** `blender_create_smb.py` imports snowgoons; every new object-reference field (`Target`, `Object`, `Activated By Actor`, `Adjacent Room 1`) must be set explicitly by name in the script — imported values won't resolve (see designer guide "stale object names").

---

## Verification

- Runtime via the debug bridge: `task run-debug -- wflevels/smb_w1_1-standalone.iff`, watch `SMB_AT_PIPE`, `GOLD`, player `X/Z_POS`, and the active-room/camshot transitions.
- **Screenshots (required as proof):** (a) Mario on the surface pipe, (b) Mario in the coin room with `cs_coin` framing + coins, (c) back on the surface after the exit warp. Place them beside the ASCII mockups above when captured.
- Engine stderr clean except the expected single `re-adding` line per transition and any benign `RenderActor3DAnimates: no animations`.

---

## Out of scope / follow-ups

- Pipe-descend animation (Mario sliding into the pipe) — instant teleport for now.
- Multiple warp pipes / a warp-zone level (W1-2) — this proves the pattern; the big multi-room level is the consumer.
- `Pole`/`Meter`/`Movie` dead stubs — untouched.
