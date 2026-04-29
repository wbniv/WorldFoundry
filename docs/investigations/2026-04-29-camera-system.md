# Investigation: World Foundry camera system

**Date:** 2026-04-29
**Sources:** `wfsource/source/game/movecam.{hp,cc}`, `camshot.{hp,cc}`, `camera.{hp,cc}`, `actboxor.{cc}`, `gfx/camera.{hp,cc}`, `oas/{camshot,camera,actboxor,director}.oas`

---

## Architecture overview

```
Level layout                    Runtime
─────────────────               ──────────────────────────────────────────────
ActBoxOR (zone trigger)   →     writes index to EMAILBOX_CAMSHOT mailbox
CamShot (shot definition) →     NormalCameraHandler reads mailbox each tick
Camera  (actor)           →     CameraHandler::SetCamera() positions Camera actor
                                gfx/camera.cc  →  RendererBackend  →  view matrix
```

Four distinct actor classes participate. Director exists in the OAS but is currently empty — no camera logic.

---

## Actor types

### Camera

The physical camera actor that moves through the world. One per level; the player's view is always rendered from its position.

**OAS fields (`camera.oas`):**

| Field | Type | Default | Notes |
|---|---|---|---|
| Eye Distance | Fixed32 | 0.025 | Stereogram only |
| Eye Angle | Fixed32 | 2.5° | Stereogram only |
| Fogging Color | Color | black | — |
| Fogging Start Distance | Fixed32 | 10 | World units |
| Fogging Complete Distance | Fixed32 | 20 | World units |

The Camera actor has no position/orientation OAD fields — it is positioned entirely at runtime by the CameraHandler based on the active CamShot.

---

### CamShot

A named camera placement in the world. Defines where the camera sits, what it looks at, and how it behaves. Multiple CamShots coexist in a level; one is active at a time.

**OAS fields (`camshot.oas`):**

| Field | Type | Default | Notes |
|---|---|---|---|
| Camera | Object ref | — | The Camera actor this shot drives |
| Target (Look At) | Object ref | — | Object the camera faces |
| Follow | Object ref | — | Object the camera position is anchored to |
| Climb Rate | Fixed32 | 5 | Bungee-Cam mode only |
| Elasticity | Fixed32 | 10 | Bungee-Cam mode only |
| Track Object Mailbox | Int32 | 0 | Mailbox to read track-object index from |
| Track Object | Object ref | Player01 | Direct track object (mutually exclusive with mailbox) |
| Rotation | Toggle | Fixed | `Fixed` = camera faces a fixed look-at; `Track` = mirrors Follow object's rotation |
| Position X/Y/Z | Toggle ×3 | Relative | `Absolute` = camera placed at CamShot world position; `Relative` = offset from Follow object |
| FOV | Fixed32 | 50° | Field of view (1–180). **Stored but not applied — see Limitations.** |
| Roll | Fixed32 | 0 | **Disabled** (Euler/Matrix34 bug, `#pragma message` since ~2003) |
| Pan Time In Seconds | Fixed32 | 1.0 s | Transition time when switching **to** this shot |
| Hither | Fixed32 | 0.1 | Near clipping plane. **Stored but not applied — see Limitations.** |
| Yon | Fixed32 | 100 | Far clipping plane. **Stored but not applied — see Limitations.** |

**Position calculation** (from `SetCameraParametersFromShot` in `movecam.cc`):

```
camera.position.X = (PositionX == Relative) ? (camshot.X - follow.X) : camshot.X
camera.position.Y = (PositionY == Relative) ? (camshot.Y - follow.Y) : camshot.Y
camera.position.Z = (PositionZ == Relative) ? (camshot.Z - follow.Z) : camshot.Z
```

After rotation is applied (if `Rotation == Track`), the track object's position is added back per-axis according to the same `PositionX/Y/Z` flags.

**Look-at calculation:** `direction = Target.position - CamShot.position`. Up vector is always world `+Z` (roll is disabled).

---

