# Level Design Troubleshooting

A running log of gotchas encountered building WF levels. Sorted roughly by "how long it takes to diagnose."

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

## Multiple face colors require multiple mesh actors

**Cause:** Each WF mesh IFF has exactly one `MATL` chunk (one `_MaterialOnDisk` struct) covering all faces. There is no per-face material index. A single mesh can only have one flat color or one texture.

**Fix:** Use separate actors with separate `.iff` files for geometry that needs different colors (e.g., orange ramp + green floor). Each is an independent `statplat` entry in the `.lev` with its own `Mesh Name`.

---

## IFF mesh face record format

When editing mesh IFF binaries by hand, the `FACE` chunk stores **8 bytes per face**:

| offset | type    | meaning        |
|--------|---------|----------------|
| 0      | uint16  | vertex index 0 |
| 2      | uint16  | vertex index 1 |
| 4      | uint16  | vertex index 2 |
| 6      | uint16  | padding / flags (always 0) |

Face count = `FACE chunk size / 8`. (Not 6 — a common off-by-one when assuming packed uint16 triples.)

---

## Checklist: new actor not showing up

1. Is the actor position strictly inside a room bbox (not on the boundary)?
2. Is `Model Type` set to `Mesh` (or `Box`), not `None`?
3. Is `Visibility Mailbox` = 1 (always visible) or a live mailbox that is currently true?
4. Is the camera actually pointing toward the actor? Check Target/TrackObject positions.
5. Is the mesh file (`sphere.iff`, etc.) present in the level's asset list and built into the `.iff`?
6. Does the mesh material use `FLAT_SHADED` (flags=0) or does it reference a texture in the level atlas?
