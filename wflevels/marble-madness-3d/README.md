# `marble-madness-3d` — course-JSON → WF level pipeline

A **data-driven, course-agnostic** generator: feed it a heightfield **course description
JSON** and it produces a runnable standalone WF level with a rolling marble player and a
fixed SW-isometric follow camera. Nothing about the level is hand-tuned per course —
geometry, spawn, goal AABB, kill plane, room bbox and camera anchor are all computed.

Plan: [`docs/plans/2026-09-22-marble-madness-3d-level-pipeline.md`](../../docs/plans/2026-09-22-marble-madness-3d-level-pipeline.md).
Parent: [`docs/plans/2026-09-21-marble-madness-true-3d-reimplementation.md`](../../docs/plans/2026-09-21-marble-madness-true-3d-reimplementation.md).

---

## Course description JSON — the contract

```json
{
  "name": "practice",
  "cell_size": 1.0,                 // metres per grid cell in X and Y
  "cells": [                        // sparse; an absent cell is void (the marble falls)
    {"i": 3, "j": 7, "h": [z00, z10, z11, z01]}   // corner heights in metres, order:
                                                   // (i,j) (i+1,j) (i+1,j+1) (i,j+1)
  ],
  "spawn": [x, y, z],               // world metres; marble CENTRE
  "goal": {"min": [x0,y0,z0], "max": [x1,y1,z1]},   // AABB; entering it = finish
  "kill_z": -3.0                    // marble below this z → respawn at spawn
}
```

World mapping: cell `(i,j)` spans `X ∈ [i·s, (i+1)·s]`, `Y ∈ [j·s, (j+1)·s]`, Z up
(WF convention). `i`/`j` may be negative. Unknown extra keys (e.g. a `source` block) are
ignored, so a decoder is free to carry provenance alongside the contract.

### Geometry rules

| Feature | Rule |
|---|---|
| Floor | one quad per cell, split on the diagonal whose two triangles have the **smaller normal deviation** (either, when planar) |
| Cliff wall | between adjacent cells whose shared-edge corner heights differ at **either** endpoint; the half-quad that degenerates when only one endpoint differs is dropped, leaving a single triangle |
| Skirt | a cell edge bordering void gets a vertical face down to `min(all heights) − 2.0` |
| Winding | authored Blender-CCW-seen-from-outside: **+Z** for floors, **away from the solid** for walls/skirts |
| Colour | flat Principled BSDF, no textures: checkerboard greys by `(i+j)%2`, dark walls, darker skirts, amber for any cell whose centre is inside the goal AABB's XY |

There is no "void floor" plane — the marble falls past `kill_z` and respawns.

---

## Files

| Path | What |
|---|---|
| `course_geom.py` | pure Python (no `bpy`): load/validate JSON → triangle soup → welded, chunked meshes. Runnable standalone: `python3 course_geom.py <course.json> --check` and `--selftest` |
| `gen_course.py` | headless Blender: builds the scene and exports `marble-madness-3d.lev` + one `.iff` per mesh |
| `make_test_course.py` | writes `course-test.json`, the synthetic test course |
| `build.sh` | Blender step + `task build-level -- marble-madness-3d` |
| `marble-madness-3d-standalone.iff.txt` | the L4 wrapper `wf_game -L` needs |
| `verify/*.png` | recorded verification frames (see § Verification) |

> `course.json`, `course-practice.json`, `extract_course.sh` and `mm_*.py` in this
> directory are **not** part of this pipeline — they are the orchestrator's ROM-recovery
> work, committed in `979505a5`. `course.json` happens to satisfy the contract above and
> is used as verification step 6.

## Commands