### ActBoxOR (Activation Box Object Reference)

An invisible volume placed in the level that, when the player overlaps it, writes a CamShot actor index to a mailbox. This is the only camera-switching mechanism.

**OAS fields (`actboxor.oas`):**

| Field | Type | Default | Notes |
|---|---|---|---|
| MailBox | Int32 | 100 | Mailbox to write to (typically `EMAILBOX_CAMSHOT`) |
| Object (Camshot Object) | Object ref | — | The CamShot actor index written to the mailbox |

The camera system reads `EMAILBOX_CAMSHOT` every tick. The mailbox is **cleared to zero by `NormalCameraHandler::update()`** after it has been consumed — so the write from ActBoxOR is one-shot and edge-triggered, not persistent.

---

### Director

An invisible, non-rendering, non-updating actor (`CanRender()=false`, `CanUpdate()=false`) whose only purpose is to carry a **Script**. The C++ class (`director.cc`) is a stub — it never runs its own update logic. All behaviour comes from its `Script` field (inherited from `common.inc` like every other actor).

A Director placed in a level runs its script each tick via the scripting system. That script can write to mailboxes — including `EMAILBOX_CAMSHOT` — to trigger camera cuts, sequence cutscene events, control other actors, start timers, etc. It is the intended mechanism for scripted cinematic sequences that are not driven by player collision (unlike ActBoxOR).

**Director is camera-adjacent, not a camera system component.** It belongs to the scripting system. The OAS has no camera-specific fields because the script itself is the interface.

---

## CameraHandler hierarchy

All handlers live in `movecam.cc`. The active Camera actor's `MovementManager` holds one at a time.

```
CameraHandler  (abstract base)
├── DelayCameraHandler    — waits until EMAILBOX_CAMSHOT has a valid index
├── NormalCameraHandler   — steady-state: reads mailbox, calls SetCameraParametersFromShot, applies view
│   ├── PanCameraHandler  — lerps position/direction/FOV/Hither/Yon between old and new shot
│   └── BungeeCameraHandler — elastic follow using CamShot's Climb Rate + Elasticity
```

**State machine transitions:**

```
start
  └─► DelayCameraHandler
        └─► NormalCameraHandler   (when EMAILBOX_CAMSHOT != 0)
              └─► PanCameraHandler   (when shot index changes)
                    └─► NormalCameraHandler  (when pan time elapses)
```

`gBungeeCam` is a runtime global bool. When true, transitions go to `BungeeCameraHandler` instead of `NormalCameraHandler`. Both pan and normal paths check it.

**`SetCamera()` (`CameraHandler::SetCamera`, `movecam.cc:182`):**

Sets the Camera actor's position and orientation from a `cameraPosition` struct. Contains the unresolved pragma:

```cpp
#pragma message ("KTS: write field of view, hither and yon code")
```

FOV, Hither, and Yon are computed into `cameraPosition` correctly by every handler but are never forwarded to `RendererBackend::SetProjection()`.

---

## PanCameraHandler interpolation

When the shot index changes, `NormalCameraHandler::_update()` switches to `PanCameraHandler`. It captures the old shot as `origCam` and the new shot as `destCam`, then linearly interpolates all six fields each tick:

```cpp
pct = (clock.Current() - panStartTime) / destShot.PanTimeInSeconds

panCam.position  = lerp(origCam.position,  destCam.position,  pct)
panCam.direction = lerp(origCam.direction, destCam.direction, pct)
panCam.up        = lerp(origCam.up,        destCam.up,        pct)
panCam.field     = lerp(origCam.field,     destCam.field,     pct)   // unused at renderer
panCam.hither    = lerp(origCam.hither,    destCam.hither,    pct)   // unused at renderer
panCam.yon       = lerp(origCam.yon,       destCam.yon,       pct)   // unused at renderer
```

`Pan Time In Seconds` comes from the **destination** shot, not the source.

---

## Limitations

