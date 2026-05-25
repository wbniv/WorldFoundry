# SMB W1-1 — tune Mario's movement + jump so he can hop onto a `?` block

**Status:** DONE 2026-05-17 (commits `9a41e91b`, `61b1d18b`) — MarbleHandler jump path + Mario speed/jump tuning + Z-up capsule.

## Context

SMB W1-1 renders correctly ([61b1d18](../../) Z-up capsule fix + mesh-feet bake), and Mario walks when the user pushes the joystick. But:

- **Walks slowly** — currently `Max Ground Speed = 6.0 m/s` with `T = 1.5 m/tile`, so Mario crosses 4 tiles/sec. With a camera viewport showing ~32 m of scene, that looks like a slow shuffle compared to NES Mario's "running" speed of ~5–6 tiles/sec at NES tile-scale.
- **Doesn't visibly jump** — the math comes out to a `0.67 m` apex (a third of Mario's height), invisible at this camera distance. Math: `JumpAccel = 20 × duration 0.2 s = Δv 4 m/s; apex = 4²/(2·12) = 0.67 m`. The `?` blocks are centred at `z = 6.75 m`, so the current jump can't even reach the bottom of one.
- Input wiring **is** correct (verified — see Phase 0 below). This is purely a numeric-tuning problem, not a plumbing bug.

**Goal:** screenshot of Mario airborne above (or standing on top of) a `?` block, captured by the debug bridge.

## Phase 0 — facts already verified (no work needed)

- Mario's `.lev` block ([wflevels/smb_w1_1/smb_w1_1.lev](../../wflevels/smb_w1_1/smb_w1_1.lev) lines 870–910) confirms current values: `Running Accel 8.0`, `Max Ground Speed 6.0`, `Jumping Accel 20.0`, `Falling Accel 12.0`, `Mass 1.0`, `Mobility Physics`, `TurnRate 0` (doom-stick).
- Active ground handler is `MarbleHandler::predictPosition` ([wfsource/source/movement/movement.cc](../../wfsource/source/movement/movement.cc) line 651) because `TurnRate == 0`. It accelerates on `EJ_BUTTONF_UP/DOWN/LEFT/RIGHT` (bits 11–14), caps at `MaxGroundSpeed`. Mario's Forth script preserves the raw L/R bits AND adds `kBtnStepLeft/Right` (bits 6/7), so both MarbleHandler (raw L/R) and AirHandler (Step bits, [movement.cc](../../wfsource/source/movement/movement.cc) lines 760–768) see input.
- Jump impulse path: [movement.cc](../../wfsource/source/movement/movement.cc) line 253 triggers AirHandler on `kBtnJump` (= `EJ_BUTTONF_A`, bit 0); lines 830–837 apply `JumpAccel × jumpDuration` Δv on Z; `jumpDuration = SCALAR_CONSTANT(0.2)`; gravity (`FallingAccel`) subtracted every frame (line 843).
- Jolt path is live: [movement.cc](../../wfsource/source/movement/movement.cc) lines 566–586 use `JoltCharacterIsOnGround()` to land-transition AirHandler → MarbleHandler. The 61b1d18 Z-up capsule means ground contact is correctly detected.
- The "recent doomstick fix on snowgoons" the user mentioned is most likely 61b1d18 itself — there are no doomstick-input commits in the last 2 weeks; snowgoons player has `TurnRate=5.0` and is **not** the doomstick path. Mario is the only doomstick consumer right now, so any doomstick-flavoured improvements ride with this work.

## Phase 1 — tune the OAS values in the Blender script

**File to edit:** [wflevels/smb_w1_1/blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py) lines 271–278 (the player block).

Target feel: NES-Mario-grade. The numbers below give an apex of ~8 m (clears a `?` block at `z = 6.75 m`, lands on top at `z ≈ 7.5 m`) and a top speed of ~8 tiles/sec.

| Field | Now | Proposed | Reasoning |
|---|---|---|---|
| `Running Acceleration` | 8.0 | **16.0** | Ramps to top speed in ~0.75 s — snappy but not instant |
| `Running Deceleration` | 0.85 | 0.85 | Keep — applied as per-frame friction |
| `Max Ground Speed` | 6.0 | **12.0** | 8 tiles/sec — "running Mario" pace |
| `Jumping Acceleration` | 20.0 | **70.0** | Δv = 14 m/s over 0.2 s → apex `14²/(2·12) ≈ 8.2 m` (clears `?` block top at 7.5 m) |
| `Falling Acceleration` | 12.0 | 12.0 | Keep for now — feel-tune after first screenshot |
| `Air Acceleration` | 10.0 | **16.0** | Air control should match running accel so mid-jump steering doesn't feel mushy |
| `Max Air Speed` | 6.0 | **12.0** | Match `Max Ground Speed` |
| `Jumping Momentum Transfer` | 0.5 | 0.5 | Keep — horizontal-momentum → bonus-vertical boost when jumping while running |

