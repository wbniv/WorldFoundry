---
plan: qbert-hop-arc-motion
date: 2026-05-10
status: Parked 2026-05-11
scope: ~30 LOC of zForth in [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py); 6 new local mailboxes (435–440); no engine, no mailbox.inc, no OAS.
---

# Q*bert hop-arc motion (Phase 1.5)

**Status:** Parked 2026-05-11 — lerp-based hop motion is acceptable for now; revisit once enemy AI / cube logic is further along, or fold into the deferred [physics-hops plan](2026-05-10-qbert-physics-hops.md).

## Context

After [Phase 1 hop-rotation](2026-05-10-qbert-hop-facing-rotation.md) (commits `78c4eb6` + `ff14144`), Q*bert smoothly rotates to face each diagonal during the 12-frame `HOP_COOLDOWN`. But position-wise, `do-hop` still **teleports** XYZ to the destination cube on frame 0 — Q*bert blinks instantly to the new cube and then sits there for 12 frames while only the rotation animates. Looks wrong.

User-approved approach (from Phase 2 question, 2026-05-10): defer mesh stretch-and-squash (would require wiring per-actor scale through engine, plan TBD), and instead implement the **parabolic Z arc + XY straight-line lerp** across the existing cooldown. Q*bert visibly hops through the air over the 12 frames — gives a partial "stretch effect" just from being airborne.

This is a teleport-based fix (still no Jolt physics on the player). The [physics-hops follow-up plan](2026-05-10-qbert-physics-hops.md) will eventually replace this with velocity-driven arcs through CharacterVirtual; this plan is the cheap visual win in the meantime.

## Existing facts to reuse

- `do-hop` at [blender_create_qbert.py:480-503](../../wflevels/qbert_practice/blender_create_qbert.py) currently computes target X/Y/Z from `(new_row, new_col)` and writes them directly to `INDEXOF_X/Y/Z_POS`. Same math stays — just routes the result to local storage instead of immediate position writes.
- `HOP_COOLDOWN` (mb 402) gates joystick + the rotation lerp. Same gate works for the position lerp.
- The rotation lerp's "self-correcting" pattern (read current each frame, divide remaining delta by frames-left) is inappropriate here because position must follow a deterministic parabolic curve. Use a fixed `(start, end)` pair stored in mailboxes and compute `t` from cooldown each frame.
- Free local mailboxes: 433 (HOP_FACING target yaw, in use), 434 (free now — unused since the rotation refactor), 435+ (free).

## Approach

### New state (4 mailboxes; HOP_END_X/Y are recomputed from row/col each frame to avoid the global vis-slot range starting at 440)

| mb | Name | Set by | Read by |
|---|---|---|---|
| 434 | `HOP_PENDING_LAND` | `do-hop` (sets to 1 on on-pyramid hops only; 0 left untouched on off-edge) | lerp block on **second-to-last** frame (cd=2, ~1 frame before exact landing) promotes to mb 411 — gives a slight "anticipation" feel as the cube colour flips just before Q*bert touches down. Easy to change to cd=1 (exact landing) if anticipation looks worse. |
| 435 | `HOP_START_X` | `do-hop` (saves current `INDEXOF_X_POS`) | per-frame lerp |
| 436 | `HOP_START_Y` | `do-hop` | per-frame lerp |
| 437 | `HOP_START_Z` | `do-hop` | per-frame lerp |
| 438 | `HOP_END_Z` | `do-hop` (computed from new row, with off-edge clamp in fall path) | per-frame lerp |

### `do-hop` change

Before the existing target-XYZ math, capture the current position into mb 435/436/437:

```
INDEXOF_X_POS read-mailbox 435 write-mailbox
INDEXOF_Y_POS read-mailbox 436 write-mailbox
INDEXOF_Z_POS read-mailbox 437 write-mailbox
```

Then keep the existing target-XYZ computation (`(2*col - row)*√2`, `(6-row)*√2`, `(6-row)*2 + 1 + 2`) but route the results to mb 438/439/440 instead of `INDEXOF_X/Y/Z_POS`. Per-frame lerp block (below) writes the actual position.

Also: bump `HOP_COOLDOWN` from 12 → **13** so the lerp gets exactly 12 frames at `t = (13-cd)/12` going through `1/12, 2/12, ..., 12/12` — final write at `cd=1` lands *exactly* on target. Joystick lockout becomes 13 frames vs current 12 — one extra frame, imperceptible. (Alternative: keep cd=12 with explicit "snap to target on final frame" logic, but +1 frame of cooldown is much simpler and reads identically.)

Off-edge fall handling in `do-hop` (existing code that updates Z to clamped-row Z when `(row, col)` is off-pyramid) updates mb 440 instead of `INDEXOF_Z_POS`. The lerp then animates toward the clamped position; the existing FALL_PHASE state machine takes over from there.

### New per-tick block (after rotation lerp, before `tick-cd`)