| Limitation | Detail | Fix effort |
|---|---|---|
| **FOV not applied** | Computed correctly into `cameraPosition.field`; never passed to `SetProjection()`. Global default is 60°. | ~1 line in `SetCamera()` |
| **Hither/Yon not applied** | Same path as FOV. Global defaults are `nz=1.0`, `fz=1000.0`. | Same 1-line fix |
| **Roll disabled** | `#pragma message("kts fix: put back when the euler/matrix34 problems are resolved")`. Euler/Matrix34 conversion was broken at the time. | Unknown — needs Euler investigation |
| **Perspective-only** | `backend_modern.cc` has only `Mat4Perspective`. No `Mat4Ortho`. | ~20 lines + OAD schema field (blocked on level-pipeline-proof) |
| **Director unused** | OAS entry exists, runtime class is empty. | — |

---

## How to use cameras in a level

### Minimal setup (single fixed shot)

1. Place a **Camera** actor anywhere — its world position does not matter (the handler overwrites it every frame).
2. Place a **CamShot** actor at the desired camera viewpoint. Set:
   - **Target (Look At)** → the object to face (typically the player or a fixed marker)
   - **Follow** → the player or whatever object the camera tracks
   - **Position X/Y/Z** = `Relative` to track the player with a fixed offset; `Absolute` to ignore the player position and stay fixed
3. Place an **ActBoxOR** volume covering the entire playable area. Set:
   - **MailBox** → `EMAILBOX_CAMSHOT` (mailbox index 101)
   - **Object** → the CamShot actor

The Camera starts in `DelayCameraHandler` until the player spawns inside the ActBoxOR, at which point it transitions to `NormalCameraHandler`.

### Multiple shots with pan transitions

Place additional CamShot actors and corresponding ActBoxOR zones (smaller, non-overlapping volumes). When the player walks from zone A to zone B:

1. ActBoxOR for zone B writes the new CamShot index to `EMAILBOX_CAMSHOT`
2. `NormalCameraHandler::_update()` sees the index has changed → switches to `PanCameraHandler`
3. `PanCameraHandler` lerps over `destShot.PanTimeInSeconds` then returns to `NormalCameraHandler`

**Pan time is on the destination shot.** Set it to `0` for an instant cut; `1–3` seconds for a smooth cinematic pan.

### Bungee-Cam

Enable the `gBungeeCam` global (currently a compile-time/runtime flag; no in-level switch). The camera follows the track object with elastic lag controlled by **Climb Rate** and **Elasticity** on the CamShot.

### Getting a narrow-FOV / pseudo-isometric look

Until the FOV fix lands, all cameras render at the global 60°. Once the fix is in:
- Place the CamShot far above and behind the subject
- Set **FOV** to 15–25°
- Set **Position X/Y/Z** = `Relative` so the camera moves with the player
- Result is visually indistinguishable from orthographic at typical game scale

---

## Director script examples (Forth)

The `\ wf` sigil marks a Forth script. The Director's script runs every tick. Local mailboxes (2000–3037) are per-actor scratch storage — use them for state that must persist between ticks.

`INDEXOF_CAMSHOT` = 1021. Write a CamShot actor's object index to it to trigger a camera switch. `NormalCameraHandler` reads and clears it each tick.

### Immediate one-shot cut on level start

```forth
\ wf
: CAMSHOT_INTRO 3 ;   \ object index of the intro CamShot actor in this level
CAMSHOT_INTRO INDEXOF_CAMSHOT write-mailbox
```

Writes once on the first tick (and every tick — harmless after the first since the handler clears it). For a true one-shot, gate on a flag mailbox:

```forth
\ wf
: CAMSHOT_INTRO  3 ;
: MB_FIRED      2000 ;        \ local mailbox — 0 = not yet fired

MB_FIRED read-mailbox 0 = if
    CAMSHOT_INTRO INDEXOF_CAMSHOT write-mailbox
    1 MB_FIRED write-mailbox
fi
```

---

### Timed sequence — cut to a new shot after N ticks