These are starting values. After the first screenshot we'll know if jump is over/under and tweak from there.

## Phase 2 — rebuild + drive the engine via debug bridge

1. **Edit** [blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py) lines 271–278 with the values above.

2. **Rebuild** (per the [build pipeline](../level-building.md) — Blender → lev → lvl → iff → standalone):
   ```bash
   blender --background --python wflevels/smb_w1_1/blender_create_smb.py
   bash wftools/wf_blender/build_level_binary.sh smb_w1_1
   ```

3. **Run with debug bridge** in background:
   ```bash
   LD_LIBRARY_PATH=engine/libs DISPLAY=:0 engine/wf_game \
     -Lwflevels/smb_w1_1-standalone.iff \
     --debug-port 7777 --debug-bind 127.0.0.1
   ```

4. **Write a driver** at `~/tmp/smb-shots/jump_capture.py` (modelled on [scripts/research/wf/qbert_wf_walker.py](../../scripts/research/wf/qbert_wf_walker.py) lines 147–148 which already shows `cli.inject_input("joystick1_raw", 0x2000, duration_frames=N)`). The right joystick bits are:
   - `RIGHT = 0x2000` (bit 13)
   - `LEFT  = 0x4000` (bit 14)
   - `JUMP  = 0x0001` (bit 0, = `EJ_BUTTONF_A` / `kBtnJump`)

   Sequence:
   - `t = 0.0`  : screenshot — idle on spawn → `~/tmp/smb-shots/jump_00_idle.png`
   - `t = 0.5`  : `inject_input("joystick1_raw", 0x2000, duration_frames=120)` — hold RIGHT 2 s
   - `t = 2.0`  : screenshot — running mid-flight → `jump_01_running.png`
   - `t = 2.5`  : `inject_input("joystick1_raw", 0x2001, duration_frames=12)` — RIGHT + JUMP (0x2000 | 0x0001)
   - `t = 2.7`  : screenshot — jump apex → `jump_02_apex.png`
   - `t = 3.5`  : screenshot — landed (hopefully on `?` block) → `jump_03_landing.png`

   Use the existing [BridgeClient](../../tests/debug_bridge_client.py) (proven this session) — no new client code needed.

5. **Kill** the engine: `pkill -f 'wf_game.*smb_w1_1'`.

## Phase 3 — iterate

Look at the four screenshots:

- If Mario passes through / under the `?` block: jump is too short → raise `JumpingAcceleration` by 10–20.
- If Mario flies offscreen up: too tall → lower it.
- If Mario walks too fast/slow on the ground: adjust `Max Ground Speed` in 2–3 m/s steps.
- If jump arc feels floaty: raise `Falling Acceleration` (e.g. 12 → 18) for snappier descent.

Re-render + re-shoot. Two iterations should be enough.

## Phase 4 — commit when "Mario on `?` block" screenshot exists

Single commit on `2026-new-level`:
- [wflevels/smb_w1_1/blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py) (tuning)
- `wflevels/smb_w1_1/smb_w1_1.lev`, `.lvl`, `.iff` (rebuilt)
- `wflevels/smb_w1_1-standalone.iff` (rebuilt)

Commit message: `feat(smb): tune Mario speed + jump to land on ? blocks`.

Add the apex/landing screenshot path to [wf-status.md](../../wf-status.md) Summary as a one-sentence entry per the rolling-summary convention (prepend; one sentence).

## Out of scope (deferred)

- Goomba walking AI, koopa shell, `?`-block bump animation, coins, pipes, bricks — these are all next-level work after we prove the player feel is right.
- Scrolling camera — current fixed Y = −20 view is fine for the screenshot goal; scroll comes after multiple level segments exist.
- Any change to [movement.cc](../../wfsource/source/movement/movement.cc) or [physics/jolt/](../../wfsource/source/physics/jolt/) — Phase 0 confirmed these are correct; jump impulse math is a function of OAS data only.

## Critical files

- [wflevels/smb_w1_1/blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py) lines 271–278 — the only line range that changes.
- [tests/debug_bridge_client.py](../../tests/debug_bridge_client.py) — reused as-is for the screenshot driver.
- [wftools/wf_blender/build_level_binary.sh](../../wftools/wf_blender/build_level_binary.sh) — rebuild script.
- [wfsource/source/movement/movement.cc](../../wfsource/source/movement/movement.cc) lines 651–720 (MarbleHandler), 726–870 (AirHandler), 830–837 (jump impulse) — reference only.

## Verification

End-to-end success criteria: `~/tmp/smb-shots/jump_03_landing.png` shows Mario standing on (or visibly very near landing on) the top of a `?` block, screen-right of his spawn position. User can re-run with `task run-level -- wflevels/smb_w1_1-standalone.iff` and visually confirm.
