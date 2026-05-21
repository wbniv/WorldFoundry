# SMB Mario movement retune — faster ground, no air control, variable jump

**Status:** Level-data changes (items 1 & 2) done — applied in a prior session with values exceeding the plan targets (`Running Acceleration`=60.0, `Max Ground Speed`=32.0, `Air Acceleration`=0.0). Item 3 (variable jump height, `movement.cc`) is engine-session work, still pending. Originally active 2026-05-18. Follow-up to interactive test of the previously-landed [SMB Mario speed/jump tuning](2026-05-17-smb-mario-speed-jump-tuning.md) and the qblock bump mechanic.

## User feedback (verbatim)

> he walks way too slowly until he's in the air and then he moves quickly and easy to fly off the level. he should move faster (quite a bit faster) and there should be no movement from the joystick directions while in the air (HOWEVER, the duration of the button press for jump does affect the height (i think you already know that and want me to test that especially))

## Three changes

### 1. Faster ground movement (level data)

`wflevels/smb_w1_1/blender_create_smb.py:452-458`:

| Prop | Old | New |
|------|-----|-----|
| `Running Acceleration` | 16.0 | 40.0 |
| `Max Ground Speed`     | 12.0 | 24.0 |

Roughly doubles top speed and gives a sharper acceleration ramp so reaching max speed takes ~0.6 s instead of ~0.75 s. Tile pitch is 1.5 m, so 24 m/s ≈ 16 tiles/sec — closer to NES Mario's run.

### 2. Zero air control (level data)

`wflevels/smb_w1_1/blender_create_smb.py`:

| Prop | Old | New |
|------|-----|-----|
| `Air Acceleration` | 16.0 | 0.0  |

`AirHandler::predictPosition`'s doomstick branch (`movement.cc:753-783`) multiplies every joystick-induced velocity delta by `airAccel`. Zero ⇒ no horizontal input authority while airborne; Mario keeps his launch momentum unchanged. `Max Air Speed` stays at 12.0 as a safety cap if any other force sneaks horizontal velocity in.

Leaves the `MaxAirSpeed` cap untouched — it only matters as an upper bound.

### 3. Variable jump height (engine code)

`wfsource/source/movement/movement.cc:843-851` currently applies upward impulse for the full `handlerData->jumpDuration` (0.2s seeded in `MarbleHandler::predictPosition:665`) regardless of whether the player keeps holding jump. Add the SMB-classic release-truncate: when `kBtnJump` is no longer pressed, clip `jumpDuration` to zero so further impulse stops accumulating.

Insert immediately before the `if (handlerData->jumpDuration > Scalar::zero)` block:

```cpp
// SMB-style variable jump height: releasing the button mid-jump truncates
// the remaining upward impulse, so a tap is short and a hold is full-height.
if (!(buttons & kBtnJump))
    handlerData->jumpDuration = Scalar::zero;
```

`buttons` is already in scope at the top of `AirHandler::predictPosition` (line 743). No new state, no new fields — just a guard on the existing duration.

Tap (≤1 frame held) ⇒ ~1 frame of jump impulse, very short hop. Full hold (≥0.2 s) ⇒ full apex (~8.2 m as designed). Linear in between.

## Verify

- `engine/build_game.sh` succeeds.
- Re-export level, rebuild .iff.
- User interactive test: ground feels fast, mid-air joystick input has zero effect on trajectory, tap-jump is short and hold-jump is tall.
- No bridge-side test needed; pure feel issue.

## Out of scope

- Re-running coin pop visual confirmation
- Goomba behaviour
- Camera scroll tuning

## Critical files

- `wflevels/smb_w1_1/blender_create_smb.py:452-458` — three OAS prop changes
- `wfsource/source/movement/movement.cc:843` — insert release-truncate guard
