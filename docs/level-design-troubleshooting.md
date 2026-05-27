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

### 4. Object too thin in camera-depth axis — invisible

**Symptom:** Mesh actor has correct `Class Name`, `Model Type = Mesh`, `Visibility Mailbox` set to a true mailbox (or forced `=1`), valid `.iff` mesh on disk with a FLAT_SHADED MATL (`flags=0`, opaque color), and is comfortably inside a room bbox — but is invisible in-game. `RenderActor3DAnimates` log count matches the actor count (so the actor *did* get a renderer constructed). All the usual offenders below check out clean.

**Cause:** The mesh is **too thin along the camera-depth axis** for the rasterizer / depth pass to draw anything. For the SMB side-scroller (camera at Y=−20 looking +Y, X-Z is the screen plane), a coin disc authored as `(X half-extent 0.3, Y half-extent 0.04, Z half-extent 0.3)` — i.e. 8 cm thick in Y — never appears even though the 60 cm × 60 cm X-Z face *is* the camera-facing surface. The pre-shipped commit `8a4f822` SMB `?`-block coin hit this.

Note: this is distinct from the older "wrong-coordinate-system" variant where the *long* axis ended up along Y and the camera saw the thin edge; here the orientation is correct, but the thickness itself is too small.

**Fix:** Bump the thickness in the camera-depth axis until it renders. For SMB W1-1's camera at Y=−20 looking +Y, **Y half-extent ≥ ~0.2 m (40 cm total)** worked; 0.04 (8 cm) did not. The exact threshold is probably renderer + viewport dependent — bisect if you need the minimum.

**How to diagnose quickly:** force `wf_Visibility Mailbox = 1` (always-on hardwired) so script logic is taken out of the loop, blow the geometry up to a 3 m cube to confirm the actor reaches the render path, then shrink it down dimension by dimension until it disappears — the last dimension you shrunk is the camera-depth axis and the threshold lives there.

---

### 5. Per-actor collision mailboxes are dead under Jolt physics

