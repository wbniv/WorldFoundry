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

## Checklist: new actor not showing up

1. Is the actor position strictly inside a room bbox (not on the boundary)?
2. Is `Model Type` set to `Mesh` (or `Box`), not `None`?
3. Is `Visibility Mailbox` = 1 (always visible) or a live mailbox that is currently true?
4. Is the camera actually pointing toward the actor? Check Target/TrackObject positions.
5. Is the mesh file (`sphere.iff`, etc.) present in the level's asset list and built into the `.iff`?
