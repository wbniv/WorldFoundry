# SMB classic scrolling camera

## Context

`wflevels/smb_w1_1/blender_create_smb.py` (lines 11, 17) currently configures a **fixed all-Absolute** CamShot centred on Mario's spawn (X=4.5). The level extends to X≈70.5; Mario walks off-screen past ~X=15. The script's header explicitly flags scrolling as a deferred milestone — this is that milestone.

Target behaviour (classic NES SMB):
- Horizontal scroll only (Y and Z locked).
- **Deadzone** — small horizontal window inside which Mario can move without scrolling.
- **One-way scroll** — once camera has advanced right, it never retreats.
- **Level-edge clamp** — camera X clamped so the frustum never shows void past `[ground_X0, ground_X1]`.
- **Forward lead ≈ 1 tile (T = 1.5 m)** — Mario sits left of centre when scrolling.

This plan implements the scrolling in pure Forth — Director script + signal-mailbox pattern — with zero engine code. The engine-side alternative (per-CamShot OAS fields + inline branch in `NormalCameraHandler::_update`) is fully designed and parked at [`docs/plans/2026-05-17-smb-scroll-engine-route.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-17-smb-scroll-engine-route.md). Parked until a new level ships — once SMB W1-1 (or whichever level next reaches shipped state) is out the door, we migrate to the engine route.

---

## Approach: Director-driven CamShot via signal mailbox

Three actors collaborate via shared global mailboxes:

1. **Player script** broadcasts its own world X to a global mailbox each tick. The player already reads its own `X_POS` mailbox (slot 3009, `wfsource/source/mailbox/mailbox.inc:58`) implicitly via the engine; add one Forth line that pushes it to a `GLOBAL_USER` slot.
2. **Director script** runs every tick (verified: `wfsource/source/game/actor.cc:919-927`). Each tick it reads `PLAYER_X` and computes the SMB-shaped target camera X (deadzone + one-way ratchet + edge clamp + forward lead), then writes the result to a second global slot `TARGET_CAM_X`.
3. **CamShot script** reads `TARGET_CAM_X` each tick and writes it to its own `INDEXOF_X_POS` (slot 3009) — moving itself. The engine reads the CamShot's position next tick via `SetCameraParametersFromShot()` (`wfsource/source/game/movecam.cc:225-229`), producing smooth scrolling.

This **signal-mailbox pattern** is the architecturally clean way to do cross-actor effects in WF — each actor owns its own local state, and the Director communicates intent through globals rather than reaching into other actors. Documented in [`docs/level-building.md`](../../WorldFoundry.2026-new-level/docs/level-building.md#mailbox-scope-rules) § "Pattern for cross-actor teleport". The alternative — Director directly writing the CamShot's `X_POS` via `write-actor-mailbox` — would work but is on the chopping block (see [TODO follow-ups](#todo--follow-ups)).

### Mailbox slot allocations (level-local — no engine edits)

The `GLOBAL_USER` range is `0..1899` (`mailbox.inc:8-12`). The SMB level claims three slots near the top of the range:

| Slot | Symbolic name in Forth | Written by | Read by | Purpose |
|------|------------------------|------------|---------|---------|
| 1800 | `PLAYER_X` | Player script | Director script | Player's current world X |
| 1801 | `TARGET_CAM_X` | Director script | CamShot script | SMB-shaped target camera X |
| 1802 | `MAX_CAM_X` | Director script | Director script | One-way ratchet state (camera X never decreases below this) |

These don't need `mailbox.inc` entries — Forth can use literal integers (e.g. `1800 write-mailbox`).

### Tuning constants (Forth literals, settable in `blender_create_smb.py`)

```
LEAD          = 1.5            \ +1 tile forward lead (Mario sits left of centre)
DEAD_HALF     = 1.5            \ deadzone half-width (1 tile)
X_MIN         = -3.0           \ level ground left edge (GROUND_X0)
X_MAX         = 70.5           \ level ground right edge (GROUND_X1)
HALF_FRUSTUM  = 12.0           \ half-width of camera frustum at Y=20, FOV=35° (≈ tan(17.5°)·20)
SPAWN_CAM_X   = 4.5            \ initial camera X (MARIO_SPAWN_X)
```

### Scripts

**Player script** (extends the existing input-routing one-liner at `blender_create_smb.py:290-295`):

```forth
\ wf
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox
dup 16384 & 256 / over 8192 & 64 / | |
INDEXOF_INPUT write-mailbox
INDEXOF_X_POS read-mailbox 1800 write-mailbox   \ broadcast player X to PLAYER_X
```

**Director script** (new — set as `wf_Script` on the Director actor):

```forth
\ wf
\ Lazy-init MAX_CAM_X to SPAWN_CAM_X on first tick.
1802 read-mailbox 0= if 4.5 1802 write-mailbox then

\ Compute desired = PLAYER_X + LEAD.
1800 read-mailbox 1.5 +                          ( desired )

\ Deadzone gate: if |desired - MAX_CAM_X| < DEAD_HALF, leave MAX_CAM_X alone.
\ Otherwise apply one-way ratchet + edge clamp and update MAX_CAM_X.
dup 1802 read-mailbox - dup 0< if -1.0 * then   ( desired |delta| )
1.5 <
if drop
else
  dup 1802 read-mailbox max                      ( desired-or-current )
  dup 9.0 <  if drop  9.0 then                   ( edge clamp: X_MIN + HALF_FRUSTUM = 9.0 )
  dup 58.5 > if drop 58.5 then                   ( edge clamp: X_MAX - HALF_FRUSTUM = 58.5 )
  dup 1802 write-mailbox                         ( MAX_CAM_X := target )
then

\ Write final target to TARGET_CAM_X for the CamShot to consume.
1801 write-mailbox
```

(Stack-juggling above is illustrative; final form uses verified zForth idioms. No nested `:` definitions inside the body — see [`feedback_zforth_int_divide`](../../WorldFoundry.2026-new-level/.claude/projects/-home-will-WorldFoundry/memory/feedback_zforth_int_divide.md).)

**CamShot script** (new — set as `wf_Script` on the `cs_side` CamShot actor):

```forth
\ wf
1801 read-mailbox INDEXOF_X_POS write-mailbox    \ apply TARGET_CAM_X to own position
```

### Files changed

| File | Edit |
|------|------|
| `wflevels/smb_w1_1/blender_create_smb.py` | (a) Player script gets one extra line broadcasting `X_POS` to slot 1800. (b) Director's `wf_Script` field set with the scroll logic above. (c) CamShot's `wf_Script` field set with the one-line `TARGET_CAM_X → INDEXOF_X_POS` apply. (d) CamShot keeps `Position X = Absolute` (the CamShot's script moves itself; the engine reads from its position). Set `Follow = player` is unnecessary here since the per-axis path is Absolute on X — Follow stays at `Target02` for the Y/Z look-at math. (e) Update the header comment (currently flags scrolling as "a later milestone"). |

**Zero engine code.** No rebuild of `wf_game`. Only re-run the level pipeline (Blender → .lev → .lvl → .iff).

---

## Risks / gotchas

1. **Forth math is fixed-point on real target, float on PC dev** ([`project_mailboxes_fixed_point`](../../WorldFoundry.2026-new-level/.claude/projects/-home-will-WorldFoundry/memory/project_mailboxes_fixed_point.md)). The arithmetic above is straight scalar add/sub/compare — works in both. No division needed, so the `/` float-vs-int trap ([`feedback_zforth_int_divide`](../../WorldFoundry.2026-new-level/.claude/projects/-home-will-WorldFoundry/memory/feedback_zforth_int_divide.md)) doesn't bite.
2. **Per-frame camera slew clamp.** `NormalCameraHandler::_update` (`movecam.cc:495-511`) clamps the final camera position to ≤10 units/frame on each axis. Why it's not a problem for SMB:
   - Mario's max ground speed is 6.0 (`blender_create_smb.py:274`) and the camera target X tracks `player_x + 1.5`, so per-frame camera delta is ≤6 — well under the 10/frame slew budget.
   - Edge-clamp doesn't introduce large jumps: when Mario approaches a level boundary, the clamp holds the camera in place (delta → 0), it doesn't snap.
   - The one-shot seed of `MAX_CAM_X` (0 → 4.5) happens on the first Director tick. At that point `cd.idxOldCamShotActor == 0` and the engine skips the slew (line 510 guard) — so the seed propagates instantly even though it would otherwise exceed the budget.
   - Documented in [`docs/level-building.md`](../../WorldFoundry.2026-new-level/docs/level-building.md) § Per-frame camera slew clamp.
3. **Per-tick execution order — verified, and there's a 1-tick lag we can't avoid (but it's fine).** Researched: WF has no priority/phase mechanism for actor scripts. The Director is special-cased at [`wfsource/source/game/level.cc:881-888`](../../WorldFoundry.2026-new-level/wfsource/source/game/level.cc) to run *after* the main `UpdatePhysics()` loop, with the literal comment *"FIX - manually update director until we get priorities working in updates"* — an unfinished feature from the original codebase. Tracked as a TODO; see [TODO follow-ups](#todo--follow-ups). What this means for our 3-script chain:
   - **Player** (main loop, actor-index order): writes `PLAYER_X` to global 1800.
   - **CamShot script** (main loop, actor-index order): reads `TARGET_CAM_X` from global 1801 and writes own `INDEXOF_X_POS`. The value of `TARGET_CAM_X` it sees was written by Director on the *previous* tick.
   - **Camera handler** (main loop, runs on the Camera actor's update — calls `SetCameraParametersFromShot` which reads CamShot's position): sees the position the CamShot script just wrote.
   - **Director** (after main loop): reads `PLAYER_X` (this tick's value, fresh), computes target, writes `TARGET_CAM_X` for next tick.
   - **Net result:** camera position lags player by exactly 1 tick. 16ms at 60Hz. Invisible.
   - **The alternative — Director-only design writing CamShot.X_POS via `write-actor-mailbox`** — has the *same* 1-tick lag, because the camera handler runs in the main loop before Director runs. So the signal-chain design isn't worse on this metric, and it's architecturally cleaner (no action-at-a-distance). Earlier drafts of this gotcha worried the signal chain was more fragile than the Director-only design; that worry was wrong.
   - **What we do need to control:** Player's actor index must be ≤ CamShot's actor index in the .lev file, so `PLAYER_X` is written before CamShot's script runs — otherwise CamShot would still see correct data (it reads `TARGET_CAM_X` not `PLAYER_X`), but the lag would be 2 ticks instead of 1 because `PLAYER_X` would also be stale by Director's read. The .blend.py creates Player before CamShot already; confirm exporter preserves creation order.
4. **Director references CamShot by name only via the Player→Director→CamShot signal chain**, not via actor index. No actor-name-to-index resolution is needed in the script literals — the slot numbers (1800/1801/1802) are plain integers. Simpler than the `write-actor-mailbox` alternative.
5. **Director script size.** The whole scroll routine is ~20 Forth ops. zForth's dictionary cap (32 KB, see TODO.md `SCRIPTING ENGINES`) has lots of room.
6. **Performance.** Director Forth runs every tick. ~20 ops × 60 Hz < 1 µs. Not a concern.

---

## Verification

- [ ] SMB level builds end-to-end (Blender script → .lev → .lvl → .iff).
- [ ] Run on the debug bridge; tap mailboxes 1800/1801/1802 each frame to confirm the player-X → target-X chain is alive.
- [ ] Four in-game screenshots ([`feedback_screenshots_for_proof`](../../WorldFoundry.2026-new-level/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md)):
  - t=0: Mario at spawn, camera centred on him (Mario slightly left of frame centre because of the 1-tile lead).
  - Mario walked right past the deadzone: camera has scrolled; Mario stays ~1 tile left of frame centre.
  - Mario walked back left from a scrolled position: camera **unchanged**; Mario drifts further left in frame (one-way ratchet proof).
  - Mario at the flagpole: camera clamped at level-end; flagpole visible at right edge with no void past it.
- [ ] Plan promoted to `docs/plans/2026-05-17-smb-scrolling-camera.md` ([`feedback_plans_in_project`](../../WorldFoundry.2026-new-level/.claude/projects/-home-will-WorldFoundry/memory/feedback_plans_in_project.md)).
- [ ] Commit after each phase ([`feedback_commit_after_each_phase`](../../WorldFoundry.2026-new-level/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md)). Three commits: player-script broadcast line; Director + CamShot script wiring; verification screenshots.

---

## Open questions

1. Is the one-line addition to the player script acceptable, or worth waiting until the `read-actor-mailbox` follow-up lands so the Director can pull instead? See [TODO follow-ups](#todo--follow-ups).
2. Confirm the deadzone half-width (1.5 m / 1 tile) and forward lead (1.5 m / 1 tile) numbers, or specify other values.

---

## Notes

- Named-actor-reference resolution in script literals is a guaranteed wf_blender capability — if a specific reference doesn't resolve at build time, that's an exporter bug to fix in `wftools/wf_blender/`, not a feature gap. (Not needed for this plan since the cross-actor coupling is via global mailbox slots, not actor indices.)
- The engine-side alternative (per-CamShot OAS fields + inline branch in `NormalCameraHandler::_update`) is fully designed at [`docs/plans/2026-05-17-smb-scroll-engine-route.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-17-smb-scroll-engine-route.md). Parked, will come back to it after this one ships.