```bash
# default (synthetic test course)
task build-mm3d
task run-mm3d                     # WF_RECORD=1 to record, WF_FULLSCREEN=1 for fullscreen

# any other course
task build-mm3d -- wflevels/marble-madness-3d/course.json

# pieces, if you want them separately
python3 wflevels/marble-madness-3d/make_test_course.py
python3 wflevels/marble-madness-3d/course_geom.py wflevels/marble-madness-3d/course-test.json --check
blender --background --python-exit-code 1 \
        --python wflevels/marble-madness-3d/gen_course.py -- <course.json>
task build-level -- marble-madness-3d

# raw run
LD_LIBRARY_PATH=engine/libs DISPLAY=:0 \
  engine/wf_game -Lwflevels/marble-madness-3d-standalone.iff
```

---

## Camera — exact SW-iso follow, no script

`SetCameraParametersFromShot` (`wfsource/source/game/movecam.cc:247-405`) computes

```
position  = (camShotPos − Follow.pos) + TrackObject.pos      [per axis, when Relative]
direction =  Target.pos − camShotPos                         [always the STATIC camShotPos]
```

The trap in the second line: with `Target = Player` the view direction is measured from the
camshot actor's fixed world position, so it **swings as the marble travels away from
spawn** — the camera stops looking along the iso axis. The fix falls out of the same
formula: anchor both `Follow` and `Target` on a `target` actor at the **world origin** and
place the camshot actor at the **offset itself**.

| Field | Value |
|---|---|
| `Target01` (a `target` actor) | world `(0, 0, 0)`, used as both `Follow` and `Target` |
| `cs_iso` actor position | `(−8, −8, +8)` = the offset |
| `Position X/Y/Z` | `Relative` |
| `Rotation` | `Fixed` |
| `Track Object` | `Player` |
| `Elasticity` | `1.0` |

⇒ `position = offset + playerPos` and `direction = 0 − offset = −offset`, **constant every
frame, no script, no tick lag.** (Rejected alternative: a Forth camshot that writes its own
`X/Y/Z_POS` each tick — same result, but costs a script and one tick of lag.)

**Why `(−d, −d, +d)`:** horizontal distance is `d√2`, so the elevation is
`atan(d / d√2) = 35.264°` — **true isometric**, independent of `d`. Camera is SW, looking
NE and down; screen-up is world NE and screen-right is world SE.

**Why `d = 8`, and why the FOV field is not the knob:** the CamShot `FOV` / `Hither` / `Yon`
fields are **dead**. `CameraHandler::SetCamera` (`movecam.cc:190`) writes position and
orientation only and carries the explicit
`#pragma message ("KTS: write field of view, hither and yon code")`; the renderer hardcodes
a **60° vertical FOV, near 1, far 1000** (`wfsource/source/gfx/gl/display.cc:666`). Framing
is therefore distance-only:

```
visible vertical extent = 2 · (d√3) · tan(30°) = 2·d
```

`d = 8` → **16 m of course on screen**, the 1 m marble ≈ 30 px of 480. The `FOV`/`Yon`
values written into the `.lev` are set to `60` / `1000` to match what the engine actually
does, rather than claiming a value it ignores.

**Elasticity 1.0:** the BungeeCam is a spring —
`vel = (desired − pos) / (dt · Elasticity)` (`movecam.cc:971`). The OAD default of `10`
lagged far enough at speed to push the marble noticeably off-centre; `1.0` (the field
minimum) converges within a couple of frames.

**Camera-side geometry matters.** With a 35° elevation, any wall between the camera (SW)
and the marble hides it. Keep the near (−X / −Y) boundaries low — the test course uses 1 m
corner-continuous lanes there and reserves the 2 m vertical rim walls for the far (+X / +Y)
sides. The arcade courses are built the same way.

---

## Marble physics

`MarbleHandler` is selected purely by `Turn Rate == 0`
(`wfsource/source/movement/movement.cc:651`).