```forth
\ wf
: CAMSHOT_A      3 ;          \ object indices of two CamShot actors
: CAMSHOT_B      7 ;
: MB_TICKS      2000 ;        \ tick counter
: CUT_AT         180 ;        \ switch after 3 s at 60 Hz

MB_TICKS read-mailbox 1 + MB_TICKS write-mailbox   \ increment counter

MB_TICKS read-mailbox CUT_AT = if
    CAMSHOT_B INDEXOF_CAMSHOT write-mailbox
fi
```

---

### Looping sequence — bounce between two shots every 5 seconds

```forth
\ wf
: CAMSHOT_A      3 ;
: CAMSHOT_B      7 ;
: MB_TICKS      2000 ;
: MB_PHASE      2001 ;        \ 0 = on A, 1 = on B
: PERIOD         300 ;        \ 5 s at 60 Hz

MB_TICKS read-mailbox 1 + MB_TICKS write-mailbox

MB_TICKS read-mailbox PERIOD = if
    0 MB_TICKS write-mailbox                        \ reset counter
    MB_PHASE read-mailbox 0 = if
        CAMSHOT_B INDEXOF_CAMSHOT write-mailbox
        1 MB_PHASE write-mailbox
    else
        CAMSHOT_A INDEXOF_CAMSHOT write-mailbox
        0 MB_PHASE write-mailbox
    fi
fi
```

---

### Real level: snowgoons — ActBoxOR mailbox multiplexer

From `wflevels/snowgoons-blender/snowgoons.lev`. The level has three camera zones; each `ActBoxOR` writes its CamShot index to a dedicated per-zone mailbox (100, 99, 98) rather than directly to `INDEXOF_CAMSHOT`. The Director fans them together:

```forth
\ wf
100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then
 99 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then
 98 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then
```

**Stack trace for each line** (`read-mailbox ( idx -- val )`):

```
100 read-mailbox    ( -- val )
dup                 ( -- val val )
0 <>                ( -- val flag )
if                  ( -- val )        \ flag consumed; val remains
  INDEXOF_CAMSHOT   ( -- val 1021 )
  write-mailbox     ( -- )            \ ( val idx -- ) — camera switches
else
  drop              ( -- )            \ discard val if zero
then
```

**Why three mailboxes instead of all writing to `INDEXOF_CAMSHOT` directly?** `ActBoxOR` writes its value once, but `NormalCameraHandler` clears `INDEXOF_CAMSHOT` to zero after reading it each tick. If two zones both wrote to `INDEXOF_CAMSHOT`, one would stomp the other. With per-zone mailboxes, the Director re-asserts the active shot every tick as long as the player stays inside a zone — the value persists in the zone mailbox until `ActBoxOR` overwrites it on the next collision tick.

Note that `then` is used here, not `fi`. Both are valid in this zForth build: `fi` is the zForth native word; `then` is a standard Forth alias defined in `scripting_zforth.cc`.

---

### Notes

- **Object indices** — the CamShot's index in the level object list. Check `lvldump` output or the Blender level importer's object panel. Indices start at 1.
- **Tick rate** — engine runs at 60 Hz; 60 ticks = 1 second.
- **`fi` and `then` are both valid** — `fi` is the zForth native word; `then` is a standard Forth alias. The snowgoons level uses `then`; the examples above use `fi`. Either works.
- **`write-mailbox` stack order** — `( val idx -- )`: value first, index second.
- **Pan time** — the transition duration comes from the destination CamShot's `Pan Time In Seconds` field, not from the script. Set it in the level editor.

---

## Related

- [Camera projection audit](2026-04-29-camera-system-audit.md) — projection-only focus; confirms perspective-only and FOV gap
- `wfsource/source/game/movecam.cc` — all CameraHandler implementations
- `wfsource/source/oas/camshot.oas` — full CamShot field definitions
- `wfsource/source/gfx/glpipeline/backend_modern.cc` — `Mat4Perspective`, `SetProjection`
