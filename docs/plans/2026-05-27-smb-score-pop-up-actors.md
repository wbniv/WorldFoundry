# Plan: SMB score pop-up actors  ✓ Done 2026-05-30

## Context

W1-1 scoring is fully wired (stomp=100, coin=200, fireball=200, shell=100, brick=50, flagpole bonus). The HUD score counter updates, but there's no per-event visual feedback — no white floating number above enemies when stomped, coins when collected, or bricks when broken. This plan adds the SMB-style floating score indicator using a pre-placed pool actor and script-driven teleport/float.

## Approach

**No dynamic spawning.** Forth scripts can't call `SafelyConstructTemplateObject`. Instead, pre-place one `popup_score` actor off-screen and control it purely via global mailboxes, exactly like the piranha plant/fireball generators already work.

### New mailboxes (mailbox.inc, after SMB_ONEUP_PICKUP=1841)

| Name | Idx | Role |
|---|---|---|
| `SMB_POPUP_X` | 1842 | X position for the popup spawn |
| `SMB_POPUP_Z` | 1843 | Z position (popup spawns 1.5 units above this) |
| `SMB_POPUP_TRIGGER` | 1844 | Pulse to 1; popup script reads + clears each tick |
| `SMB_POPUP_UNTIL` | 1845 | Level-clock time when popup expires; 0 = idle |

### New actor (blender_create_smb.py)

`popup_score`: bright-yellow diamond mesh (four verts in the XZ plane: top, right, bottom, left), parked at x=−70. Schema `gold`, Gold Value=0, Mobility=Anchored (no physics/gravity), Mass irrelevant, Script=`POPUP_SCRIPT`.

Mesh dimensions: POP_W = T*0.35 (half-width), POP_H = T*0.45 (half-height), POP_T = 0.12 (Y-depth). Color: `(1.0, 0.95, 0.2)` — near-white yellow, visible against sky.

`make_mat` and `attach_schema` helpers already exist in blender_create_smb.py. The diamond mesh uses `bm.faces.new([top, right, bot, left])` — a single planar quad.

### POPUP_SCRIPT (constant in blender_create_smb.py, embedded in lev)

```forth
\\ wf
INDEXOF_SMB_POPUP_TRIGGER read-mailbox 0<> if
  INDEXOF_SMB_POPUP_X read-mailbox INDEXOF_X_POS write-mailbox
  0.0 INDEXOF_Y_POS write-mailbox
  INDEXOF_SMB_POPUP_Z read-mailbox 1.5 + INDEXOF_Z_POS write-mailbox
  INDEXOF_TIME read-mailbox 0.75 + INDEXOF_SMB_POPUP_UNTIL write-mailbox
  0 INDEXOF_SMB_POPUP_TRIGGER write-mailbox
then
INDEXOF_SMB_POPUP_UNTIL read-mailbox 0<> if
  INDEXOF_TIME read-mailbox INDEXOF_SMB_POPUP_UNTIL read-mailbox < if
    INDEXOF_Z_POS read-mailbox 3.0 INDEXOF_DELTA_TIME read-mailbox * + INDEXOF_Z_POS write-mailbox
  else
    -70.0 INDEXOF_X_POS write-mailbox
    0 INDEXOF_SMB_POPUP_UNTIL write-mailbox
  then
then
```

Logic: on trigger → teleport to (POPUP_X, 0, POPUP_Z+1.5), set expiry = now+0.75s, clear trigger. While TIME < expiry → float up at 3 m/s. On expiry → park back to x=−70, clear POPUP_UNTIL.

### Script changes (smb_w1_1.lev)

Three insertion snippets are used. Because the .lev is modified via Edit, each insertion must match a unique surrounding context.