```
\\ 3.7. Hop-arc position interpolation across HOP_COOLDOWN frames.
\\ Smoothstepped lerp on XY; parabolic Z arc with peak +arc_height at mid-hop.
\\ t_raw = (13 - cd) / 12 → range [1/12, 12/12]; smoothed via t*t*(3-2t)
\\ for ease-in-out (ramps up from rest, decelerates to landing).
\\ cd=1 ⇒ t_raw=1 ⇒ smoothstep(1)=1 ⇒ exact landing.
402 read-mailbox 0 > if
  13 402 read-mailbox - 12.0 /            ( t_raw )
  dup dup * swap 2.0 * 3.0 swap - *       ( t = smoothstep(t_raw) )
  \\ X: start + t*(end - start)
  dup 438 read-mailbox 435 read-mailbox - * 435 read-mailbox + INDEXOF_X_POS write-mailbox
  \\ Y: same shape
  dup 439 read-mailbox 436 read-mailbox - * 436 read-mailbox + INDEXOF_Y_POS write-mailbox
  \\ Z: lerp + 4*t*(1-t)*arc_height ; arc_height = 2.0 units
  dup 440 read-mailbox 437 read-mailbox - * 437 read-mailbox +    ( t lerp_z )
  swap                                                              ( lerp_z t )
  dup 1.0 swap - * 4.0 * 2.0 *                                      ( lerp_z arc_bonus )
  + INDEXOF_Z_POS write-mailbox
then
```

Stack budget: peak depth ~5 — well within zForth defaults.

`arc_height = 2.0` is a tunable constant. With cube vertical spacing `Δz = 2`, an arc peak of +2 above start means Q*bert clearly leaves the cube top, peaks ~2 units above, and lands. If it looks too floaty, lower to 1.5 or 1.0.

### Respawn paths

The three respawn blocks (game-over, round-clear apex, fall-death) currently set `INDEXOF_X/Y/Z_POS` to the apex spawn directly + reset `HOP_COOLDOWN=0`. Need one extra line per block: **after** the position writes, copy the new position into mb 435/436/437 (start) AND mb 438/439/440 (end) so a stale half-hop doesn't lerp from old start to old end on the next frame:

```
INDEXOF_X_POS read-mailbox dup 435 write-mailbox 438 write-mailbox
INDEXOF_Y_POS read-mailbox dup 436 write-mailbox 439 write-mailbox
INDEXOF_Z_POS read-mailbox dup 437 write-mailbox 440 write-mailbox
```

Or skip and let `cd=0` gate the lerp entirely (which it does — the lerp block reads `402 read-mailbox 0 >` first). Stale start/end values in mb 435–440 are harmless when the lerp doesn't fire. Simpler: **don't reset start/end on respawn**; the next `do-hop` overwrites them.

## Critical files

| File | Change |
|---|---|
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | `do-hop`: save start XYZ, route target XYZ to mb 438/439/440, bump cd to 13. New per-tick lerp block. Off-edge fall path: write to mb 440 instead of `INDEXOF_Z_POS`. |

No engine changes. No `mailbox.inc` changes. No new OAS. No new Forth word definitions.

## Verification

Per memory: edit script → blender headless → `build_level_binary.sh qbert_practice` → run.

1. **Build clean**: no engine rebuild needed; only level binaries regenerate.
2. **Visible arc**: from rest, hop DOWN. Q*bert leaves apex Z, rises ~2 units, comes down on the next-row cube top. Smooth XY translate to the SE position concurrent with the arc.
3. **Land exact**: at cooldown end, Q*bert is sitting exactly on the destination cube top (no Z drift, no XY offset). Verify by hopping back and forth between two cubes — no gradual drift.
4. **Hop UP the pyramid**: Q*bert hops to higher cube — arc goes up to *above* the higher cube and lands. (Arc height is added on top of the lerp, so hopping to a higher-Z cube means rising even higher mid-arc.)
5. **Off-edge fall**: drive Q*bert off the pyramid edge. Arc starts toward the (off-pyramid) target, but the existing off-edge clamp updates the end-Z. Q*bert visibly arcs toward the clamped destination, then FALL_PHASE takes over and ramps Z down.
6. **Rotation still works**: shipped Phase 1 + Phase 1.1 (180° fix) rotation continues to lerp concurrently with the position arc. Both lerps share the same `cd > 0` gate.
7. **Death + respawn**: drive into a fall, wait for FALL_PHASE to snap to apex. Next hop should arc cleanly from apex (no stale start/end leak).

## Out of scope

- **Mesh stretch-and-squash** — separate plan, requires wiring per-actor non-uniform scale (`EMAILBOX_X_SCALE/Y_SCALE/Z_SCALE`) through actor → renderer. Significant engine work. The OAS already has stored-but-unread `x_scale/y_scale/z_scale` fields ([levelcon.h:87](../../wfsource/source/oas/levelcon.h)) that this plan would also wire up.
- **Variable arc height** based on hop distance/direction — currently constant `2.0`. Could ramp with `|Δz|` for more arcade-authentic "big leaps look bigger."
- **Physics-driven hops** — the [physics-hops plan](2026-05-10-qbert-physics-hops.md) eventually replaces this whole block with velocity-driven arcs through CharacterVirtual + Jolt gravity. This plan is the cheap visual win until then.