| OAD field | Value | Why |
|---|---|---|
| `Turn Rate` | `0.0` | selects MarbleHandler |
| `Running Acceleration` | `26.0` | joystick impulse |
| `Running Deceleration` | `0.004` | the **only** XY decay under Jolt |
| `Max Ground Speed` | `20.0` | XY cap while grounded |
| `Max Air Speed` | `60.0` | must not be 0 — `AirHandler`'s cap would zero gravity itself |
| `Horiz/Vert Air Drag`, `Air Acceleration`, `Jumping Acceleration` | `0.0` | no drag, no mid-air steering, no jump |
| `Falling Acceleration` | `9.8` | gravity |
| `Mobility` | `Physics` | → Jolt `CharacterVirtual` |
| `Script Controls Input` | `True` | required before `INDEXOF_INPUT` (3024) accepts writes (`actor.cc:1653`) |

**Terminal speed on a slope** is frame-rate independent: MarbleHandler damps XY by
`decel · dt · 30` per frame and gravity adds `a · dt`, so

```
v_terminal = a / (30 · decel)      where a = g · sin θ · cos θ
```

At `decel = 0.004`: 5° → 7.1 m/s, 10° → 14 m/s, 18.4° (the test trough) → capped by
`Max Ground Speed`. Flat ground coasts with a ~4.6 s half-life, which is the marble feel
we want.

**Collision shape.** `JoltCharacterCreate` builds the character from the actor's
`Global Bounding Box`; equal half-extents in all three axes make it pick a `SphereShape`,
and `ctr = 0` means the actor position **is** the sphere centre. The generator therefore
overwrites the imported player's bbox with `(−0.5,−0.5,−0.5)…(0.5,0.5,0.5)` — leaving
snowgoons' humanoid box there would give a marble that slides instead of rolling.

**Course collision** is a real trimesh, not a box: a `StatPlat` with `Model Type = Mesh`
gets its box placeholder replaced by `JoltMakeStaticMesh` in `Actor::BindAssets`
(`actor.cc:586`). Jolt adds **both windings**, so winding is a rendering concern only.

---

## Scripts

**Player** (per frame): camera-relative input remap → `INDEXOF_INPUT`; publish position to
mailboxes 20/21/22; `Z < kill_z` → respawn at spawn with velocities zeroed; inside the goal
AABB → latch mailbox 13 to `2` (FINISH) and hold the marble.

The camera-relative remap is the documented 45°-CW bit rotation. It is only correct because
the marble's Euler **C is π/2**: MarbleHandler applies input along
`fwd = currentDir() = (cos C, sin C, 0)` and `right = (fwd.Y, −fwd.X, 0)`, which at
`C = π/2` are `+Y` and `+X` — the world axes the remap word assumes.
(`wfsource/source/physics/physicalobject.hpi:52` is authoritative; the `movement.cc:698`
comment saying `(sin C, cos C, 0)` is wrong, as CLAUDE.md notes.)

**Director** (runs last each tick): 60 s countdown into HUD mailbox 71; expiry raises a
respawn one-shot and restarts the clock; writes `LIVES = 1` every tick (see gotcha 6).

| Mailbox | Use |
|---|---|
| 13 | level state: 0 = rolling, 2 = FINISH |
| 20 / 21 / 22 | marble X / Y / Z, published each tick |
| 23 | level `TIME` at which the current countdown started |
| 24 | Director → Player respawn one-shot |
| 25 | respawn counter (falls + timeouts) |
| 70 / 71 / 72 | HUD score / timer / lives (read by `game.cc:614-616`) |

---

## Synthetic test course (`make_test_course.py` → `course-test.json`)

170 cells, `cell_size = 1.0`:

* **leg 1** — a 4-cell-wide trough running +X for 24 cells, descending z=8 → z=0 (18.4°),
  the two outer lanes 1 m above the centre as corner-continuous 45° ramps
* **junction** — a 4×4 pad tilted downhill in +Y, so the 90° corner is taken under gravity
* **leg 2** — 10 cells of +Y at 11.3°, with a **2 m vertical cliff** between cells j=8 and
  j=9 (separate cells sharing a corner at two different heights — the only way to express a
  true discontinuity in a heightfield)