**POPUP_SET_SELF** — used at enemy/brick scoring locations (fires from actor's own position):
```forth
INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox
INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox
1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox
```

**POPUP_SET_PLAYER** — used in player script for coin scoring (fires from player's position):
```forth
INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_SMB_POPUP_X write-mailbox
INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox
1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox
```

Insert locations in each script (all in smb_w1_1.lev):

| Script | Trigger | Insert BEFORE |
|---|---|---|
| **Goomba** — stomp | POPUP_SET_SELF | `0 INDEXOF_ALIVE write-mailbox\n  1 INDEXOF_SMB_STOMP write-mailbox` |
| **Goomba** — fireball kill | POPUP_SET_SELF | `INDEXOF_SMB_SCORE read-mailbox 200 +` (fireball block) |
| **Goomba** — shell kill | POPUP_SET_SELF | `INDEXOF_SMB_SCORE read-mailbox 100 +` (shell block) |
| **Koopa** — stomp (shell retract) | POPUP_SET_SELF | `1 INDEXOF_SMB_KOOPA_STATE write-mailbox\n  0 INDEXOF_XSPEED write-mailbox\n  1 INDEXOF_SMB_STOMP write-mailbox` |
| **Koopa** — fireball kill | POPUP_SET_SELF | `INDEXOF_SMB_SCORE read-mailbox 200 +` (fireball block) |
| **Brick** — Super-hit break | POPUP_SET_SELF | `INDEXOF_SMB_SCORE read-mailbox 50 +` |
| **Player** — coin delta>0 | POPUP_SET_PLAYER | `200 * INDEXOF_SMB_SCORE read-mailbox +` |

Stomp sets popup from enemy position BEFORE `INDEXOF_ALIVE write-mailbox` so the actor's X_POS is still valid. Fireball/shell kill blocks also fire before `ALIVE=0`.

## Files changed

| File | Change |
|---|---|
| `wfsource/source/mailbox/mailbox.inc` | +4 MAILBOXENTRY rows (1842–1845) |
| `wflevels/smb_w1_1/blender_create_smb.py` | +POPUP_SCRIPT constant, +`_make_popup_template()` call |
| `wflevels/smb_w1_1/smb_w1_1.lev` | 7 script insertions as above |
| `wflevels/smb_w1_1/smb_w1_1.lvl` + `.iff` + `-standalone.iff` | rebuilt from .lev/.py |
| `wflevels/smb_w1_1/popup_score.iff` | new actor mesh |
| `engine/stubs/scripting_stub.cc` | touch to recompile new mailbox constants |

## Build sequence

1. Edit mailbox.inc, blender_create_smb.py, smb_w1_1.lev
2. `python3 -m py_compile wflevels/smb_w1_1/blender_create_smb.py`
3. Run Blender headless to rebuild level actors
4. Rebuild level binary (levcomp + iffcomp)
5. `touch engine/stubs/scripting_stub.cc && task build`

## Verification

- Existing `tests/verify_smb_scoring.py` must still pass (all 5 checks)
- Extend test: after coin injection, watch `popup_score` actor (discovered via log) for `Z_POS > spawn_z + 0.1` within 3 s → confirms popup floats up
- Screenshot: `tests/screenshots/smb_popup_stomp.png` — popup visible above Goomba

## Completion notes (2026-05-30)

**Deviation from plan:** parking position changed from `(−70, 0, 0)` to `(0, 0, −5)`.
Actors outside the surface room's bbox (`x ∈ [−66.25, 133.75]`) are assigned `roomnum < 0`
by `LevelRooms::AddObjectToRoom`, which calls `SetPendingRemove` — permanently killing the
actor at startup. Parking underground at z=−5 keeps it inside the bbox so the script runs
every frame. Park-back in POPUP_SCRIPT uses `0.0 INDEXOF_X_POS write-mailbox` +
`-5.0 INDEXOF_Z_POS write-mailbox` instead of an x=−70 offscreen park.

**Test result:** `tests/verify_smb_scoring.py` — ALL PASS (6 checks).
Screenshot: `tests/screenshots/smb_popup_stomp.png`.