---

## TODO / follow-ups

- **Add `read-actor-mailbox` Forth primitive.** Asymmetric with existing `write-actor-mailbox` at [`engine/stubs/scripting_zforth.cc:135-148`](../../WorldFoundry.2026-new-level/engine/stubs/scripting_zforth.cc) (custom syscall id 2). The read counterpart would be custom syscall id 3, signature `( idx actor_idx -- val )`, ~10 LOC. Reads are just observation across the actor boundary, no encapsulation violation — distinct from the write-side concern below. Adding it lets this plan drop the player-script broadcast line: the Director would pull `<player_actor_idx> INDEXOF_X_POS read-actor-mailbox` directly. Logged in [`TODO.md`](../../WorldFoundry.2026-new-level/TODO.md) under `SCRIPTING INFRASTRUCTURE`.
- **Review `write-actor-mailbox` — consider removing.** Action-at-a-distance bypasses the signal-mailbox pattern; if removed, this plan's signal-chain design is the only path forward (no fallback to direct CamShot poking). Tracked in [`TODO.md`](../../WorldFoundry.2026-new-level/TODO.md) under `SCRIPTING INFRASTRUCTURE`.
- **Wire per-CamShot slew override.** `camshot.oas:45-47` has commented-out `XSlew/YSlew/ZSlew` stubs Phil never finished. Documented in [`docs/level-building.md`](../../WorldFoundry.2026-new-level/docs/level-building.md) § Per-frame camera slew clamp. Not needed for SMB (Mario speed = 6 < 10/frame).
- **Finish the "priorities working in updates" feature.** `level.cc:881-888` has a hardcoded Director-after-main-loop workaround with the literal comment *"FIX - manually update director until we get priorities working in updates"*. A real priority/phase mechanism would let signal-chain designs run all producers before all consumers in a single tick, eliminating the 1-tick lag this plan currently accepts. Logged in [`TODO.md`](../../WorldFoundry.2026-new-level/TODO.md). Not blocking SMB — the 1-tick lag is invisible at 60Hz — but worth doing once another level surfaces the same pattern.
- **Engine-side SMB scroll route (parked plan).** See [`docs/plans/2026-05-17-smb-scroll-engine-route.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-17-smb-scroll-engine-route.md) for the OAS-fields-and-inline-branch design. Trigger to unpark: after a new level ships.
