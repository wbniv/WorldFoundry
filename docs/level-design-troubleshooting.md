# Level Design Troubleshooting

A running log of gotchas encountered building WF levels. Sorted roughly by "how long it takes to diagnose."

---

## Coordinate systems — game, editor, and screen

### World coordinate system (WF / Jolt)

WF uses a **right-handed, Z-up** system, identical to Blender's default **Z-up** mode.
This means the same XYZ numbers in the Blender `.lev` export and in the game at runtime.

```
           Z (up / sky)
           |
           |
           o──────── Y (North / forward)
          /
         X (East / right)

Gravity acts in the −Z direction.
```

| Axis | World meaning         | Screen intuition (iso view from SW) |
|------|-----------------------|--------------------------------------|
| +X   | East / right          | Toward lower-right of screen         |
| +Y   | North / forward       | Toward upper-right of screen         |
| +Z   | Up                    | Toward top of screen                 |
| −Z   | Down (gravity)        | Toward bottom of screen              |

### Path headings

MM ROM path segments store heading as the lower byte of the `type` field —
**256ths of a full revolution, CCW from the +X (East) axis:**

```
         +Y (North)
         |   heading = 64/256 = 0.25 rev = 90°
         |
−X ──────o──────── +X   heading = 0/256 = 0° (East)
         |
         −Y (South)  heading = 192/256 = 0.75 rev = 270°

Heading 32/256 = 45° = NE diagonal (northeast)
Heading 13/256 ≈ 18° = ENE (Practice level)
```

### Player orientation — Euler C and `currentDir()`

`currentDir()` (`physicalobject.hpi:50`) returns **(cos C, sin C, 0)** —
**not** `(sin C, cos C, 0)` as the comment in `movement.cc:698` claims.
The comment is wrong; the implementation is authoritative.

| C (radians) | currentDir | faces |
|-------------|-----------|-------|
| 0 | (1, 0, 0) | +X |
| π/2 | (0, 1, 0) | +Y (into depth) |
| π | (−1, 0, 0) | −X |
| 3π/2 | (0, −1, 0) | −Y (toward camera) |

Doom-stick strafe (TurnRate=0): **StepRight = (sin C, −cos C, 0)** — 90° clockwise
from currentDir.

**Side-scroller recipe** (camera at Y < 0 looking toward +Y):

```python
player.rotation_euler.z = math.pi / 2   # C = π/2
```

| C | StepLeft | StepRight |
|---|----------|-----------|
| 0 (wrong) | (0, +1, 0) away from cam | (0, −1, 0) toward cam |
| π/2 (correct) | (−1, 0, 0) screen-left | (+1, 0, 0) screen-right |

See [`docs/investigations/2026-05-15-wf-coordinate-system-and-currentdir.md`](investigations/2026-05-15-wf-coordinate-system-and-currentdir.md)
for the full numeric chain (levcomp-rs u16 encoding → Angle::Sin/Cos → Scalar × 2π).

---

### Blender editor vs. WF game

Blender's default orientation matches WF exactly (both Z-up, Y-forward):

```
Blender viewport (front ortho, default):     WF game (iso camera from SW):

         Z                                              Z
         |  Y (into screen)                             |   Y (into screen)
         | /                                            |  /
         |/                                             | /
         o──── X                                        o──── X

No axis flip needed.  Numbers authored in Blender are correct in-game.
```

### Camera offset → screen view

The BungeeCam adds `CamShot` offset to the player's world position each frame.
Choosing the offset determines what part of the level the player sees:

```
Top-down view of path going North (+Y):

        N (+Y)
        ▲
        │  ← path runs this way
        │
 W ─────○───── E (+X)          ○ = player/marble
        │
        S

Offset (−8, −8, +10):          Offset (+8, −10, +10):
Camera is SW + above.          Camera is SE + above.
Looks NE + down.               Looks NW + down.
Path goes upper-right.         Path goes upper-left.

     SW camera view:                SE camera view:
  ┌─────────────────┐           ┌─────────────────┐
  │       /path     │           │  path\          │
  │      /          │           │       \         │
  │     ○ (marble)  │           │  (marble) ○     │
  │                 │           │                 │
  └─────────────────┘           └─────────────────┘

For a level going mostly North, the SE camera (+X, −Y, +Z) shows the path
receding to the upper-left — closest to the classic isometric arcade view.
```

### Room bbox = global bounding box of all actors

The room bbox must strictly contain:
- All renderable geometry (path mesh, decorations)
- The Camera entity position (`SPAWN_POS + CAMSHOT_POS`)
- The CamShot entity (absolute world position = `CAMSHOT_POS`)
- All lights
- All targets, trigger volumes (ActBox), etc.

**Rule:** Set room bbox = bounding box of all scene objects + ~2-unit margin.
A too-small room causes `fell out of room` crashes when actors drift near the edges.

```python
# Quick check: for each actor at world pos P,
# all of these must be true:
assert ROOM_POS.x - abs(ROOM_LOCAL_BBOX[3]) < P.x < ROOM_POS.x + abs(ROOM_LOCAL_BBOX[3])
assert ROOM_POS.y - abs(ROOM_LOCAL_BBOX[4]) < P.y < ROOM_POS.y + abs(ROOM_LOCAL_BBOX[4])
assert ROOM_POS.z - abs(ROOM_LOCAL_BBOX[5]) < P.z < ROOM_POS.z + abs(ROOM_LOCAL_BBOX[5])
```