* **rim** — one-cell-wide cells 2 m above the floor they abut on the far (+X, +Y) sides,
  each producing a full-height vertical wall quad
* **goal** — the flat platform at the end of leg 2

The result rolls the whole course **start to goal with no input**, which is what makes it
useful as a regression course.

---

## Engine gotchas hit, and how they were resolved

1. **`CamShot` FOV / Hither / Yon are dead fields.** `CameraHandler::SetCamera` never
   writes them (explicit `#pragma message` TODO) and the renderer hardcodes 60°/1/1000.
   *Resolved:* framing is set by camera **distance**; authored FOV/Yon match the renderer.
   **This contradicts `docs/level-building.md`, which presents FOV as a CamShot field you
   tune** — trusting the engine, per house rule.

2. **Jolt's "zone volume" heuristic can swallow the whole course.**
   `JoltCharacterCreate` (`jolt_backend.cc:686-704`) permanently excludes from a
   character's collision any existing **static** body whose world AABB fully contains the
   character's spawn AABB — a region-marker heuristic. A terrain chunk contains a marble
   resting on it, so a naively-placed spawn can make the marble fall through the level.
   *Resolved two ways:* `course_geom.spawn_clearance_z()` raises the spawn until
   `spawn.z + R` strictly exceeds the max Z of every chunk that could enclose it
   (0.22 m on the test course), **and** the Player actor is created before the course
   chunks so at character-creation time no static body exists at all. Verified by the
   absence of `jolt: character N ignoring zone body` in the log (step 3 below).

3. **Mesh vertex indices are `int16`.** `export_level._write_mesh_iff` packs faces as
   `struct.pack('<hhhh', v1, v2, v3, mat_idx)`, hard-capping a mesh actor at
   **32767 vertices**. *Resolved:* `course_geom` partitions cells into chunks
   (`CELLS_PER_CHUNK = 1500`, guard at `MAX_VERTS_PER_CHUNK = 20000`) and emits one
   statplat per chunk, with every face owned by exactly one cell so shared walls are
   emitted once. The 1729-cell arcade Practice course needs 2 chunks.