**Symptom:** Forth script that reads `INDEXOF_COLLIDER_IDX`, `INDEXOF_COLLISION_NORMAL_X/Y/Z` (mailboxes 3044–3047, added by [`f4071a3`](https://github.com/anthropics/wf/commit/f4071a3) — per-actor collision mailboxes) never sees a non-zero value during *interactive* play, even though the same script behaves correctly when the bridge directly `set_mailbox`'es those values. SMB W1-1's `?`-block "bump from below" trigger looks like this:

```forth
INDEXOF_COLLIDER_IDX read-mailbox 0<> if
  INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 > if
    ... flip block to USED, spawn coin ...
  then
then
```

— the `0<>` guard fails every tick because `COLLIDER_IDX` stays 0.

**Cause:** [`wfsource/source/physics/collision.cc:513-520`](../wfsource/source/physics/collision.cc) explicitly *skips* populating the legacy collision event list whenever either object is Jolt-managed (has a valid `JoltCharacterID`). The skip avoids double-resolving physics — but `Actor::Collision()` is *only* called from the legacy event-list path (`collision.cc:309-310`), so for any Jolt-managed actor (the player, anything with a CharacterVirtual), `_lastColliderIdx` and `_lastCollisionNormal` are never written. They stay at their `Actor::StartFrame()` reset values (zero) forever.

`jolt_backend.cc` does not call `Actor::Collision()` or write the per-actor mailbox fields — there's no Jolt contact listener wired to that path.

**Fix:** Engine change — hook Jolt's character/contact callback to call `Actor::Collision(otherActor, normal)` for Jolt-managed actors. Tracked in [TODO.md](../TODO.md) under engine bugs. Until that lands, anything depending on per-actor collision mailboxes only works via bridge `set_mailbox` injection, not interactive play.

**Workaround for level scripts:** Don't rely on `COLLIDER_IDX` / `COLLISION_NORMAL_*` for trigger logic. Use alternatives like Z-velocity sign transitions, Z position thresholds, or pre-placed `ActBoxOr` trigger volumes that fire via their own activation mechanism.

---

### 6. `write-actor-mailbox` on `X/Y/Z_POS` is mesh-offset, not absolute world position

**Symptom:** A Forth script animates an anchored actor's position by writing `INDEXOF_Z_POS` (3011) — say, an SMB `?`-block coin that should pop up and fall back over 60 ticks — but the actor either teleports off-screen on the first write, or moves by twice the expected amount, or stays put.

**Cause:** `EMAILBOX_Z_POS` writes update `_position`, which the renderer concatenates onto the mesh vertices via `Matrix34(orientation, position)` ([`renderassets/rendacto.cc:466`](../wfsource/source/renderassets/rendacto.cc)). The *visible* world Z is therefore `mesh_vertex_z + _position.z`. Two authoring patterns exist in the codebase, and they need *different* script conventions:

- **Mesh-in-local-space** (qbert popup pattern — [`wflevels/qbert_practice/blender_create_qbert.py`](../wflevels/qbert_practice/blender_create_qbert.py) `_make_popup_actor`): mesh vertices centered at origin, `actor.location` set separately. Exporter records `Position = actor.location`, mesh bbox is local. Z_POS writes are **absolute world Z**. Idle: `actor.location.z = baked`; on write: `_position.z = new_world_z` overrides.
- **Mesh-in-world-space** (SMB `add_box()` pattern — [`wflevels/smb_w1_1/blender_create_smb.py`](../wflevels/smb_w1_1/blender_create_smb.py)): `bpy.ops.mesh.primitive_cube_add(location=…)` + `transform_apply(scale=True)` bakes location into vertices; `actor.location` ends up at origin. Exporter records `Position = (0,0,0)` and mesh bbox in world coords. Z_POS writes are **additive offsets** on top of the world-baked mesh — writing `world_z` would push the actor to `world_z * 2`.

You can tell which variant any given actor is by reading its `.lev` entry: look at `Position` and the `Global Bounding Box`. If Position is `(0,0,0)` and the bbox is in real world coords, it's the world-baked variant. If Position is the world location and the bbox is centered near origin, it's the local variant.

**Fix:** Match the convention to the authoring style. For world-baked meshes, write just the *delta* (e.g. `0 → 3 → 0` for a 3 m up-then-down arc) and skip any "world Z" addition. For local meshes, write absolute world Z.

**Trap when copying patterns**: the SMB W1-1 coin originally copied the qbert popup_500 snippet *literally* (`7.5 + write-actor-mailbox`) without noticing the authoring difference, and the coin spent ~1 s at world z ≈ 15 m where nobody could see it. Now corrected in [`8a4f822`](https://github.com/anthropics/wf/commit/8a4f822) → [`856f69c`](https://github.com/anthropics/wf/commit/856f69c).

---

### 7. Visibility Mailbox value

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

## "Blender build renders flat gray / untextured" → check the CamShot toggles first

A level can look completely untextured/gray when the textures are perfectly fine —
the culprit is often the **CamShot tracking toggles**, not the texture pipeline.
The BungeeCam `Rotation` (`Fixed|Track`) and `Position X/Y/Z` (`Absolute|Relative`)
enums decide whether the camera follows the player. With `Fixed`/`Absolute` the
camera parks at the CamShot's static pose and ignores `Track Object` — on a level
that's mostly white/gray (e.g. a snow level) that static view shows little colour,
which reads as "untextured."

Before suspecting textures: confirm faces are actually drawn textured (atlas bound,
white vertex colour) — e.g. force a known-good camera and look. If the *same* level
looks colourful from one camera and gray from another, it's the camera. (2026-05-22
snowgoons-blender investigation: the whole "untextured" symptom was `camshot_12`
exporting as Fixed/Absolute instead of Track/Relative.)

## A decompiled `.lev` enum field whose DATA and STR disagree is corrupt

A `{ 'I32' { 'NAME' "Rotation" } { 'DATA' 0l } { 'STR' "Track" } }` is **invalid** —
`DATA 0` means index 0 (`Fixed`) but the label says `Track` (index 1). A stale/buggy
decompile can emit these; the Blender importer used to silently trust `DATA`, which
flipped Track→Fixed on round-trip. The importer now **hard-fails** on such a
mismatch (`export_level.py` enum branch) — regenerate the `.lev` from the binary
with the current levcomp if you hit it.

---

## `ActBox` aborts the instant it fires — "attempt to write to mailbox #0"

**Symptom:** you place an `ActBox` trigger volume (e.g. to write `END_OF_LEVEL`), the player
enters it, and the engine aborts: `AssertMsg: attempt to write to mailbox #0, which is not
allowed` ([`mailbox.cc:63`](../wfsource/source/game/mailbox.cc) — mailboxes 0 and 1 are reserved,
`mailbox >= 2`).

**Cause:** `ActBox::activate` ([`actbox.cc:84`](../wfsource/source/game/actbox.cc)) writes the
activator's index to the **`Activated Actor Mailbox`** field *unconditionally* — and that field
**defaults to 0** ([`actbox.oas`](../wfsource/source/oas/actbox.oas)). So an ActBox configured
with only `MailBox`/`MailBoxValue` (leaving `Activated Actor Mailbox` at its default) crashes the
moment it triggers. The `MailBox` write (your real payload, e.g. `END_OF_LEVEL`) happens first
and *succeeds*; the very next line — the activator write to mailbox 0 — is what aborts.

**Fix (level-side):** set `Activated Actor Mailbox` to a valid mailbox (≥ 2). If you don't need
to record who triggered it, send it to a scratch slot — `SCRATCH_USER_START = 4005` (the 4000s
are the scratch range). Example from the SMB flagpole
([`blender_create_smb.py`](../wflevels/smb_w1_1/blender_create_smb.py)):

```python
flagtrig['wf_MailBox']                 = 1905   # INDEXOF_END_OF_LEVEL
flagtrig['wf_MailBoxValue']            = 1
flagtrig['wf_Activated By Actor']      = 'Player'
flagtrig['wf_Activated Actor Mailbox'] = 4005   # scratch — discard the activator (must be >= 2)
```

The engine-side alternative (guard the write so `0` means "don't record") is logged in
[`TODO.md`](../TODO.md) § ENGINE ROBUSTNESS but deferred.

---

## Added a mailbox to `mailbox.inc` but scripts using its `INDEXOF_` fail (`error 7 not_a_word`)

**Symptom:** you add a `MAILBOXENTRY( FOO, … )` row to
[`mailbox.inc`](../wfsource/source/mailbox/mailbox.inc), rebuild with `task build`, but every
Forth script referencing `INDEXOF_FOO` is silently rejected (`zforth compile error 7 (...):
not_a_word`) — and since zForth compiles each script as a unit, the *whole* script dies (even
unrelated lines), so e.g. an enemy stops moving entirely.

**Cause:** the script-side `INDEXOF_*` constants come from `mailboxIndexArray` in
[`engine/stubs/scripting_stub.cc`](../engine/stubs/scripting_stub.cc), which `#include`s
`mailbox.inc`. The incremental build keys on the `.cc` mtime, **not** the `#include`d `.inc`, so
editing only `mailbox.inc` relinks the binary with a **stale** `scripting_stub.o` — the new
constants never make it in. (Confirm: `strings engine/wf_game | grep INDEXOF_FOO` → MISSING.)

**Fix:** force the recompile — `touch engine/stubs/scripting_stub.cc wfsource/source/mailbox/mailbox.cc`
then `task build`. Re-check `strings engine/wf_game | grep INDEXOF_FOO` → PRESENT. (Surfaced
2026-05-25 adding the SMB enemy/respawn mailboxes; see
[the plan](plans/2026-05-25-smb-enemy-walk-stomp.md).)

---

## Player↔enemy (and other CharacterVirtual↔CharacterVirtual) contact doesn't fire collision logic

**Symptom:** two `MOBILITY_PHYSICS` actors (e.g. Mario and a Goomba) collide *physically* (they
push each other) but neither's `COLLIDER_IDX`/`COLLISION_NORMAL_*` mailboxes populate, and any
`Actor::Collision`-driven logic never runs.

**Cause:** `MOBILITY_PHYSICS` actors are Jolt **CharacterVirtual** bodies, which aren't in
`gBodies`, so `JoltContactDispatch`'s `FindActorForBodyID` can't resolve the other party — the
character-vs-character contact is resolved for *movement* but never dispatched to
`Actor::Collision`. (Same reason the `Gold` coin uses proximity pickup, not `Collision`.)

**Fix:** use **proximity** instead — broadcast the player's X/Z to globals and have the other
actor compare against its own `X_POS`/`Z_POS` (squared distance avoids needing `abs`). The SMB
Goomba/Koopa stomp-vs-hurt detection works this way (`blender_create_smb.py` `ENEMY_SCRIPT`).
Collision mailboxes *do* work for character-vs-**static** (e.g. the `?`-block, an anchored
Generator in `gBodies`).

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

## Assembling the `cd.iff` bundle — feed cdpack the **standalone** IFFs, not the bare LVAS

**Symptom:** Running `wf_game` with no `-L` (default `cd.iff` path) aborts immediately
while opening the bundle:

```
AssertMsg: Attempted to read past end of chunk: ALGN  count = 12, _bytesLeft = 4
iff/iffread.cc:108
```

or, one layer deeper, after the bundle opens:

```
plmc->tagRam == IFFTAG('R','A','M','\0')   level.cc:426
```

**Cause:** `cd.iff` is a `GAME` form whose `TOC` lists `SHEL` + N level bodies
([cdpack-rs](../wftools/cdpack-rs/src/main.rs)). Two ways to get it wrong:

1. **No `GAME`/`TOC` envelope** (the `ALGN count=12` abort). The loader reads
   each 12-byte TOC entry as `{ tag, offset, size }` ([disktoc.cc](../wfsource/source/iff/disktoc.cc)).
   If the file is a bare level chunk (e.g. a single `L4`+`ALGN`, what you get by
   copying a `-standalone.iff` straight to `cd.iff`), the loader reads a phantom
   12-byte entry out of the alignment padding and runs off the end. Always build
   `cd.iff` through cdpack, never by hand.
2. **Wrong level-body flavor** (the `tagRam` abort). `game.cc:250` seeks to
   `tocLevelEntry._offsetInDiskFile + SECTOR_SIZE` — **one sector past** the TOC
   offset — before reading the `RAM`/`OBJD`/`PERM`/`ROOM`/`FLAG` config. So each
   level body needs a leading `ALGN` sector. The **`-standalone.iff`** (`L4`-rooted,
   `RAM\0` at its own offset 2048) has it; the bare **`*.iff`** (`LVAS`-rooted) does
   **not**. Feed cdpack the `-standalone.iff` files.

**Fix / reproducible build** (`task build-cd-iff`):

```bash
cargo build --release --manifest-path wftools/cdpack-rs/Cargo.toml
wftools/cdpack-rs/target/release/cdpack \
  wfsource/source/game/shell.fth \
  wflevels/snowgoons-standalone.iff \
  wflevels/qbert_practice-standalone.iff \
  -o wfsource/source/game/cd.iff
```

Level order = TOC order: `GetTOCEntry` is a plain array index ([disktoc.hpi:48](../wfsource/source/iff/disktoc.hpi)),
so the TOC tags are cosmetic — the first level argument becomes level 0 (the
default `_desiredLevelNum`), the next is level 1, etc. `shell.fth` selects the
boot level via `INDEXOF_LEVEL_TO_RUN`.

> Regression note: commit `527c15f` (2026-05-16) rebuilt `cd.iff` by hand and
> dropped the `GAME`/`TOC`/`SHEL` envelope, producing the `ALGN count=12` abort.
> The `build-cd-iff` task exists so this can't recur silently.

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

## Texture atlas empty / Room0.tga is 146 bytes

**Symptom:** After `textile-rs` runs, `Room0.tga` is only 146 bytes (4×16 pixels). The mesh
material has `TEXTURE_MAPPED` set and references a TGA file that exists, but the atlas
contains only zeros. The mesh renders as solid colour with no texture applied.

**Cause:** Two bugs in `wftools/textile-rs/src/bitmap.rs` interact:

1. `rgba_555()` returns `0x0000` (the BGR555 transparent key) when alpha > 170 — i.e. for
   every fully-opaque pixel in a standard RGBA (32-bit) TGA. Every pixel becomes 0x0000.

2. `find_existing()` compares the all-zero texture pixel data against the newly-initialized
   all-zero atlas. They match, so the texture is falsely considered "already present." The
   blit is skipped, the allocation map records no usage, and the atlas crops to its minimum
   no-data size.

`Room0.ruv` still records the correct texture name and dimensions (from the dedup-match path
before blitting), so the engine starts without errors but finds only transparent pixels.

**Fix:** Generate textures as **24-bit RGB** TGA, not 32-bit RGBA. PIL uses 24-bit when you
create the image with `Image.new('RGB', ...)`. `textile-rs` detects `bpp=24` and takes the
`try_load_tga_bgr555()` fast path which calls `br_colour_rgb_555()` with no alpha logic.

```python
img = Image.new('RGB', (W, H), (255, 255, 255))   # 24-bit RGB, no alpha channel
```

**Verification:**

```bash
ls -lh Room0.tga       # > 1 KB for a real texture
xxd Room0.tga | head   # first pixels should NOT be 0x0000
```

`Room0.ruv` having a correct entry does NOT prove the texture was blitted.

---

## Texture colour disappears in-game (transparent key 0x0000)

**Symptom:** Texture looks correct in an image viewer but text or dark regions are invisible
in-game. Background colour renders fine; dark foreground disappears.

**Cause:** The engine uses BGR555 colour `0x0000` as the transparent pixel key.
`br_colour_rgb_555(r, g, b)` rounds each channel to 5 bits: any colour with all channels
below 8 produces `(0, 0, 0)` = 0x0000 = transparent.

```
(20, 20, 20) → br_colour_rgb_555 → (0, 0, 0) = 0x0000 → transparent (invisible)
(40, 40, 40) → br_colour_rgb_555 → (1, 1, 1) = 0x0421 → opaque ✓
```

**Fix:** Use a minimum channel value of 8 in any colour that must be opaque. For dark text,
`(40, 40, 40)` is a safe minimum that is visually near-black and rounds to a non-zero
BGR555 value.

**Rule:** no intentionally-opaque colour should have all three RGB channels below 8.

Full root-cause analysis: [docs/investigations/2026-05-16-textile-rs-rgba555-dedup-bug.md](investigations/2026-05-16-textile-rs-rgba555-dedup-bug.md).

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

> **Caveat (Jolt):** the `Surface Friction` rows above are effectively **dead under the Jolt
> backend** — `MarbleHandler::predictPosition` never reads `Surface Friction`, and the legacy
> wheel-friction path that did is skipped because `supportingObject` is never set for a Jolt
> `CharacterVirtual`. The only horizontal-velocity decay that actually applies to a
> doom-stick/marble actor is `Running Deceleration`. See the next section.

---

## "I set Surface Friction / Air Drag to 0 but the actor still stops dead on landing"

**Symptom:** A coin / projectile / marble has `Surface Friction = 0` **and** `Horiz Air Drag =
0`, drifts correctly while airborne, but **freezes its horizontal position the instant it lands**
— it won't slide.

**Cause:** Under Jolt, `Surface Friction` and the air-drag fields are **not consulted** for
doom-stick/`MarbleHandler` actors (TurnRate == 0). The *only* horizontal decay applied is
`Running Deceleration` (`movement.cc:689`, `MarbleHandler`: `vel.X *= 1 - RunningDeceleration *
dt * 30`; `:233`, `GroundHandler`: same). Its movebloc default is **0.90** — that's ≈ a full
stop within a single frame, so any actor that doesn't override it loses all horizontal momentum
on contact. (Airborne motion is fine because `AirHandler` doesn't apply this decay.)

**Fix:** Set **`Running Deceleration = 0`** on the actor. Setting `Surface Friction` / `Air
Drag` to 0 does **not** do it. Example: the SMB `?`-block coin (`blender_create_smb.py`
`_make_coin_template`) is meant to keep its generator-imparted +X drift and slide rightward
along the ground; it only does so with `Running Deceleration = 0` (with the 0.90 default it
froze the moment it landed — verified by [tests/verify_coin_slide.py](../tests/verify_coin_slide.py)).
See [the gold-value follow-up plan](plans/2026-05-25-smb-gold-value-wire-and-doc-fix.md).

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

## Spawning a new OAD class → `terminate called without an active exception`

**Symptom:** The instant a newly-added actor class is *constructed* (e.g. a
`Generator` throws a new collectible), the engine prints
`terminate called without an active exception` and dies — with **no** assertion
message and **no** `fell out of room` line (distinguishing it from the room-bbox
crash above). The last useful log line is often a benign render warning like
`RenderActor3DAnimates constructed with no animations!`.

**Cause (the message is a red herring):** it's actually a **failed assertion**
wearing a disguise. Every actor's `kind()` asserts
`GetMovementBlockPtr()->MovementClass == <Name>_KIND`. If the new class was added
to [`objects.mac`](../wfsource/source/oas/objects.mac) but its **generated files
were hand-patched instead of regenerated** (or its `.ht` is a renamed-stopgap from
another class), the constructed object's `MovementClass` isn't `<Name>_KIND` and the
assert fails. `assert` calls `exit()`; during `atexit` the still-joinable debug-bridge
listener thread (`gListenerThread`) destructs while joinable → `std::terminate`,
which is what actually prints. The real failure is hidden one frame earlier.

**Confirm it:** run under gdb (`gdb -batch -ex run -ex bt -ex quit --args engine/wf_game …`).
The backtrace shows `Gold::kind` / `<Name>::kind` → `_sys_assert(... MovementClass == <Name>_KIND ...)`
→ `Actor::BindAssets` → `Level::ConstructTemplateObject`. (Repro harness:
[`tests/repro_gold_spawn_crash.py`](../tests/repro_gold_spawn_crash.py).)

**Fix:** don't touch the assert. Regenerate the OAD class properly — see
[Creating a new OAD (actor) class](level-building.md#creating-a-new-oad-actor-class)
in the building guide. The class is half-generated: regenerate `objects.*` and
`<name>.ht` from the masters, and add the `COLTABLEENTRY` rows (without them the
object also collides with nothing).

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

## Actor not rendering — "falls outside every room bbox" warning

**Symptom:** An actor is present in your `.blend` and exported to `.lev` but
invisible at runtime. The levcomp-rs build output contains a line like:

```
levcomp-rs: WARNING: actor "curse_bubble" world-center (0.00,0.00,-30.00)
falls outside every room bbox — it will not render in-game.
Expand the room actor in Blender to contain this actor.
```

**Cause:** levcomp-rs places each actor into the first room whose bounding box
contains the actor's world-space center point. If no room bbox covers that
center, the actor is omitted from all room render-entry lists. The engine never
constructs the actor's renderer, so it is completely invisible.

**Fix:** In Blender, select the room actor and enlarge its bounding box
(`RoomMinX/Y/Z`, `RoomMaxX/Y/Z` fields) until it encompasses the offending
actor's world-space position. Re-export and rebuild.

**Common cases:**
- Actor parked far off-screen at a "hidden" Z (e.g. Z = −30) while the
  room bbox only covers the visible play field.
- Actor added to the scene after the room bbox was last authored and the bbox
  was never updated to include it.

---

## Runtime actor indices do NOT match the .lev OBJECT ordering

**Symptom:** A Forth script uses `write-actor-mailbox` (or similar per-actor
write) with an actor index counted by hand from the `.lev` file's OBJECT
entries. The writes land on the wrong actor — usually one or two slots later
than expected — and the targeted actor visibly doesn't update (no position
change, no per-actor mailbox effect).

**Cause:** The engine's runtime actor list includes implicit actors at low
indices that are not OBJECT entries in the `.lev` (Level metadata actors,
Director, camera-internal actors, etc.). Indices in the `.lev` text are not the
indices the engine assigns. Off-by-one or off-by-two errors are common when
you count `.lev` OBJECTs in your head.

For example, SMB W1-1 currently yields this runtime ordering for the `?`-block
cluster — the first `?` block is at idx 12, not 8 or 9 (where it sits in the
`.lev`):

```
actor idx=12 mesh=qblock_00.iff
actor idx=13 mesh=qblock_00_used.iff
actor idx=14 mesh=qblock_00_coin.iff
actor idx=15 mesh=qblock_01.iff
```

**Fix:** *Always* read the index from `engine/wf_game --debug-print-actors`
output after a rebuild. The engine prints one `actor idx=N mesh=... pos=...`
line per actor at construction time, before the main loop. Grep for the mesh
filename — that's the canonical mapping.

**Don't:** trust an LLM/code agent's enumeration of OBJECT entries from the
`.lev` file. The agent will likely miscount and confidently report a wrong
index. (`feedback_check_class_names_before_comparing` covers the broader
"don't speculate, verify" principle.)

**Workflow if your hardcoded index might be stale:**

```bash
# After any level rebuild that adds/removes/reorders actors:
cd wfsource/source/game
LD_LIBRARY_PATH=../../../engine/libs DISPLAY=:0 \
  timeout 5 ../../../engine/wf_game \
    -L../../../wflevels/<level>-standalone.iff \
    --debug-print-actors --debug-port 7780 --debug-bind 127.0.0.1 \
    > /tmp/actorlist.log 2>&1
grep "actor idx=" /tmp/actorlist.log
```

Then update any `<index> write-actor-mailbox` literal in the Blender script.

## Spawned actor despawns instantly if it uses `startupData->currentTime` for TTL

**Symptom:** A generator fires and the spawned object appears for a single
frame (or is invisible entirely), then vanishes — even though the actor's TTL
(e.g. `kGoldTTL = 3.0f`) should keep it alive for seconds. The object IS
being constructed (you may see a brief flash), but its `update()` calls
`SetPendingRemove` on the very first tick.

**Cause:** `SObjectStartupData::currentTime` is a **value-copy** of the level
clock taken at level-load time (`level.cc:267`):

```cpp
startupData.currentTime = LevelClock();   // frozen at t≈0
```

`Clock::Current()` returns `_nWallClock` — a stored `Scalar`, not a live
reference. An actor constructor that initialises a despawn timer as:

```cpp
_despawnTime = startupData->currentTime.Current() + Scalar(kGoldTTL)
```

…produces `_despawnTime ≈ 0 + 3 = 3 s` regardless of when the spawn occurs.
Any coin spawned after t > 3 s into the session satisfies
`LevelClock().Current() >= _despawnTime` on the very first `update()` call.

**Engine fix (2026-05-22):** `SafelyConstructTemplateObject` in `level.cc`
now stamps the current clock onto `startupData` immediately before calling
the actor constructor:

```cpp
startupData->currentTime = theLevel->LevelClock();   // actual spawn time
Actor* retVal = ConstructTemplateObject( ... );
```

All spawnable actors constructed via `Generator` now receive the correct
spawn-time clock. Actor constructors that store
`startupData->currentTime.Current()` for expiry timers work correctly
without change.

**If you bypass the engine fix** (e.g. constructing actors through a
different path), use `theLevel->LevelClock().Current()` directly in the
actor constructor instead of `startupData->currentTime.Current()`.

---

## Generator + Template Object spawn position must clear collidable objects by ≥ template half-size

**Symptom:** `Generator` actor activation mailbox fires, FIRING prints, but no
instance appears in the world. With debug fprintf around
`Level::ConstructTemplateObject`, you see:

```
Generato::FIRING objectToGenerate=12 _idxActor=15
Generato: calling ConstructTemplateObject(idx=12, pos=(11.88,-0.12,7.77), vel=(0,0,8))
Generato: ConstructTemplateObject returned NULL (collision blocked or out of mem)
```

**Cause:** `SafelyConstructTemplateObject` (`level.cc:1586`) runs a collision
check at the *spawn position* before instantiating. If the template's
collision box (`coarse.minX..maxZ` from the OAD) overlaps *any* collidable
object in the room at that position, spawn is rejected. If the template has
no Poof fallback (`commonData->Poof == -1`), NULL is returned and the
generator silently swallows the failure (no assert, no log without
instrumentation).

**Specific gotcha — generator anchor vs. spawn position:** the generator
spawns at `_physicalAttributes.GetColSpace().GetCenter(currentPos()) +
displacement` (`generator.cc:118`), **not** at the authored Blender `location`.
The collision-space centre includes the generator's own mesh-offset. In SMB
W1-1's `coin_spawner_NN`, authored Z = `block_top + 0.4` (= 7.9), but the
generator's actual spawn Z came out as **7.77** — a 0.13 m drop from the
anchor. The coin template's half-Z is 0.3, so coin extents reached Z=7.47
while block top sat at Z=7.5 — a 0.03 m overlap, enough to fail the spawn
check on every bump.

**Fix / authoring rule:** As of the 2026-05-22 engine fix in `generator.cc`,
the generator automatically queries the template's colspace half-Z and offsets
spawn Z upward by that amount, so the spawned object's **bottom** lands at
`topZ` rather than its centre. No manual clearance calculation is needed when
using the qblock-as-generator pattern.

If using a generator without the auto-offset (older build or a different
spawn axis), position the generator so the *spawn position* clears the nearest
collidable surface by **at least the template's half-extent on the relevant
axis, plus margin**. For SMB's coin template (half-Z=0.75 after the NES resize),
anchor Z = `block_top + 1.0` gives clearance for reliable spawns.

**Verification workflow:** add a temporary fprintf around
`SafelyConstructTemplateObject` and `Generato::update`'s spawn site that
prints the computed `pos` plus the NULL/non-NULL return. The "Mario's bump
fires the script but no coin appears" failure mode is invisible without it —
the generator happily fires every pulse and silently drops every spawn.

**Don't:** rely solely on the Blender `location` to predict spawn position.
The mesh-offset can easily eat your margin if you reuse an existing template
or schema that anchors below its centroid. Always measure the actual `pos=`
in the spawn fprintf during bring-up.

## Generator spawn crashes with `terminate called without an active exception` after `AddObject`

**Symptom:** A `Generator` actor fires (`mailbox != 0`), `ConstructTemplateObject` returns non-NULL, `Level::AddObject` completes, then the engine immediately aborts with:

```
terminate called without an active exception
Aborted (core dumped)
```

A gdb backtrace at the crash shows:

```
#13 0x... in Actor::update at actor.cc:869
#14 0x... in Missile::update at missile.cc:125
#15 0x... in ObjectUpdate::operator() at movement/movementobject.cc:135
```

with `Actor::update`'s first assert (`HasRunPredictPosition()`) failing.

**Cause:** Frame pipeline has two passes that iterate the active-room
UPDATE list:

1. **PredictPosition** pass — sets each actor's `HasRunPredictPosition` flag.
2. **UpdatePhysics** pass (`for_each(iter, ObjectUpdate(...))` in
   `movement/movementobject.cc:159`) — calls each actor's `update()`
   which asserts `HasRunPredictPosition`.

A `Generator` that spawns a template instance via
`Level::AddObject` *inside* the UpdatePhysics pass appends the new
actor to the room's UPDATE list. The same `for_each` iterator picks up
the freshly-added actor and calls its `update()` — but
PredictPosition has long since finished, so the new actor has
`HasRunPredictPosition == false` and the assertion fires.

(Confusingly, the assertion failure routes through `_sys_assert` →
`exit(-1)` → `__run_exit_handlers` → some module's `std::thread`
destructor on a joinable thread → `std::terminate`. The "terminate"
message is the *downstream* symptom; the actual cause is the
asserted-false-`HasRunPredictPosition` upstairs in `Actor::update`.)

**Fix:** `Level::AddObject` marks the freshly-spawned actor with both
per-frame flags set to "looks like already ran this frame":

```cpp
physAttrib.HasRunPredictPosition(true);
physAttrib.HasRunUpdate(true);
```

`ObjectUpdate` honours `HasRunUpdate` and skips it; `DoneWithPhysics`
clears both flags between frames, so the new actor enters the normal
PredictPosition→Update flow on the *next* frame. Net effect: a
template-spawned actor sits parked at its spawn position for one tick
before its own scripts/movement start.

**Don't:** call `actor->update()` manually from `AddObject` to "make
up for the missed pass" — that re-enters the assertion path. The
clean handoff to next frame's pipeline is correct.

**Why this surfaces specifically for template instances:** pre-placed
actors are constructed and added to rooms during level load, before
any frame pipeline runs. They get their first PredictPosition+Update
pair cleanly on frame 0. Only runtime-spawned actors (generators,
explosions, etc.) ever land mid-frame.

---

## Physics tunnelling — Template coins fall through the floor on slow machines

**Symptom:** A physics-mobility template coin (spawned by a Generator from
`ConstructTemplateObject`) appears to vanish immediately after spawning —
it never renders. Verified by log: `AddObject ok, coin actor_idx=N`, then
two frames later the actor is re-added from "fell out of room" with `Z ≈ -11`.

**Cause:** Jolt character physics accumulates velocity per-frame using the full
frame `dt`. On a slow dev machine running at ~1 fps, `dt ≈ 1.0 s`. With
`FallingAcceleration = 12`, the coin gains `-12 m/s² × 1 s = -12 m/s` in a
single frame, plus any initial upward velocity (e.g. 8 m/s), giving a net
downward displacement of 4–16 m in frame 1. The 1.5 m-thick floor trimesh
is skipped entirely — **Jolt's character sweep tests the capsule from A to B
but can miss geometry if the displacement is larger than the shape diameter**.

**Fix:** Give the coin a TTL despawn in `update()` using `LevelClock().Current()`.
With a 1.5-second TTL the coin self-removes before it can tunnel, and the
behaviour matches the SMB arcade coin (brief arc then vanish) regardless of
framerate.

```cpp
// In constructor:
_despawnTime = startupData->currentTime.Current() + Scalar(1.5f);

// In update():
if (theLevel->LevelClock().Current() >= _despawnTime) {
    theLevel->SetPendingRemove(this);
    return;
}
Actor::update();
```

Use `LevelClock().Current()` (seconds), never "N ticks" — WF's loop is
variable-dt; tick counts are meaningless.

**Why the coin was invisible (not just underground):** At ~1 fps the coin spent
its entire above-floor time within frame 0's `predictPosition` call, before
`Actor::isVisible()` was ever tested. From the camera's perspective, the coin
was never rendered at all.

---

## New OAD class — objects.mac / gold.oad order of operations

**Symptom:** Adding a new OAD actor class and running the game causes
`assert(GetMovementBlockPtr()->MovementClass == Actor::Gold_KIND)` to fire,
disguised as `"terminate called without an active exception"` because `exit(-1)`
from the failing assert tears down a still-joinable debug-bridge thread.

**Cause:** `gold.oad` was generated *before* `Gold_KIND` was added to
`objects.mac`. The `oas2oad` tool writes the `MovementClass` field using the
enum value from `objects.lc` at generation time. If Gold_KIND doesn't exist
yet, MovementClass defaults to 0 (NULL_KIND). At runtime, `Gold::kind()`
asserts `MovementClass == Gold_KIND` and fires.

**Additionally:** `objects.{car,col,ctb}` (collision tables) are derived from
`objects.mac` via `coltab.pl`. If you add `OBJECTONLYTEMPLATEENTRY(Gold,1)` to
`objects.mac` but forget to regenerate the collision tables, `Actor::CanCollide()`
indexes past the end of the collision table (global buffer overflow, caught by
ASan as a stack-smash or silent wrong-answer).

**Fix — correct order:**

1. Add `OBJECTONLYTEMPLATEENTRY(Gold,1)` + `COLTABLEENTRY(Gold,...)` rows to
   `objects.mac`.
2. Run `task gen-oas-headers` (regenerates `objects.{c,e,h,inc,car,col,ctb}`
   from the `.mas`/`.mac` master files).
3. Generate `gold.oad` via `task oas2oad` — Gold_KIND now exists in objects.lc.
4. Rebuild the level binaries (`build_level_binary.sh <level>`).
5. Build the engine (`task build`).

Steps 3 and 4 must happen *after* step 1, not before.

---

## Blender re-export: stale object names from the imported base level

**Symptom:** After a headless `blender --background --python blender_create_smb.py`
re-export, the game crashes with a CamShot assertion, an actboxor "actor not found",
or a player-tracking failure.

**Cause:** `blender_create_smb.py` imports snowgoons.lev (or another base level) to
reuse meshes and camera rigs. That import carries the base level's object names —
`player_33`, `target_14`, etc. — into the `.lev` export. Any OAD `STR` field that
cross-references an object by name (Track Object, Target, Activated By Actor) will
reference the old base-level name, which `levcomp-rs` cannot resolve in smb_w1_1's
name table → silently falls back to index 0 → assert / wrong object selected.

**Affected fields and the fix pattern:**

After every `find_by_class()` / `find_by_name()` lookup in the Blender script, add
an explicit name and reference override:

```python
# Rename the imported player so CamShot Track Object + actboxor can find it
player = find_by_class('player')
if player:
    player.name = 'Player'            # override snowgoons "player_33"

# CamShot: set Target explicitly (imported base level had "target_14")
camshot['wf_Target'] = 'Target02'

# Actboxor: set Activated By Actor to match the renamed player
actboxor['wf_Activated By Actor'] = 'Player'
```

**General rule:** every object-reference `STR` field must be set explicitly in the
generator script. Never rely on the imported value surviving unchanged.

---

## Z-axis coin spin via `ROTATION_C` Forth script

**Goal:** Coin rotates about the WF Z-axis (up) at 1 rev/sec, stateless, no C++
changes.

**Script:**

```forth
\ wf
INDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox
```

**How it works:**

- `INDEXOF_TIME` (mailbox 1906) returns the current level time in seconds as a float.
- Writing that value to `INDEXOF_ROTATION_C` (mailbox 3014) sets WF Euler angle C
  (heading / Z-rotation) in revolutions.
- `Angle::Revolution(Scalar)` internally calls `AsUnsignedFraction()`, which strips
  the whole-number part. So time=1.7 s → 0.7 revolutions — wraps cleanly as time
  grows, no `fmod` needed in the script.
- Result: exactly 1 rev/sec Z-axis spin driven by absolute time, so even a coin that
  spawns late has a coherent orientation with no accumulated error.

**In `blender_create_smb.py`:**

```python
COIN_SCRIPT = "\\ wf\nINDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"

def _make_coin_template():
    ...
    obj['wf_Script'] = COIN_SCRIPT
    return obj
```

**Note:** WF Euler C is the Z-rotation (heading), not `ROTATION_A` (pitch/X) or
`ROTATION_B` (roll/Y). See CLAUDE.md "WF Euler angles" for the axis mapping.

---

## LMalloc FileLine alignment invariant

**Symptom:** UBSan or ASan fires with "member access within misaligned address … for
type 'struct DMalloc'" immediately after the first `LMalloc::Allocate()` returns.

**Invariant:** `sizeof(FileLine)` must be a multiple of `WF_POINTER_ALIGN` (8 on
64-bit). The allocator layout is `[FileLine header | user data | int32 canary]`; the
user pointer is `block_start + sizeof(FileLine)`. Since `block_start` is already
8-byte aligned, user data is only aligned if `sizeof(FileLine) % 8 == 0`.

With `LMALLOC_TRACK_SIZE=1, LMALLOC_TRACK_LINE_AND_FILE=0`:

```
_state (int32, 4) + _size (int32, 4) = 8 bytes ✓
```

**Trap:** Adding *any* odd-sized field (e.g. `int32 _pad` on 64-bit only via
`#if SIZE_MAX > 0xFFFFFFFFUL`) makes `sizeof(FileLine) = 12`, breaking alignment for
every subsequent allocation. The fix is to leave the struct at the natural 8-byte
size; the comment in `lmalloc.cc` documents the invariant explicitly so it doesn't
get broken again.


## Per-actor scale is visual-only — collision and physics don't scale

**Symptom:** You scale an actor (via the `X/Y/Z_SCALE` mailboxes 3040–3042, or — once
wired — Blender object scale) and the mesh visibly stretches, but the actor still
collides, blocks, and is walked on as if it were its original size.

**Why:** The scale is applied **at draw time only** — `Actor` caches `_scaleX/Y/Z`
and forwards them to `RenderActor3D::SetActorScale`, which column-multiplies the world
matrix just before rendering (`wfsource/source/game/actor.cc:1606-1622`). Nothing
propagates that scale to the collision bbox (`coarse` rect in the on-disk record) or
to the Jolt physics shape, so collision and physics keep the unscaled geometry.

**What to do:**

- For **purely visual** scaling (squash/stretch effects, decorative size variation
  with no gameplay collision — e.g. qbert), this is fine and intended.
- For a size change that must **affect gameplay** (a genuinely bigger crate you stand
  on or bump into), make it a **real mesh edit in Blender** and re-export — the mesh
  is the golden source of an object's true size.
- A first-class "scale that also scales collision + physics" (Jolt `ScaledShape`,
  authored as Blender object scale) is a tracked follow-up, deferred until after the
  next level ships — see `TODO.md` § *DEFERRED UNTIL LEVEL*.


## Multi-room levels & cross-room warps (the SMB pipe warp)

The SMB W1-1 pipe → underground coin room ([plan](plans/2026-05-25-smb-pipe-warp-coin-room.md))
is the **first genuinely multi-room WF level**, and the room-transition path had several
non-obvious gotchas. If you build a second room or a room-to-room warp, read this first.

### How a cross-room warp actually works

A "warp" is just **teleporting the player into a different room's bounding box** — either
the `Warp` actor (`SetPredictedPosition`) or a script writing `INDEXOF_X/Y/Z_POS`. Both are
Jolt-safe (`jolt/physical.hpi::Update()` explicitly pushes WF-side warps into the Jolt
character). The room system then follows on its own:

- `ActiveRooms::UpdateRoom(watchObject)` ([actrooms.cc:293](../wfsource/source/room/actrooms.cc))
  runs each frame with `_camera->GetWatchObject()` (the player). When the player leaves
  `_activeRooms[0]`'s bbox it loops over **every** room and switches to the first one whose
  bbox contains the player. **Adjacency is NOT required for the switch** — it's a full scan.
- **The rooms must partition space CONTIGUOUSLY — touching, NOT gapped.** Two competing
  constraints:
  - For the **switch**: the warp destination must be unambiguously inside the *target*
    room and outside the source room, so the player leaves `_activeRooms[0]`. SMB drops
    Mario to Z=−46.5, far below the surface room's Z=−10 floor.
  - For the **camera**: the rooms' bboxes must **touch with no gap** (SMB: surface
    Z[−10,25] meets coin Z[−58,**−10**] at the −10 plane). The camera entity *physically
    pans* between camshot poses; if there's an empty Z band between the rooms it lands in
    "no room" mid-pan, stops updating, and **freezes** there (it renders the destination
    room from a wrong, too-high angle, or a black screen). An earlier draft of this note
    said "disjoint with a gap" — **wrong**; a gap freezes the camera. Make them adjoin.
    (The shared boundary plane is harmless: the player is never parked exactly on it.)
- The one transition frame prints `Room::UpdateRoomContents: object N … fell out of room 0
  … re-adding` — **harmless**; `AddObjectToRoom` re-homes the actor to whatever room now
  contains it. A `… is not in any room` line is **also not a crash** — it's a graceful
  `SetPendingRemove` ([rooms.cc:188](../wfsource/source/room/rooms.cc); the old assert is
  `#if 0`). It means the destination coords missed every room bbox — fix the coords.

### Required objects / properties for a second room (each bit was a real bug)

1. **The player needs `Moves Between Rooms = True`.** Without it the player's mesh binds to
   the *source* room's transient asset slot and **unloads on the switch** → Mario vanishes
   underground. (Anchored markers — targets, camshots — have no asset and don't need it.)
2. **Each room needs its OWN light.** Lights are room-scoped; the surface light unloads on the
   switch, so the destination renders **pure black** (engine logs ` has no lights, gonna be
   hard to see!`, [level.cc:1200](../wfsource/source/game/level.cc)). Add a directional light
   inside each room's bbox. (No matte needed underground — black is SMB-faithful.)
3. **Each room that the camera visits needs a CamShot framing it.** The surface camera's
   Position Z is `Absolute`, so it will *not* follow the player down — the underground needs
   its own camshot (e.g. a static shot over the coin room).
4. **The rooms must be MUTUALLY ADJACENT for the camera to follow.** This is the subtle one:
   the **camera entity is updated only via the active room's update list**
   ([level.cc:948-964](../wfsource/source/game/level.cc); `updateMainCharacter` merely sets
   `_mainCharacter` — the camera is *not* a special/global actor). With a hard switch the
   camera lives in the now-inactive source room and **freezes at its last pose**, never
   adopting the new shot → the destination room renders off-camera (black). Listing the two
   rooms as each other's `Adjacent Room 1` keeps **both** active simultaneously
   (`MAX_ACTIVE_ROOMS = MAX_ADJACENT_ROOMS + 1 = 3`, [assets.hp:39](../wfsource/source/asset/assets.hp)),
   so the camera keeps ticking and follows. `adjacentRooms[0]=self` is implicit
   ([room.cc:152](../wfsource/source/room/room.cc)) — author only the neighbour.
   `levcomp-rs` resolves `Adjacent Room 1/2` by name ([rooms.rs](../wftools/levcomp-rs/src/rooms.rs)).

### `INDEXOF_CAMSHOT` is **1921**, not 1021

`MAILBOXENTRY( CAMSHOT, 1921 )` ([mailbox.inc:59](../wfsource/source/mailbox/mailbox.inc)).
An ActBoxOR (or Director) that switches cameras must write `MailBox = 1921`. The
`level-building.md` mailbox-scope table said 1021 — **wrong** (now corrected). Writing the
wrong slot fails *silently*: the camera keeps reading the bootstrapped shot and never
switches (it looks exactly like a frozen / dead camera). Verify against the engine's
`zforth: INDEXOF_CAMSHOT = 1921` boot line.

### ActBoxOR fires via C++ overlap, regardless of the script engine

`ActBoxOR::update` ([actboxor.cc](../wfsource/source/game/actboxor.cc)) activates through
`Activation::Activated()` (a pure AABB overlap test), like `ActBox` — **not** through a
script. The old `level-building.md` claim that "ActBoxOR zones never fire with scripting
disabled" is false (corrected). A fresh ActBoxOR switched the camera fine with Tcl disabled.
Size its activation volume to cover the player's reachable area in the room, centred on the
**play plane** (Y≈0), not the room-bbox Y-centre (which may sit far back where the camera is).

### `room.copy()` carries a stale `Adjacent Room`

Duplicating the imported room with `room.copy()` is the easy way to get a second room (it
inherits the room schema + Mobility/MovementClass), but it also copies the snowgoons room's
self-adjacency name (e.g. `room_6`). **Overwrite `Adjacent Room 1/2` explicitly** on both
rooms or you get a dangling reference.

### The down-press warp gate (pure composition, no engine change)

The `Warp` actor is **collision-only** — it teleports on overlap with no input gate, so it
can't do "press Down at the pipe." Compose it instead:

- an **`ActBox`** at the pipe mouth (a thin Z band *above* the pipe top so only standing on
  top triggers it, not walking past on the ground) sets a mailbox (`SMB_AT_PIPE`) on overlap,
  with `ClearOnExit=True` to reset it;
- the player's per-tick script ANDs that mailbox with the joystick **DOWN** bit
  (`EJ_BUTTONF_DOWN = 0x1000 = 4096`) and reuses the **respawn teleport** (write
  `X/Y/Z_POS` + zero the velocities) to drop into the coin room.

Use a pure `Warp` + `Target` for the *exit* pipe (walk-into, no gate needed) — that's exactly
what `Warp` does natively, and it validates the `Warp` class's Jolt teleport.

> **Warp renders its volume as a white box.** Unlike `actbox.oas`/`actboxor.oas` (which
> `@define DEFAULT_MODEL_TYPE 3` = None), `warp.oas` has no such override, so the box mesh
> you give the Warp for its activation volume draws as a white debug cube. Setting
> `wf_Model Type='None'` doesn't help (the exporter doesn't emit it for the warp schema).
> Force it invisible with **`wf_Visibility Mailbox = 0`** (mb[0] = always false) — activation
> is independent of rendering, so the Warp still fires.

### Verifying camera moves on the bridge — resume, don't step

In pause/`step` bridge mode each step advances a tiny `dt`, so camera **pans/slews barely
move** (a CamShot switch pans over its Pan Time, and the per-frame slew clamp is 10 units/axis
— see the camera-slew section in [level-building.md](level-building.md)). Drive the warp with
`step` for determinism, then **`resume`** and sleep real-time before screenshotting so the
camera pan to the new shot completes. (Headless GL is low-fps, so allow a few seconds.)
The same applies to **walking** the player a distance: in `step` mode each frame's `dt` is
tiny so he barely moves — `resume` + hold the joystick bit (`inject_input` with a long
`duration_frames`) and poll, instead of one `step` per injected frame.

### A warp-landing floor must be WIDE and THICK

The floor the player warps *onto* needs more margin than a normal walking floor. The teleport
can land the character a hair inside the slab; Jolt's `CharacterVirtual` then depenetrates him
— sometimes **sideways**. SMB's first coin-room floor was the usual narrow (Y±1.5) 1-tile-thick
slab; the warp-landing drifted Mario to Y≈−2.2, off the Y edge, and he fell out the room
bottom. Make a warp-landing floor wide (Y±5) and thick (≥4 units) so landing jitter can't push
him off it. (Adding actors elsewhere — e.g. coins → more Jolt static bodies → slower broadphase
→ bigger `dt` — makes the landing penetrate more, so don't tune this to the bare minimum.)

### Collectible coins in a room (the `gold` TTL blocks pre-placing)

`gold` coins can't be pre-placed: `Gold`'s despawn TTL is a hardcoded `kGoldTTL = 5.0f`
([gold.cc](../wfsource/source/game/gold.cc), no OAD field) stamped at construction, so a
coin placed at level-load vanishes 5 s in — long before the player reaches a warp room. Two
working alternatives:

- **Static disc + player-script proximity pickup** (used by the SMB coin room): a `statplat`
  gold disc with `Visibility Mailbox = <per-coin global mb>` (seeded to 1 once by the player
  script, like the lives seed), and the player script awards `GOLD` and flips that mailbox to
  0 (hides the coin) when close. Gate the proximity on **both** X *and* a player-Z band — the
  coin room shares the surface's X range, so the Z test (`|z − coinRoomFloorZ|` small) is what
  stops a surface coin at the same X from firing. **Float the discs clear above the player's
  head** — a collidable `statplat` at body height shoves him (and can push him through a thin
  floor); pickup uses the *player's* Z, not the coin's, so coin height is free.
- **Generator-on-entry**: an ActBox triggers a `Generator` (Object To Throw = a coin template)
  while the player is in the room, so coins spawn fresh (collectible within their 5 s).

## Script-driven bounce off the floor — read the contact normal, and consume it

A collectible/actor can bounce off the ground from its own Forth script (no engine
restitution exists — every `MOBILITY_PHYSICS` actor is a kinematic Jolt `CharacterVirtual`
that zeroes vertical velocity on landing; `mRestitution` is never set, and the
`Vertical/Horizontal Elasticity` OAS fields are dead pre-Jolt legacy). The SMB Starman bounce
does it by re-launching `ZSPEED` on the real landing contact. Three non-obvious facts make or
break this:

- **Landing on static ground gives `COLLIDER_IDX = 0`, not an actor index.** The ground has no
  WF `Actor`, so the contact routes through `Actor::JoltStaticCollision(normal)`
  ([`actor.cc`](../wfsource/source/game/actor.cc)), which sets `_lastColliderIdx = 0`. So a
  `COLLIDER_IDX != 0` gate (correct for *actor-vs-actor* hits like the `?`-block bump) will
  **never fire** on a floor landing. Gate on the normal instead.
- **The landing normal points DOWN: `COLLISION_NORMAL_Z < 0`.** The contact normal is "the
  direction the character pushes against the contacted body" — falling onto the floor pushes
  down, so `Z < 0` (a bump-from-*below* gives `Z > 0`). Floor-landing gate: `NORMAL_Z -0.5 <`.
- **`_lastCollisionNormal` is NOT cleared per-frame** (only `_lastColliderIdx` is, at
  `StartFrame`, `actor.cc:1106`). So the normal goes **stale** and a bare normal gate re-fires
  every frame — including mid-air. Either also require descent (`ZSPEED 0 <`) or, cleaner,
  **consume** it: `COLLISION_NORMAL_Z` is script-writable, so write `0` to it after acting, and
  it only goes non-zero again on a genuine new contact. This keeps the bounce ground-aware —
  over a pit there's no contact, the normal stays 0, and the actor falls in.

```forth
\ Starman: re-launch upward on a real floor contact, then consume the normal.
INDEXOF_COLLISION_NORMAL_Z read-mailbox -0.5 < if
  6.0 INDEXOF_ZSPEED write-mailbox
  0 INDEXOF_COLLISION_NORMAL_Z write-mailbox
then
```

## A fast Generator-thrown object won't spawn near another actor (velocity-expanded spawn box)

`SafelyConstructTemplateObject` ([`level.cc`](../wfsource/source/game/level.cc)) runs a collision
pre-check before constructing, and **expands the candidate's ColSpace by `velocity × LevelClock
delta`** before testing — so a *fast* spawned object reserves room in its direction of travel.
A fireball thrown at +12 reserves ~`12 × dt` ahead of its nominal spawn point (and under the debug
bridge, where a step can inject a larger dt, that reach grows). If that expanded box overlaps any
actor the template collides with, the spawn returns **NULL** (or constructs the template's `Poof`).
Symptom: the Generator logs `FIRING` but there's no `AddObject ok` — intermittently, depending on
dt and the other actor's exact position.

So when authoring runtime spawns (the SMB fireball pool generators), keep the spawn point clear of
other collidable actors by **more than `velocity × dt + both half-extents`**, not just the static
boxes. The SMB Fire Mario fireball spawns `1.8` ahead of Mario (not the original `1.2`) for exactly
this reason — `1.2` left only ~0.5 of slack, which Mario's idle +X drift plus the velocity
expansion intermittently closed.

## A killed actor (`ALIVE = 0`) is removed — its change-only mailbox watch freezes at stale values

Writing `0 INDEXOF_ALIVE` self-removes the actor at frame end. The debug bridge's `watch`
broadcasts are **change-only**, so once the actor is gone, no further updates arrive and the
watcher keeps reporting the **last pre-death value** — typically `ALIVE = 1` and a frozen position.
**Do not assert a kill by watching `ALIVE → 0`** (you'll see a stale `1` forever and conclude it
survived — this cost real debugging time on the SMB fireball-defeat test). Instead probe the
removal directly: `set_mailbox` on a removed actor replies `{"op":"error", "msg":"... actor not
found"}` ([`debug_server.cc:796`](../engine/stubs/debug_server.cc)). A frozen position + a
"not found" reply is the definitive "it died" signal.
(SMB Fire Flower + Star, 2026-05-26 — [plan](plans/2026-05-26-smb-fire-flower-and-star.md).)