---

## Object not appearing in-game (invisible)

### 1. Object placed on room bbox boundary → assigned to PERM

**Symptom:** Object is in the level file, no crashes, but never renders.

**Cause:** `levcomp` assigns each object to a room by checking whether its position falls *strictly inside* a room's bounding box. If the position lands exactly on the boundary (e.g. Z equals the room's `maxZ`), the object falls through to PERM (the permanent/global pool), which is outside the room render list.

**Fix:** Move the object at least a small epsilon inside the room. If the room ceiling is Z=5.0, place the object at Z=4.5 or 4.9.

---

### 2. Camera FOV culling — object behind or off to the side of the camera

**Symptom:** Object is in the correct room, Visibility Mailbox=1, but never visible.

**Cause:** The renderer frustum-culls objects outside the camera FOV. With FOV=50° the half-angle is 25°; an object more than 25° from the camera centre is culled even though it exists and has a mesh.

**Root cause in practice:** The BungeeCam `Target` / `TrackObject` objects were far from the player, causing the camera look direction to point away from the player. See the [BungeeCam section](#bungecam-target-placement) below.

---

### 3. ModelType = NONE → `CanRender()` returns false

**Cause:** `actor.cc CanRender()` checks `GetMeshBlockPtr()->ModelType != MODEL_TYPE_NONE`. If the mesh block's `Model Type` field is `None` (enum value 3), the actor is skipped entirely before any visibility check.

**Fix:** In the OAD / `.lev` mesh block, set `Model Type` to `Mesh` (for a `.iff` mesh file) or `Box` (AABB debug box). The field uses `SHOW_AS_DROPMENU`; in a `.lev` text block it looks like:

```
{ 'STR' "Mesh" }   // no { 'DATA' } needed for enum fields
```

---

### 4. Visibility Mailbox value

**Cause:** `actor.cc isVisible()` reads `GetMeshBlockPtr()->VisibilityMailbox`. Mailbox 0 is *always false*; mailbox 1 is *always true* (hardwired in `mailbox.cc`). Actor-local mailboxes start at index 2000 (`EMAILBOX_LOCAL_START`).

| Value | Effect |
|-------|--------|
| 0 | Always invisible |
| 1 | Always visible |
| 2–1999 | Level-global mailbox (scripted) |
| 2000+ | Actor-local mailbox |

**Fix:** Set `Visibility Mailbox = 1` for any unconditionally visible object.

---

## "no animations" warning at runtime

**Symptom:** Console prints something like `RenderActor3DAnimates: no animations`.

**Cause:** The actor type uses `RenderActor3DAnimates` which expects skeletal animation data. A static mesh (UV sphere, simple geometry) has no animation tracks.

**This warning is harmless.** The mesh renders in its rest pose. Suppress it by switching the actor's render class to one that does not expect animations, or ignore it during level bringup.

---

## BungeeCam: target placement {#bungecam-target-placement}

The BungeeCam handler (`movecam.cc BungeeCameraHandler::update`) computes:

```
direction = (Target - Follow + TrackObject) - cameraPosition
```

where `Target`, `Follow`, and `TrackObject` are actor world positions.

**Common setup:** `Follow` at origin (0,0,0) world anchor, `TrackObject` = the player, `Target` = a fixed offset above the player's spawn point. The camera then looks from its current elastic position toward `(player_pos + offset)`.

**Gotcha:** If `Target` is placed far from the player (e.g. 10 units away in Y), the computed look direction tilts sharply toward `Target`, not toward the player, and the player ends up 30°+ off-screen.

**Rule of thumb:** `Target` should be within ~1 unit of the player's spawn position, with a small upward offset (e.g. `(0, 0, 0.5)`) so the camera looks slightly above the ball's centre.

### Marble Madness specific: CamShot Target = Player, not Target02

**Symptom:** Camera shows the path walls head-on (or looking through them) instead of looking down at the marble; the marble is off-screen or barely visible.

**Cause:** CamShot `Target` set to a fixed world-space empty (`Target02`). As the marble moves along the path the camera look direction stays pinned to the fixed point, not the ball. On a trough level the fixed point may end up inside or behind a wall.

**Fix:** Set CamShot `Target` to `'Player'`:

```python
obj['wf_Target'] = 'Player'
```

The BungeeCam then tracks the marble's actual position each frame, so the look direction always points at the ball regardless of where it is on the path.

---

## Camera sight line blocked by trough wall

**Symptom:** Marble is on the path and `Target` = `'Player'`, but the path geometry obscures the marble — the west or south wall fills the viewport.

**Cause:** With a SW isometric camera the sight line from the camera to the marble passes through the west trough wall. The wall top is at `Z = scale(h_left)` while the camera z at the wall's XY position is below that.

**Condition:** Sight line clears the wall when:
```
camera_z - 0.5 * (camera_z - marble_z) > wall_top_z
```
i.e. the midpoint of the camera-to-marble line is above the wall top.

**Fix:** Increase the CamShot Z offset until the condition holds. For `PATH_HALF=2.0` and `GAME_UNIT=0.05`, west wall tops reach z ≈ 4–5.5 m above the goal plane. A CamShot offset of `(-6, -8, 10)` from the marble puts the sight-line midpoint at z≈6.6, clearing walls of up to 6.6 m.

---

## Camera initial position (`SetCameraParametersFromShot`)

`CamShot01` sets the camera start position and initial look direction:

```cpp
outPos.direction = targetPos - camShotPos;  // Target02 - CamShot01
```

`Target02` is the look-at point at frame 0. Place `CamShot01` behind and above the player, `Target02` at or near the player spawn.

**Example that works for a ramp level:**

| Object | Position |
|--------|----------|
| Player | (0, 0, 4.5) |
| CamShot01 | (0, −2, 7) |
| Target01 (Follow) | (0, 0, 0) — origin anchor |
| Target02 (TrackObject / look-at) | (0, 0, 5.0) — just above player |

---

## How to run a standalone level

```bash
cd wfsource/source/game
DISPLAY=:0 engine/wf_game -L/abs/path/to/level-standalone.iff
```

The standalone wrapper format:

```
{ 'L4'
    { 'ALGN' .align( 2048 ) }
    { 'RAM'
        'OBJD' 100000l
        'PERM' 300000l
        'ROOM' 300000l
        'FLAG' 1l 1l    // doomStickFlag, bungeeCamFlag
    }
    { 'ALGN' .align( 2048 ) }
    [ "../level.iff" ]
}
```

Build the standalone with:

```bash
cd wflevels/<name>
bash ../../wftools/wf_blender/build_level_binary.sh <name>
iffcomp-rs -binary -o=../<name>-standalone.iff <name>-standalone.iff.txt
```

---

---

## Mesh material: use FLAT_SHADED for simple geometry

**Symptom:** Mesh actor has correct `Model Type = Mesh`, `Visibility Mailbox = 1`, and a valid `.iff` file, but appears invisible or washed-out.

**Cause:** The `_MaterialOnDisk` struct in the mesh IFF has `_materialFlags = TEXTURE_MAPPED (2)` and references a texture (e.g. `G_SnowyGrass1.tga`) that isn't available in the level's atlas. The runtime falls back to `emptyTexture` (zero-size), which may render as black or be clipped by the depth pass.

**The `textile` tool** packs referenced textures into the room atlas (`Room0.tga`) and emits `Room0.ruv` for UV remapping. If the source mesh references a texture from a different level, the atlas won't contain it and the lookup silently returns `emptyTexture`.

**Fix:** Use `_materialFlags = FLAT_SHADED (0)` with a solid color for new geometry (no texture lookup, no atlas dependency). In the Blender export script, set material flags to 0 and pick an explicit RGB color. To patch an existing `.iff` binary:

```python
import struct
with open('ramp.iff', 'rb') as f: data = bytearray(f.read())
# MATL data offset: find 'MATL' tag, skip 8-byte header
# struct: 4(flags) 4(color=R<<16|G<<8|B) 256(texName)
# flags=0 → FLAT_SHADED; color=0x00FF8000 → orange
struct.pack_into('<I', data, matl_data_offset, 0)           # flags
struct.pack_into('<I', data, matl_data_offset + 4, 0x00FF8000)  # color
data[matl_data_offset+8:matl_data_offset+264] = b'\x00'*256  # no texture
with open('ramp.iff', 'wb') as f: f.write(data)
```

After patching rebuild the level IFF and standalone:

```bash
cd wflevels/<name>
iffcomp-rs -o=../<name>.iff <name>.iff.txt
iffcomp-rs -binary -o=../<name>-standalone.iff <name>-standalone.iff.txt
```

---

## Mesh face normals

WF's `glpipeline` renderer does **not** enable `GL_CULL_FACE`. Faces are always drawn regardless of winding order.

However, face normals (computed in `rendobj3.cc` via cross-product during load) affect lighting. A face whose normal points away from the dominant light source will receive less light and may appear dark. For a ramp or floor surface the normal should point generally upward (+Z).

**Rule of thumb:** Export the mesh with normals pointing away from the surface in the direction the player/camera faces it.

---

## Marble actor OAD configuration (MarbleHandler)

A "marble" actor uses `MarbleHandler` instead of `GroundHandler`. The handler is selected automatically when the actor's `TurnRate` OAD field is exactly `0.0`; AirHandler transitions to MarbleHandler (rather than GroundHandler) on landing.

**Required OAD values for a marble actor:**

| Field | Value | Why |
|-------|-------|-----|
| `Turn Rate` | `0.0` | Selects MarbleHandler on landing |
| `Max Air Speed` | ≥ 50 | **Must not be 0** — see gotcha below |
| `Horiz Air Drag` | `0.0` | Marble keeps horizontal momentum while airborne |
| `Vert Air Drag` | `0.0` | Falling speed accumulates unimpeded |
| `Air Acceleration` | `0.0` | No mid-air steering |
| `Jumping Acceleration` | `0.0` | No jump |
| `Running Deceleration` | ~0.05 | Rolling friction (lower = less friction) |
| `Max Ground Speed` | ~20 | XY speed cap while rolling on ground |
| `Falling Acceleration` | ~9.8 | Gravity magnitude |

MarbleHandler carries the full 3D velocity each frame. Gravity accumulates in Z; Jolt projects the Z component onto the slope normal, producing downhill motion. `Max Ground Speed` caps only the XY components so the ball does not roll infinitely fast.

---

## Marble barely moves on a gentle slope — `Running Deceleration` too high

**Symptom:** Marble spawns on a downward slope but crawls or stops immediately; reducing friction has no effect.

**Cause:** `Running Deceleration` is applied as an artificial reverse-thrust every frame when the joystick is at rest.  On a 2.2° slope gravity ≈ 0.38 m/s². Any `Running Deceleration` above ~0.35 exceeds this and the net acceleration is negative — the ball decelerates to zero and stays there.

**Fix:** Set `Running Deceleration` to `0.0`.  Let surface friction alone determine rolling resistance.  Typical working values:

| OAD field | Value |
|-----------|-------|
| `Running Deceleration` | `0.0` |
| `Surface Friction` (player) | `0.3` |
| `Surface Friction` (mesh/statplat) | `0.2` |

Combined friction ≈ 0.06; the ball rolls down grades of 4°+ without joystick input.

---

## Marble frozen at spawn — `MaxAirSpeed = 0` kills gravity in AirHandler

**Symptom:** Marble spawns on the ramp but never moves; position is constant every frame.

**Cause:** `AirHandler::predictPosition` applies a speed cap:
```cpp
if (newSpeed > maxSpeed)
    newVelocity *= (maxSpeed / newSpeed);
```
When `MaxAirSpeed = 0`, `maxSpeed = 0`, and the condition `newSpeed > 0` is immediately true on the first frame that gravity accumulates any velocity. The entire `newVelocity` vector is zeroed, including the gravity component. The marble can never fall to the ramp surface, so `JoltCharacterIsOnGround` never returns true and MarbleHandler is never selected.

**Fix:** Set `Max Air Speed` to a value large enough that normal free-fall never hits it — `50.0` is a safe default. The value `0.0` does **not** mean "unlimited"; it means the speed cap is zero.

---

## Marble stuck in AirHandler — slope classified as `OnSteepGround`

**Symptom:** Marble spawns above a sloped surface, falls (position decreases in Z), but never transitions to MarbleHandler; it passes through or bounces off the slope indefinitely.

**Cause:** Jolt's `CharacterVirtual` classifies the contact surface as `OnSteepGround` when the slope angle exceeds `mMaxSlopeAngle` (set in `jolt_backend.cc`). `AirHandler` transitions only when `JoltCharacterIsOnGround` returns true, which requires `GetGroundState() == OnGround` — not `OnSteepGround`. With the old default of 45°, a ramp at exactly 45° was classified as steep and the marble never landed.

**Current setting:** `mMaxSlopeAngle = 80°` (raised 2026-04-30). Slopes up to 80° register as `OnGround`.

**Rule of thumb:** Keep ramp angles below 75° to stay safely under the limit. If you need steeper geometry (walls, near-vertical chutes), it will register as `OnSteepGround` and the marble will slide off rather than roll.

---

## Marble / sphere physics on slopes: velocity accumulation

*(Historical note: this section describes the `GroundHandler` approach that predates `MarbleHandler`. Marble actors now use `MarbleHandler` which is not affected by this issue. The fix described here is still in `jolt_backend.cc` and benefits non-marble characters on slopes.)*

**Symptom:** Character on a sloped surface moves extremely slowly (~0.001 WF-units/frame).

**Cause:** `JoltCharacterUpdate` clamped `vel_z` to 0 whenever `GetGroundState() == OnGround`. `GroundHandler` adds one frame of `−gravity × dt` to `newVelocity` each frame, but since `vel_z` was zeroed after the previous step, the slope only receives a single frame's worth of gravitational impulse per frame.

**Fix (implemented):** In `jolt_backend.cc:JoltCharacterUpdate`, only clamp `vel_z` when the ground normal is nearly vertical (`normal.z > 0.966`, i.e. slope < 15°). On inclined surfaces, `vel_z` accumulates between frames.

---

## Marble stops dead at ramp-to-floor junction

*(Historical note: this section describes a `GroundHandler` + `wheelVelocity` issue. Marble actors now use `MarbleHandler` which carries full 3D velocity directly and is not affected. The `velCache.Y` fix described here is still in `jolt_backend.cc`.)*

**Symptom:** Ball rolls freely down a slope but halts the instant it reaches flat ground.

**Cause:** `CharacterVirtual::GetLinearVelocity()` returns the *input* velocity, not Jolt's resolved post-constraint velocity. `GroundHandler`'s `wheelVelocity.Y` was never updated from the actual slope displacement, so Y velocity dropped to zero at the transition.

**Fix (implemented):** `jolt_backend.cc:JoltCharacterUpdate` computes effective Y velocity from the position delta:
```cpp
if (dt > 0.0f)
    e.velCache.SetY((newPos.Y() - e.posCache.Y()) / Scalar(dt));
```

---

## Actor falls out of room → `terminate called without an active exception`

**Symptom:** Game runs, then prints `Room::UpdateRoomContents: object N fell out of room 0; re-adding` followed by `is not in any room (or is in the wrong room at startup)` and then crashes.

**Cause:** The room's `Global Bounding Box` does not extend far enough in the direction the actor travels. `levcomp` assigns actors to rooms by checking whether the actor's world **position** falls strictly inside the room bbox — but the room also defines the *containment volume* checked by `Room::UpdateRoomContents` each frame. If the actor drifts outside, the re-add fails and the engine terminates.

**Fix:** The room bbox and the playfield geometry are independent. Extending a ramp mesh does not grow the room — you must update the room `Global Bounding Box` separately to cover the full volume the player can reach.

**Rule:** Room bbox Z-min must be lower than the lowest point the player can reach. For a ramp ending at Z=−4, set room Z-min to −10 or lower to give headroom.

**Debugging the out-of-bounds position:** `Room::UpdateRoomContents` only prints the object index and kind, not its coordinates. To get the actual position at crash time, temporarily add a print to `room.cc` before the `cerror` line:
```cpp
Vector3 pp = po->GetPhysicalAttributes().Position();
cerror << "pos=(" << pp.X().AsFloat() << "," << pp.Y().AsFloat() << "," << pp.Z().AsFloat() << ") ";
```

---

## Platform geometry must cover maximum ball overshoot distance

**Symptom:** Ball rolls down a ramp, transitions to a floor at the bottom, then flies off the far end of the floor into the void.

**Cause:** WF's game loop runs at a variable frame rate; when the machine is slow (dt capped at 0.2 s by `display.cc`), each physics step moves the ball further. A 45° ramp 8 m long gives the ball ~7.7 m/s horizontal velocity at the bottom. With a 0.2 s step, the ball travels 1.5 m per frame — it crosses a 7-unit floor extension in just five frames.

**Fix:** The landing zone after a ramp must be long enough to catch the ball at its maximum speed. For a 45° slope of length *L* metres, ball exit velocity is `sqrt(2 × g × sin(45°) × L) ≈ sqrt(13.8 × L)` m/s. At dt=0.2 s the ball moves `vel × 0.2` per frame; ensure the floor extends at least `vel × 1.0` m (five frames' worth) past the ramp base, plus gameplay space.

**Rule of thumb for marble-madness style ramps:** make the receiving floor at least 15–20 WF units deep before the next drop or wall.

---

## Multiple face colors in one mesh — per-face materialIndex

A single mesh IFF supports multiple materials.  The `MATL` chunk stores an **array** of `_MaterialOnDisk` structs (one per material), and each face record has a `materialIndex` field (int16) that selects which material applies to that face:

```
_TriFaceOnDisk  (8 bytes)
  int16  v1Index
  int16  v2Index
  int16  v3Index
  int16  materialIndex   ← index into the MATL array
```

The renderer batches consecutive faces that share the same materialIndex, then switches when the index changes.  Faces are sorted by materialIndex at load time so all faces for a given material are contiguous.

**To use multiple colors in one mesh:** emit a MATL chunk with N `_MaterialOnDisk` entries, then set each face's `materialIndex` to the appropriate entry (0-based).  The Blender exporter writes materialIndex from Blender's face material slot index — assign different materials to different face selections in Edit Mode and the exporter handles the rest.

**Still need separate actors for:** geometry that must be independently visibility-culled, independently positioned/animated, or that references different OAD schemas.

---

## IFF mesh face record format

When editing mesh IFF binaries by hand, the `FACE` chunk stores **8 bytes per face**:

| offset | type    | meaning        |
|--------|---------|----------------|
| 0      | uint16  | vertex index 0 |
| 2      | uint16  | vertex index 1 |
| 4      | uint16  | vertex index 2 |
| 6      | int16   | materialIndex (0-based index into MATL array) |

Face count = `FACE chunk size / 8`. (Not 6 — a common off-by-one when assuming packed uint16 triples.)

---

## Non-mesh actors need Mobility + MovementClass or engine crashes

**Symptom:** Engine assertion `Actor #N has invalid renderActor` immediately after level load.

**Cause:** Every actor whose OAD inherits from `MovingObject` / `PhysicalObject` requires both `Mobility` and `MovementClass` fields. If these are absent, the engine cannot construct the physics body, and the `renderActor` pointer stays null.

This affects actors created programmatically (e.g., via MCP Python scripts) where only explicitly set properties are exported. Actors edited through the Blender OAD panel automatically populate all OAD defaults, so this bites only scripted creation.

**Fix:** Set `Mobility` and `MovementClass` explicitly for every non-geometry actor. Correct values from `mm_practice_blender.lev`:

| OAD class  | Mobility  | MovementClass | Model Type |
|------------|-----------|---------------|------------|
| `director` | Anchored  | 20            | None       |
| `camera`   | Camera    | 13            | Box        |
| `light`    | Anchored  | 23            | None       |
| `levelobj` | Anchored  | 15            | Box        |
| `matte`    | Anchored  | 11            | Box        |
| `camshot`  | Anchored  | 16            | Box        |
| `actboxor` | Anchored  | 17            | None       |
| `target`   | Anchored  | 3             | Box        |
| `player`   | Physics   | 22            | Mesh       |
| `statplat` | Anchored  | (auto)        | Mesh       |
| `enemy`    | Path      | 6             | Box        |
| `missile`  | Physics   | 8             | Box        |
| `tool`     | Anchored  | 19            | None       |
| `room`     | (not set) | (not set)     | (not set)  |

`room` is a container, not a `PhysicalObject`, and needs none of these.

---

## Bool/enum OAD I32 fields require string labels, not integers

**Symptom:** Boolean OAD field (e.g. `Script Controls Input`) exported as `DATA 0l` even though the Python script set it to `1`. Actor ignores the flag — Player joystick does nothing, or engine asserts "tried to set input ... but 'Script Controls Input' wasn't set".

**Cause:** The wf_blender exporter resolves I32 enum fields by looking up the `STR` value in the OAD's allowed-values list (`False|True`, `Absolute|Relative`, etc.). If the property is set as a Python integer (`obj['wf_Script Controls Input'] = 1`), the exported STR is `"1"`, which doesn't match any enum label, so DATA defaults to `0` (the first option, `False`).

**Fix:** Use the string label from the OAD comment, not a raw integer:

```python
# Wrong
obj['wf_Script Controls Input'] = 1
obj['wf_Moves Between Rooms']   = 1

# Correct
obj['wf_Script Controls Input'] = 'True'
obj['wf_Moves Between Rooms']   = 'True'
```

Applies to any I32 field with a `//ValueA|ValueB` OAD comment. Numeric I32 fields (mailbox indices, MovementClass, etc.) still use Python ints.

---

## Goal-zone segment type 0x0D20 — h_left/h_right are not wall heights

**Symptom:** ROM-decoded path mesh has absurdly tall spikes (30+ m) at the end of the level.

**Cause:** Goal segments (MM segment type `0x0D20`, always `h_center = 5`) use a completely different internal layout from normal path segments. The values at offsets `+02`/`+04` (decoded as `h_left`/`h_right`) likely encode funnel attraction, visual animation, or entrance dimensions — not wall heights. Interpreting them as geometric heights with `GAME_UNIT = 0.5` produces 30+ m walls.

**Fix:** Detect goal segments by `h_center ≤ H_ZERO` (or by checking the segment type's upper byte `= 0x0D`) and replace with level-appropriate flat platform geometry at `Z = 0`. See `rom_to_blender.py` `build_path_mesh()`.

---

## Black screen — light orientation wrong

**Symptom:** Level loads and runs but the viewport is completely black. No geometry visible.

**Cause:** A directional light with rotation `(0, 0, 0)` (default Blender orientation) doesn't illuminate mesh geometry. The light direction ends up perpendicular to all surface normals, so the dot-product lighting gives zero illumination.

**Fix:** Set the light object's `rotation_euler` to `(π/2, 0, 0)` in the Blender/MCP script — this is a 90° rotation around X, pointing the light downward along Z:

```python
import math
light_obj = make_empty('Light01', LIGHT_POS, 'light', props={...})
light_obj.rotation_euler = (math.pi / 2, 0, 0)
```

This matches the orientation used by the working `mm_practice` level. When diagnosing a black screen, check light orientation BEFORE checking textures or visibility mailboxes.

---

## Black screen — Matte actor not configured

**Symptom:** Level loads, geometry is present, but background is black and no background colour is visible.

**Cause:** The Matte actor requires explicit `Matte Type`, `Background Color`, and `Visibility Mailbox` OAD fields. With only `Mobility`/`MovementClass`/`Model Type` set, the matte renders nothing.

**Fix:**

```python
make_empty('Matte', ROOM_POS, 'matte',
    props={
        'Mobility':           'Anchored',
        'MovementClass':      11,
        'Model Type':         'None',   # NOT 'Box' — see "debug box gotcha" below
        'Matte Type':         'Color',
        'Background Color':   0,
        'Visibility Mailbox': 1,
    })
```

> **Note:** Earlier guidance here suggested `Model Type='Box'`. That causes a
> random-coloured debug cube to render at the matte's world position, on top
> of the real geometry. Always use `'None'` for matte (and any other
> infrastructure actor with no real mesh). See "Infrastructure actors render
> as random-coloured debug cubes" below.

---

## Infrastructure actors render as random-coloured debug cubes (Model Type=Box)

**Symptom:** A small, oddly-coloured cube (often magenta, lime, olive, or grey) appears in front of real geometry. Sometimes appears to "obscure" a cube, an apex, or a target, and the colour is different on different runs.

**Cause:** `wfsource/source/game/actor.cc:398` (`MODEL_TYPE_BOX` branch in
`Actor::ConstructRenderActor`) instantiates `RenderActor3DBox(memory, min, max)` for any actor with `Model Type=Box`.  That class calls `MakeRandMaterialList(memory, 6)`, so the actor draws as a 6-material cube with **random colours generated at engine startup**. This is debug visualisation that was never gated off.

The OAS schemas for several "abstract" actor types (camera, levelobj, matte, camshot, target, etc.) default `Model Type` to `Box`. Any such actor inside the camera frustum will render as one of these random debug cubes.

In the Q✱bert MVP, the matte at `(0, 0, 6)` was inside the frustum and drew a magenta hex on top of the apex cube; four other Box actors (Camera, Level, cs_pyramid, cs_death) rendered offscreen but still occupied poly slots in the renderer.

**Fix:** Override `Model Type` to `'None'` on every infrastructure actor that has no real mesh:

```python
for obj in (levelobj, matte, camera, camshot, cs_death,
            target01, target02, director):
    obj['wf_Model Type'] = 'None'
```

The `player` and any `statplat`-mesh children should keep `Model Type='Mesh'` (they actually point at a `.iff`).

The proper long-term fix is to gate `RenderActor3DBox`'s random-material rendering behind a `SHOW_ABSTRACT_ACTORS_AS_BOXES` debug flag — but that is an engine change, out of scope for content-only level work.

---

## wf_blender exporter writes two `Mesh Name` fields per actor — the first wins

**Symptom:** Mesh actor that has both real Blender mesh data and a `wf_Mesh Name` property override (pointing at a hand-authored `.iff`) renders with the *Blender* mesh's material — not the override file's material. In the Q✱bert MVP this caused all 84 cubes to render white instead of their intended palette colours, even though `cube_state{0,1,2}.iff` had the right `MATL` chunks on disk.

**Cause:** `wftools/wf_blender/export_level.py:994` writes a `Mesh Name` line **before** iterating the OAS schema fields, exporting the Blender geometry to `<obj_name>.iff` (overwriting any same-named file in the level dir!). The schema iteration then emits a *second* `Mesh Name` line from the `wf_Mesh Name` override. The engine's lev parser uses the first occurrence; the override is silently ignored.

**Fix (until the exporter is fixed upstream):** After `bpy.ops.wf.export_level`, overwrite the auto-generated per-actor `.iff` with the intended hand-authored content. Example from `wflevels/qbert_practice/blender_create_qbert.py`:

```python
import shutil
bpy.ops.wf.export_level(filepath=OUT_LEV)

for row in range(NUM_ROWS):
    for col in range(row + 1):
        N = cube_index(row, col)
        for state_idx in range(3):
            src = os.path.join(SCRIPT_DIR, f'cube_state{state_idx}.iff')
            dst = os.path.join(SCRIPT_DIR, f'cube_{N:02d}_s{state_idx}.iff')
            shutil.copyfile(src, dst)
```

Alternative: use Empty Blender objects (no `obj.data.polygons`). Untested, but the exporter's `has_mesh` guard should skip the Blender-mesh emit path entirely. Verify by checking the exported `.lev` for duplicate `{ 'NAME' "Mesh Name" }` entries — a properly-routed Empty actor should have exactly one.

If the exporter is later fixed (e.g. by skipping the Blender mesh emit when `wf_Mesh Name` is non-empty), the post-export `shutil.copyfile` workaround becomes redundant and should be removed.

---

## Texture assertion: `width < map.GetXSize()+1` (width = 320)

**Symptom:** Engine crashes immediately at startup with assertion failure:

```
AssertMsg:width = 320, map.GetXSize()+1 = 257
|(ptrdiff_t)(width) < (ptrdiff_t)(map.GetXSize()+1)
|in file "wfsource/source/gfx/texture.cc" on line 74
```

**Cause:** `textile-rs` generates `pal0.tga` / `palPerm.tga` palette atlas files at 320 pixels wide by default (`pal_x_page = 320` in `config.rs`). On the PC/Linux build, the engine allocates palette PixelMaps at `VRAMPaletteWidth = 256` (see `vmem.hp`). Loading a 320-wide TGA into a 256-wide PixelMap asserts.

**Fix:** Change `pal_x_page` in `wftools/textile-rs/src/config.rs` from `320` to `256` and rebuild textile-rs:

```diff
-            pal_x_page:           320,
+            pal_x_page:           256,
```

This matches the engine's `VRAMPaletteWidth` on the PC path. The PSX path uses 320 (the value in `VIDEO_MEMORY_IN_ONE_PIXELMAP` branch of `vmem.hp`); set accordingly when targeting PSX.

---

## Camera exits room → level crashes or stutters

**Symptom:** At runtime: `Room::UpdateRoomContents: object N kind=13 ... fell out of room 0`. Camera actor exits the room bounds and the engine crashes or forces level done.

**Cause:** The BungeeCam entity's world position at runtime is `CamShot_position_offset + player_world_pos`. If the CamShot Z offset is large and the player spawns near the room ceiling, the camera ends up above `room_max_Z` and falls outside the room bbox.

**Fix:** When setting `ROOM_LOCAL_BBOX`, add enough headroom to accommodate the camera at its maximum expected Z:

```
camera_max_Z = player_spawn_Z + camshot_Z_offset
room_max_Z   = ROOM_POS.Z + ROOM_LOCAL_BBOX[5]   # must be > camera_max_Z
```

For example, if spawn is at Z=7 and camshot offset is Z=5, camera can reach Z=12. Set `ROOM_LOCAL_BBOX[5]` so that `ROOM_POS.Z + ROOM_LOCAL_BBOX[5] > 12` with margin.

---

## zForth: `and`/`or` silently broken — use `&` and `|`

zForth's primitive word for bitwise AND is `&`, not `and`; for bitwise OR it is
`|`, not `or`.  Writing `and` or `or` in a zForth script compiles without a
lexer warning but fails at runtime with:

```
zforth compile error 7 (defs): : myword ... and ...
```

Error code 7 = `ZF_ABORT_NOT_A_WORD`.  The entire word definition is silently
discarded — every tick it does nothing.  If the word is `cam-remap` the
`INDEXOF_INPUT` mailbox stays at 0 and the marble is uncontrollable.

**Fix:** replace `and` → `&` and `or` → `|` throughout.

```forth
\ WRONG — compiles but silently fails at runtime
over 2048 and if 10240 or then

\ CORRECT
over 2048 & if 10240 | then
```

Other bitwise primitives: `^` (XOR), `<<` (shift left), `>>` (shift right).
Other logical helpers defined in the WF bootstrap: `not` (= `0 =`), `<`, `>`,
`<=`, `>=`, `<>`.

---

## Checklist: new actor not showing up

1. Is the actor position strictly inside a room bbox (not on the boundary)?
2. Is `Model Type` set to `Mesh` (or `Box`), not `None`?
3. Is `Visibility Mailbox` = 1 (always visible) or a live mailbox that is currently true?
4. Is the camera actually pointing toward the actor? Check Target/TrackObject positions.
5. Is the mesh file (`sphere.iff`, etc.) present in the level's asset list and built into the `.iff`?
6. Does the mesh material use `FLAT_SHADED` (flags=0) or does it reference a texture in the level atlas?

---

## zForth scripts: `\n`, `\` comments, ASCII, dictionary size

Authoring `wf_Script` content from a Blender create-script (`blender_create_*.py`)
hits four traps that all silently break script execution. Fix all four together
when bringing up a new actor with non-trivial Forth.

**1. Use real `\n` newlines in Python strings, not `"\\n"` text.**
The wf_blender exporter (`export_level.py:1304`) escapes literal `\` to `\\` when
writing the .lev STR field. Python `"\n"` (1 char) round-trips to a real newline
at runtime. Python `"\\n"` (2 chars) round-trips to `\n` (backslash + n) — which
zForth treats as the unknown word `\` followed by `n`. Symptom: the first
statement in a script runs, the rest is silently skipped because zForth has no
`\` line-comment word.

**2. zForth has no `\` line-comment word. Only the FIRST line of an actor script is auto-skipped.**
The script handler (`engine/stubs/scripting_zforth.cc:275-279`) skips one leading
line as the sigil (typically `\ wf` or `\ wf description`). Every subsequent line
is fed to `zf_eval` verbatim. Starting a non-first line with `\` triggers
`ZF_ABORT_NOT_A_WORD` (error code 7) at compile time. For inline comments use
`( ... )` — `(` is the `_(` primitive (PRIM_COMMENT).

**3. Stay within ASCII inside script bodies.**
The tokenizer chokes on multi-byte UTF-8 (`→`, `—`, smart quotes, em-dashes).
Use plain `->`, `--`, `'`, `"`.

**4. `ZF_DICT_SIZE` is fixed and append-only.**
Every `: word ... ;` definition consumes dictionary slots; same word in two
actors compiles twice. If you see `zforth compile error 2` (`ZF_ABORT_OUTSIDE_MEM`)
at compile time, the dict is full. Remediation: bump `ZF_DICT_SIZE` in
`engine/stubs/zfconf.h` and rebuild the engine. Default raised 2026-05-03 from
16 KB to 64 KB to fit the Q✱bert MVP director + player scripts.

**Diagnosing all of the above:** watch engine stderr after each level boot for
`zforth compile error N` lines. Engine continues running with broken/missing
script handlers, so visual symptoms are misleading (e.g. "only one cube visible"
looks like a vis_mb misconfig but is actually rule 1).

**5. `if/else/then` only works inside a colon definition (compile mode).**
The script handler (`engine/stubs/scripting_zforth.cc` `RunScript`) splits the
Script field at the **last `;`**:
- Code **before** the last `;` is the "defs" section, eval'd directly in
  interpret mode.
- Code **after** the last `;` is wrapped in an auto-generated
  `: _wfsN ... ;` word that runs in compile mode.

zForth's `if/else/fi/then` are immediate words that emit jump targets — they
require compile mode. So this works:

```forth
\ wf
: stick INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;
stick 0x0800 & if 1 411 write-mailbox then    \ <-- after the last `;`, OK
```

But this fails with `zforth compile error 7 (defs)`:

```forth
\ wf
416 read-mailbox 0 = if 1 414 write-mailbox then   \ <-- BEFORE the first `:`, FAILS
: stick INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;
```

The error message is misleading — error 7 is `NOT_A_WORD`, but the actual
problem is `if` running in interpret mode where it doesn't know how to emit
its jump patch. Workaround: move the `if/else/then` lines *after* the last
`;`, or wrap them in their own `: name ... ;` definition.

## zForth standard-Forth gaps

The WF bootstrap is deliberately small. Words you may reach for that are
**not** defined: `2dup`, `2drop`, `2swap`, `nip`, `tuck`, `?dup`, `abs`,
`negate`, `min`, `max`, `+!`, `inc`, `dec`, `mod`. See
`memory/reference_zforth_bootstrap_words.md` for the full catalog and 1-line
inline workarounds. Common substitutions:

- `2dup` → `over over`
- `nip` → `swap drop`
- `abs` → `dup 0 < if 0 swap - then`
- `min` / `max` → `over over > if swap then drop` (min) / `<` (max)
- `+!` → `dup @ rot + swap !`
