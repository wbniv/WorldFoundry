# SMB camera pull-back — Y=−20 → Y=−30

**Status:** Done — committed `0aecb44` + `528084b` 2026-05-21

## Goal

Show ~50% more vertical content in the side-scrolling view so the coin arc
(and other above-ground actors) are visible without having to scroll or pan.

## Change

Move the side-scroller camera from Y=−20 to Y=−30 (50% further from the
gameplay plane → frustum is 50% taller and wider at Y=0).

Room01 bbox Y-min extended from −30 to −35 so the camera sits safely inside
the room rather than exactly on its boundary.

### Files

| File | Change |
|------|--------|
| `wflevels/smb_w1_1/blender_create_smb.py` | `CAM_Y = -30.0`; `RY0 = -35.0`; comments updated |
| `wflevels/smb_w1_1/smb_w1_1.lev` | Camera and cs_side Position Y: −20 → −30; Room01 bbox Y-min: −30 → −35 |
| `wflevels/smb_w1_1.iff` + `smb_w1_1-standalone.iff` | Rebuilt via `build_level_binary.sh` |

FOV stays at 35°; no perspective-distortion change — the scene just zooms out uniformly.

## Before / After

### Before (Y=−20)
Only the nearest `?`-block visible in frame; coin at Z≈9.5 m was above the viewport.

### After (Y=−30) — pre-trigger

All three `?`-blocks (qblock_00, 01, 02) visible simultaneously; coin arc fits in frame:

![camera pull-back — wider view](../../tests/screenshots/smb_camera_pullback.png)

### After — coin above block

Coin (red box, inset) at Z≈9.5 m above qblock_00 after generator fires:

![coin above block proof](../../tests/screenshots/gold_coin_spawn_proof.png)