4. **Sub-threshold polygons abort the level.** `Vector3::Normalize` asserts
   `length > Scalar(0,4)` = `4/65536` = `6.1e-5` on the face-normal cross product
   (`math/vector3.hpi:243`). *Resolved:* the soup drops any triangle whose cross-product
   length is under `1e-3` (16× the engine's threshold), which is also what turns a
   one-endpoint-only wall into a single triangle; and `gen_course` asserts the marble
   sphere's smallest triangle clears it before exporting.

5. **`MarbleHandler` freeze creeps.** The script runs *after* the handler has already
   applied a frame of gravity, so zeroing all three velocity components on FINISH left the
   marble sinking ~2.7 mm/frame wherever it happened to latch. *Resolved:* FINISH zeroes
   input and **XY** velocity only and leaves Z alone, so the marble settles onto the goal
   platform and stays at exactly `floor + radius`.

6. **The arcade HUD is opt-in and turns itself off.** `display.cc:1225` gates the whole HUD
   on `(score | timer | lives | game_over | …) != 0`. Stopping the countdown at FINISH made
   every one of them 0 and the HUD vanished mid-recording. *Resolved:* the Director writes
   `LIVES = 1` every tick, and FINISH simply stops writing the timer so the HUD holds the
   finishing time.

7. **zForth `if/else/then` only compiles after the last `;`.** Both scripts are written as
   a block of `: word … ;` definitions followed by the per-tick body; real newlines, ASCII
   only, `&`/`|` rather than `and`/`or`.

8. **Textile kills the build on any reused snowgoons mesh.** All snowgoons gameplay actors
   are deleted and every surface is a flat Principled BSDF base colour with no image, so
   textile has nothing to look up.

9. **Noisy but harmless:** `JoltBodyCreateStaticMesh` `fprintf`s **one line per vertex** of
   every collision mesh (`jolt_backend.cc:294-300`) — 355 lines for the test course, ~2900
   for the arcade Practice course. Filter with `grep -v 'jolt: mesh v'`. Fixing it would be
   an engine change, so it was left alone.

---

## Verification

Run 2026-09-22 on this worktree (`marble-madness-3d-fable`), engine
`wf_game v0.4.1, Built:Sep 21 2026`, Blender 5.0.1, `WF_CULL` default (ON).

> **Re-running these steps:** `wf_game`'s frame rate on this box is set by the compositor,
> not by the level. Under `kwin_wayland`/Xwayland an occluded or unfocused `wf_game`
> window is frame-callback-throttled to roughly **1 fps**, and the engine then logs
> `delta too large: 1.000…` and the 30-tick `ball pos:` line may never fire inside a short
> `timeout`. Runs with `-record_video` render through the capture FBO and hold ~30 fps
> regardless, so that is the reliable way to reproduce steps 3–5 in the background. This
> is an environment property, not a level defect.

### 1. Geometry invariants (pure Python, no engine)

```
$ python3 wflevels/marble-madness-3d/course_geom.py --selftest
PASS: wall/skirt emission edge cases

$ python3 wflevels/marble-madness-3d/make_test_course.py
wrote /home/will/WorldFoundry-wbniv-mm3d-fable/wflevels/marble-madness-3d/course-test.json  (170 cells, spawn=[0.5, 2.0, 8.3333], goal={'min': [24.0, 12.0, -5.0], 'max': [28.0, 14.0, -2.9]}, kill_z=-9)

$ python3 wflevels/marble-madness-3d/course_geom.py wflevels/marble-madness-3d/course-test.json --check
course      : mm3d-test (170 cells, cell_size=1)
triangles   : 592  (dropped 2 degenerate)
chunks      : 1  verts=[355]  faces=[592]
bounds      : (0.00, 0.00, -6.40) .. (29.00, 15.00, 9.00)
spawn       : [0.5, 2.0, 8.3333]
spawn min z : 8.550 (zone-volume clearance, radius 0.5)
kill_z      : -9
faces       : floor=340 wall=76 skirt=176
PASS: winding, verticality and index-cap invariants hold
```

**PASS** — `--selftest` covers the flush / one-endpoint / two-endpoint / void-edge /
outward-normal wall cases; `--check` covers +Z floor winding, wall verticality and the
int16 index cap.

### 2. Build succeeds from clean

Every generated artifact removed first (`.lev`, `.lev.bin`, `.lvl`, `.ini`, `.iff.txt`,
`.blend`, per-mesh `.iff`, `course-test.json`, `Perm.*`, `Room0.*`, `pal*.tga`,
`../marble-madness-3d{,-standalone}.iff`, `__pycache__`):

```
$ task build-mm3d
[mm3d] course-test.json missing -- regenerating
[mm3d] 1/2  blender --background --python gen_course.py -- .../wflevels/marble-madness-3d/course-test.json
[mm3d] spawn Z 8.333 -> 8.550 (Jolt zone-volume clearance: the marble must poke out of every static body that could otherwise swallow the course)
[mm3d] course "mm3d-test": 170 cells, 592 tris (2 degenerate dropped), 1 chunk(s) [355] verts
[mm3d] importing .../wflevels/snowgoons-blender/snowgoons-blender.lev
Info: Imported 38 objects (0 skipped)
[mm3d] classes after strip: ['camera', 'camshot', 'director', 'levelobj', 'light', 'matte', 'player', 'room', 'target']
[mm3d] room bbox (-28.0, -28.0, -69.0) .. (49.0, 35.0, 39.0)
[mm3d] export order: ['Camera01', 'Director', 'LevelObj', 'Matte', 'cs_iso', 'Target01', 'Room', 'Player', 'Light01', 'mm3d_course_00', 'AmbientLight']
[mm3d] exported .../marble-madness-3d.lev ({'FINISHED'})
[mm3d] 2/2  task build-level -- marble-madness-3d
[1/5] iffcomp-rs  marble-madness-3d.lev  →  marble-madness-3d.lev.bin
[2/5] levcomp-rs  marble-madness-3d.lev.bin  →  marble-madness-3d.lvl + asset.inc + marble-madness-3d.iff.txt + marble-madness-3d.ini
[3/5] textile-rs  -ini=marble-madness-3d.ini  →  palN.tga / RoomN.{tga,ruv,cyc} / Perm.{tga,ruv,cyc}
[4/5] iffcomp-rs  marble-madness-3d.iff.txt  →  ../marble-madness-3d.iff

✓ built .../wflevels/marble-madness-3d.iff (47104 bytes)

[5/5] iffcomp-rs  marble-madness-3d-standalone.iff.txt  →  ../marble-madness-3d-standalone.iff
✓ built .../wflevels/marble-madness-3d-standalone.iff (51200 bytes)
```

**PASS.** Note `Player` precedes `mm3d_course_00` in the export order — that ordering is
load-bearing (gotcha 2).

### 3. `wf_game` runs ≥ 10 s with no assert or crash

```
$ timeout 15 env LD_LIBRARY_PATH=engine/libs DISPLAY=:0 \
    engine/wf_game -Lwflevels/marble-madness-3d-standalone.iff > run.log 2>&1
EXIT=124                       # 124 == timeout killed it, i.e. it survived the full 15 s

$ wc -l run.log; grep -c 'jolt: mesh v' run.log
505
355                            # per-vertex collision-mesh dump, gotcha 9

$ grep -cE "AssertMsg|zforth compile|fell out of room|ignoring zone body|terminate called" run.log
0
```

**PASS** — no assertion, no zForth compile error, no room eviction, no zone-volume
exclusion, and the process was still alive when `timeout` killed it.

### 4. The marble rolls downhill from spawn with no input

`jolt_backend.cc:806` logs the character position every 30 ticks. Same run as step 3, with
no input injected at any point:

```
$ grep -o "ball pos: ([^)]*)" run.log
ball pos: (1.148, 2.000, 8.146)      <- leg 1, rolling +X and descending
ball pos: (2.479, 2.001, 7.702)
ball pos: (4.509, 2.002, 7.025)
ball pos: (7.298, 2.003, 6.095)
ball pos: (11.040, 2.015, 4.848)
ball pos: (15.935, 2.028, 3.217)
ball pos: (22.278, 2.047, 1.148)
ball pos: (27.415, 4.283, -0.346)    <- junction: hits the +X rim wall, turns +Y
ball pos: (27.323, 9.632, -1.559)    <- leg 2
ball pos: (27.337, 12.049, -3.899)   <- past the 2 m cliff, onto the goal platform
ball pos: (27.337, 12.064, -3.900)   <- FINISH latched; resting at floor(-4.4) + r(0.5)
```

**PASS** on three counts: Z falls monotonically from 8.15 to 1.15 across leg 1 with zero
input; Y stays pinned at 2.00 (the trough contains it); and the final resting Z is exactly
`goal floor + marble radius`, with X/Y/Z all static afterwards — the goal AABB test and the
FINISH freeze both work, with no creep (gotcha 5).

### 5. Rendered frames — floor visible (not culled), framing is iso

`WF_RECORD=1` run, frames pulled with `ffmpeg -ss <t> -frames:v 1`. Each PNG was read back
and inspected.

| Frame | Shows |
|---|---|
| [`verify/01-spawn-trough.png`](verify/01-spawn-trough.png) | t=0.7 s — marble at spawn in the trough; checkerboard floor, trough lanes, skirt, HUD `TIME 59 LIVES 1` |
| [`verify/02-trough-midway.png`](verify/02-trough-midway.png) | t=3.0 s — marble mid-trough; the descent recedes to the upper-right, goal amber visible at the bend |
| [`verify/03-bend-and-cliff.png`](verify/03-bend-and-cliff.png) | t=4.7 s — the 2 m cliff face, the +X rim wall, the amber goal platform below |
| [`verify/04-goal-platform.png`](verify/04-goal-platform.png) | t=12.0 s — marble at rest on the goal platform, timer frozen at `TIME 55` |

**PASS.** The floor renders under `WF_CULL` default-on, so the geometry is wound correctly
(a back-wound floor would be invisible, not merely dark). The course recedes along both
screen diagonals at equal rates — the 35.26° true-isometric elevation reading as intended —
and ~16 m of course is on screen, matching `2·d` for `d = 8`.

### 6. The real ROM-derived arcade course loads and runs

`course.json` (arcade Practice, committed by the orchestrator in `979505a5`: 1729 cells,
`cell_size = 0.8`, negative `i`/`j`) satisfies the contract with no changes to either side:

```
$ python3 wflevels/marble-madness-3d/course_geom.py wflevels/marble-madness-3d/course.json --check
course      : practice (1729 cells, cell_size=0.8)
triangles   : 5036  (dropped 122 degenerate)
chunks      : 2  verts=[2519, 350]  faces=[4440, 596]
bounds      : (-64.00, -66.40, -6.25) .. (-5.60, -5.60, 0.98)
spawn       : [-13.997, -14.0, 0.55]
spawn min z : 0.550 (zone-volume clearance, radius 0.5)
kill_z      : -6.2458
faces       : floor=3458 wall=334 skirt=1244
PASS: winding, verticality and index-cap invariants hold

$ task build-mm3d -- wflevels/marble-madness-3d/course.json
[mm3d] course "practice": 1729 cells, 5036 tris (122 degenerate dropped), 2 chunk(s) [2519, 350] verts
[mm3d] room bbox (-92.0, -94.4, -66.2) .. (20.0, 20.0, 31.0)
[mm3d] export order: ['Camera01', 'Director', 'LevelObj', 'Matte', 'cs_iso', 'Target01', 'Room', 'Player', 'Light01', 'mm3d_course_00', 'mm3d_course_01', 'AmbientLight']
✓ built .../wflevels/marble-madness-3d.iff (143360 bytes)
✓ built .../wflevels/marble-madness-3d-standalone.iff (147456 bytes)

$ timeout 22 env LD_LIBRARY_PATH=engine/libs DISPLAY=:0 \
    engine/wf_game -Lwflevels/marble-madness-3d-standalone.iff > real.log 2>&1
EXIT=124
$ grep -c "ignoring zone body" real.log
0
$ grep -o "ball pos: ([^)]*)" real.log | head -3
ball pos: (-13.997, -14.000, 0.500)
ball pos: (-13.997, -14.000, 0.500)
ball pos: (-13.997, -14.000, 0.500)
```

**PASS** for the pipeline: 1729 cells, chunking engaged (2 mesh actors), level built, ran
22 s with no assert, no zone exclusion, and the marble resting on the terrain at
`z = 0.500` (spawned at 0.55, settled 0.05 m). See
[`verify/05-real-course-practice.png`](verify/05-real-course-practice.png).
The marble does **not** move on its own here — the arcade Practice start is flat, and
Marble Madness expects joystick input. That is the course's shape, not a pipeline fault,
but it does mean the real course has **not** been play-tested end to end by this work.

### 7. `task build` stays green

```
$ task build
...
=== Linking ===

Built: /home/will/WorldFoundry-wbniv-mm3d-fable/engine/wf_game
```

**PASS** — no engine C++ was touched.
