# WF Level Building & Engine Knowledge

This doc is organised level-designer-first: start here, set up tooling,
follow authoring conventions, wire the engine systems your level needs,
crib from a worked example, and (for engine maintainers only) read the
internals at the bottom. For per-symptom debugging recipes, see
[docs/level-design-troubleshooting.md](level-design-troubleshooting.md).

## Contents

1. [Start here — references for level designers](#start-here--references-for-level-designers)
2. [Tooling](#tooling)
   - [Blender MCP Connector](#blender-mcp-connector)
   - [Headless Blender export fallback](#headless-blender-export-fallback)
   - [Build & Run](#build--run)
3. [Authoring conventions](#authoring-conventions)
   - [Blender Viewport Display by Object Type](#blender-viewport-display-by-object-type)
4. [Engine systems you wire from a level](#engine-systems-you-wire-from-a-level)
   - [Scripting System](#scripting-system) — per-frame player script, camera-relative input (SW iso), Director / ActBoxOR pattern, level selection without scripts
   - [Camera System](#camera-system) — state machine, EMAILBOX_CAMSHOT bootstrap
5. [Worked example — Marble Madness arcade-ROM pipeline](#worked-example--marble-madness-arcade-rom-pipeline)
   - [Tools](#tools)
   - [Step 1 — Extract ROM data](#step-1--extract-rom-data)
   - [Step 2 — Build path mesh in Blender (via MCP)](#step-2--build-path-mesh-in-blender-via-mcp)
   - [Step 3 — Build pipeline (unchanged)](#step-3--build-pipeline-unchanged)
   - [ROM Segment Format](#rom-segment-format)
   - [Coordinate Mapping](#coordinate-mapping)
   - [Calibration Constants (`rom_to_blender.py`)](#calibration-constants-rom_to_blenderpy)
   - [Actor Spawn Placement](#actor-spawn-placement)
   - [Camera Setup for Marble Madness (SW Isometric)](#camera-setup-for-marble-madness-sw-isometric)
   - [Marble Physics: Friction and Deceleration](#marble-physics-friction-and-deceleration)
   - [Goal Platform: Back Wall](#goal-platform-back-wall)
   - [Marble Actor: Use `sphere.iff`, Not `player.iff`](#marble-actor-use-sphereiff-not-playeriff)
6. [Engine internals](#engine-internals)
   - [Level File Format](#level-file-format) — cd.iff TOC, DO_CD_IFF, level object count
   - [LP64 Port Issues](#lp64-port-issues)
   - [Level Constructor Ordering Bug (fixed)](#level-constructor-ordering-bug-fixed)

---

## Start here — references for level designers

Three documents to keep open while building any level. They cover
"what actors are available," "what a finished port looks like," and
"how to verify behaviour at runtime without rebuilding."

- **[docs/2026-05-03-oas-actor-types.md](2026-05-03-oas-actor-types.md)** — Index of every shipped
  OAS actor type, its OAD fields, and what game patterns it enables.
  Read this *first* before planning any level — the engine's
  ecosystem is wider than the headline classes (`player`, `room`,
  `camera`, etc.) suggest. Notable types people miss on a first pass:
  - `Generator` + `Template` — spawn-by-mailbox primitive.
  - `Warp` / `Destroyer` — paired spawn/despawn for projectiles + pickups.
  - `Meter` — on-screen mailbox-driven HUD gauge (score, timer, lives,
    counters). Wires straight to a director-side mailbox; no bitmap-
    font subsystem needed for basic readouts.
  - `Activation Box` / `Activation Box Object Reference` — collision
    triggers that write to mailboxes; the `Object Reference` variant
    is how the camera switches between `CamShot`s in `mm_practice`.
  - `Enemy` — generic NPC base with path-follow support.
- **Worked-example port plans** — read these to see how shipped
  primitives actually wire together end-to-end:
  - **[docs/plans/2026-05-03-qbert-mvp.md](plans/2026-05-03-qbert-mvp.md)** — content-only port (no
    engine changes): 28-cube pyramid + hop state machine + colour-flip
    win condition + fall-and-respawn, built entirely from shipped OAS
    types + Forth scripts in actor Script fields + mailboxes. The
    verification block in that doc shows the canonical bridge-dump
    format for proving a level's scripts behave as intended.
  - **`wflevels/mm_practice/`** — the original generic test level (a
    marble on a ramp); see `~/.claude/projects/-home-will-wf-games/memory/project_mm_practice_status.md`
    for status and gotchas.
  - **§5 of this doc** — Marble Madness arcade-ROM pipeline (full ROM
    → JSON → Blender mesh → WF level reproduction).
- **`~/.claude/projects/-home-will-wf-games/memory/reference_wf_debug_bridge.md`**
  — TCP/JSON debug bridge on port 7777. Watch any mailbox at runtime,
  pause / step the simulation, edit OAD properties live. Launch with
  `task run-debug -- wflevels/<level>.iff` (binds 127.0.0.1) or
  `task run-debug-remote ...` (binds 0.0.0.0). Pending bridge ops
  (mailbox-write, input-inject, shader hot-reload, script hot-swap,
  DAP breakpoints) are tracked in
  [docs/plans/2026-05-03-debug-bridge-gap-features.md](plans/2026-05-03-debug-bridge-gap-features.md).

For gotchas hit during real level work — coordinate systems, BungeeCam
target placement, Mesh face-normal rules, `Mobility`+`MovementClass`
requirements, zForth bitwise-op pitfalls, the `Model Type=Box` random-
debug-cube behaviour, the wf_blender exporter's dual-`Mesh Name`
field, etc. — see [docs/level-design-troubleshooting.md](level-design-troubleshooting.md).

---

## Tooling

### Blender MCP Connector

The official Blender MCP server (released 2026-04-28, Blender + Anthropic) lets Claude
directly manipulate a live Blender session — execute Python, introspect the scene, and
capture viewport screenshots — instead of round-tripping through `blender --background`
scripts.

#### One-time setup

**1. Install `uv` (once per machine)**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Install the Blender addon (scripted, no GUI needed)**

```bash
bash wftools/wf_blender/install_blender_mcp.sh
```

This downloads the addon from [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)
(Blender 3.0+, works with 4.0.2), installs it headlessly, and verifies it's enabled.
The official Blender Lab addon requires Blender 5.1+ and isn't usable yet.

**3. Connect Blender each session**

Open Blender, press **N** in the 3D Viewport → **BlenderMCP** tab → **Connect to Claude**.  
Keep this panel open while working; the socket server runs only while connected.

**4. Project MCP config** (already committed at `.mcp.json` in repo root)

```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["blender-mcp"]
    }
  }
}
```

Claude Code picks this up automatically on session start. Restart the session after
the first-time setup.

#### What this replaces

| Before | After |
|--------|-------|
| Edit `blender_update_player_sphere.py`, run `blender --background --python …` | Ask Claude to modify the scene directly in the open Blender window |
| Blind iteration — no visual feedback until game runs | Viewport screenshot available immediately after each change |
| Script must handle import, export, and reload | Claude issues targeted Python API calls; you trigger export when ready |

#### Notes

- Only one MCP client may connect at a time (don't run Claude Desktop and Claude Code
  simultaneously against the same Blender session).
- The server process (`uvx blender-mcp`) is managed by Claude Code; don't launch it
  manually in a terminal.
- The Blender addon listens on `localhost:9876` by default.

### Headless Blender export fallback

`bpy.ops.wf.export_level` is only registered when MCP is connected (the `debug_bridge`
module injected by the MCP server is needed by `wf_blender/__init__.py`). For headless
`blender --background --python` runs (i.e. any `blender_create_*.py` driver script that
needs to run from the command line), use the direct module loader:

```python
try:
    bpy.ops.wf.export_level(filepath=OUT_LEV)
except AttributeError:
    import importlib.util as _ilu
    _addon = os.path.expanduser('~/.config/blender/4.0/scripts/addons/wf_blender')
    _spec = _ilu.spec_from_file_location(
        'wf_blender.export_level', os.path.join(_addon, 'export_level.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ok, msg = _mod.export_scene_to_lev(bpy.context, OUT_LEV)
    if not ok:
        raise RuntimeError(f'export_scene_to_lev failed: {msg}')
```

This bypasses `__init__.py` entirely and calls `export_scene_to_lev` directly. Used by
both `blender_create_mm_practice.py` and `blender_create_qbert.py`.

### Build & Run

```bash
cd engine
bash build_game.sh

# Run:
cd wfsource/source/game
LD_LIBRARY_PATH=../../../engine/libs DISPLAY=:0 ../../../engine/wf_game
```

`build_game.sh` compiles all source dirs, skips test/Windows files, uses the scripting stub
and platform stubs from `wftools/engine/stubs/`.

For per-level builds (Q✱bert / mm_practice / etc.) use the four-stage Rust pipeline:

```bash
bash wftools/wf_blender/build_level_binary.sh <level-name>
```

For runtime use Taskfile entries: `task run-level -- wflevels/<level>.iff` (no bridge),
`task run-debug -- wflevels/<level>.iff` (debug bridge on `:7777`).

---

## Authoring conventions

### Blender Viewport Display by Object Type

**The rule: anything that does not render in the game engine should display as
Wire in Blender.** This keeps editor visibility unobstructed — infrastructure
boxes (cameras, CamShots, ActBoxORs, room bbox visualisations, etc.) otherwise
occlude the actual level geometry and make it impossible to see what the player
will see at runtime.

The two `wf_Model Type` values that *do* render in-engine are:

- **`Mesh`** — the actor renders the geometry from its `Mesh Name` (.iff) reference.
- **`Matte`** — the actor renders its `Matte Type` background (colour or tiled image).

`None`, `Scarecrow`, `Emitter`, and unset are internal scaffolding the engine
uses for physics / triggers / messaging but draws nothing.

> ⚠️ **`Model Type='Box'` is NOT non-rendering.** The engine's
> `RenderActor3DBox` (instantiated by `actor.cc:398` for any Box-model actor)
> renders as a small **random-coloured** cube via `MakeRandMaterialList`.
> If a Box actor falls inside the camera frustum, it will obscure real
> geometry with a magenta / lime / olive cube whose colour changes between
> runs. Always set infrastructure actors to `Model Type='None'`. See
> `level-design-troubleshooting.md` § "Infrastructure actors render as
> random-coloured debug cubes" for the full diagnosis.

> ⚠️ **Actors authored outside every room's bbox silently don't render.**
> The room bbox isn't just a runtime culling volume — it controls
> render-set membership at level-export time. levcomp-rs
> ([`wftools/levcomp-rs/src/rooms.rs:168-178`](../wftools/levcomp-rs/src/rooms.rs))
> assigns each non-room actor to the first room whose bbox contains the
> actor's world-space *center*. Actors whose center falls outside every
> room's bbox get no `room.entries` push, so the `.lev` lists them in the
> level's object table but not in any room. At engine load,
> `Room::AddObject` / `ROOM_OBJECT_LIST_RENDER` walks only the room's
> listed entries, so `BindAssets` (which calls `new
> RenderActor3DAnimates(...)`) is never called for orphaned actors. They
> stay invisible no matter what their `wf_Model Type`, `Visibility
> Mailbox`, `Mass`, `Mobility`, or schema says.
>
> Diagnose with `grep -c RenderActor3DAnimates wf_game.log` against your
> expected animated-mesh count. One short → an actor's authored center is
> outside every room's bbox. Compare against `object count = N` in the
> same log — that's the total actor count, so the diff "object count
> non-NULL minus rendered" tells you how many actors fell off the map.
>
> **Fix:** either move the actor's authored center inside an existing
> room's bbox, *or* expand the room. For single-room levels (like the
> qbert_practice pyramid) the cleanest fix is a global-ish room bbox
> (e.g. `±200` in every axis around the room centre) so that any
> authored position — including off-camera "parking" locations the
> scripts want to teleport actors to — lands inside the room.
> Worked example: see
> [docs/plans/2026-05-11-qbert-player-death-and-curse-bubble.md](plans/2026-05-11-qbert-player-death-and-curse-bubble.md)
> § "2026-05-12 implementation notes" — the curse bubble at authored
> `Z=-100` was outside the room and didn't render until the room bbox
> was expanded.

Wire-displayed objects in Blender should be everything that doesn't render
in-engine (`Mesh` / `Matte` excluded). The `display_type='WIRE'` automation
below applies to all non-rendering classes.

To apply in one shot (run via MCP or in the Blender scripting console):

```python
import bpy
RENDERED = ('Mesh', 'Matte')
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue  # EMPTY / LIGHT / CAMERA already non-occluding
    mt = obj.get('wf_Model Type', None)
    if mt not in RENDERED:
        obj.display_type = 'WIRE'
```

#### Standard infrastructure object table

| Class | Typical `wf_Model Type` | Renders in-engine? | Wireframe in Blender? |
|-------|-------------------------|--------------------|-----------------------|
| `statplat`, `player`, `enemy`, `missile` (with mesh) | `Mesh` | yes | ✗ |
| `matte` | `None` (background painted via `Matte Type`/`Background Color`) | yes (backdrop) | ✗ |
| `room` | *(no OAD on the bbox visualisation mesh)* | no | ✓ |
| `actboxor`, `actbox` | `None` | no | ✓ |
| `camshot` | `None` (override default `Box`) | no | ✓ |
| `camera` | `None` (override default `Box`) | no | ✓ |
| `levelobj` | `None` (override default `Box`) | no | ✓ |
| `target` | `None` (override default `Box`) | no | ✓ |
| `director` | `None` | no | ✓ (often EMPTY anyway) |
| `light` | `None` | no | ✓ (often EMPTY anyway) |
| `generator`, `destroyer`, `warp`, `init`, `dir`, `file` | `None` | no | ✓ |

For each `wf_Model Type='None'` row above where the OAS schema's default
`Model Type` is `Box`, the `blender_create_*.py` script *must* set
`obj['wf_Model Type'] = 'None'` explicitly — otherwise the actor renders as
a random debug cube and obscures real geometry. The matte row also flips
from `Matte` to `None`: matte's backdrop drawing is independent of its
Model Type field, and `Model Type='Matte'` plus the `MODEL_TYPE_BOX`-default
behaviour combine to surprising results in practice. Use `'None'` and rely
on `Matte Type='Color'` + `Background Color` for the backdrop.

Authoring scripts (`blender_create_*.py`) should apply the snippet above as a
last step before saving the .blend, so the `wf_Model Type` settings stay in
sync with viewport display.

---

## Engine systems you wire from a level

These are the runtime systems your level interacts with through OAD
fields, mailboxes, and Forth scripts. The patterns below are what the
existing levels (`mm_practice`, `qbert_practice`, `snowgoons`, the MM
reproduction) actually use.

### Scripting System

#### Per-frame player script (basic pattern)

Forwards raw joystick to the input mailbox:

```forth
\\ wf
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
```

For an isometric camera where screen-up ≠ world-N, use a bit-rotation word instead (see
"Camera-relative input" below). For complex per-tick behaviour (state machines,
hop arcs, AI), see `qbert_practice/blender_create_qbert.py` for the canonical multi-tick
state-machine pattern in Forth.

#### Camera-relative input (SW iso pattern)

The WF `MarbleHandler` applies button bits as world-axis impulses:
`EJ_BUTTONF_UP` → world +Y (North), `EJ_BUTTONF_RIGHT` → world +X (East),
etc. Arrow keys map to these bits via `INDEXOF_HARDWARE_JOYSTICK1_RAW`.

For an SW isometric camera (offset −6,−8,+10 looking NE), screen-up =
world NE and screen-right = world SE. The player expects pressing Up to move
the ball "up the screen" (NE), not world-North. The fix is to rotate the
four direction bits 45° CW in a Forth word before writing to `INDEXOF_INPUT`:

```forth
\ zForth — use & and | for bitwise ops, NOT "and"/"or"
: cam-remap  0
  over 0x0800 & if 0x2800 | then    \ UP    → UP|RIGHT  (0x0800|0x2000) = NE
  over 0x1000 & if 0x5000 | then    \ DOWN  → DOWN|LEFT (0x1000|0x4000) = SW
  over 0x2000 & if 0x3000 | then    \ RIGHT → DOWN|RIGHT(0x1000|0x2000) = SE
  over 0x4000 & if 0x4800 | then    \ LEFT  → UP|LEFT  (0x0800|0x4000) = NW
  swap drop ;

INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox cam-remap INDEXOF_INPUT write-mailbox
```

Diagonal combos cancel correctly: pressing Up+Right produces
NE+SE = (UP|RIGHT)|(DOWN|RIGHT) — the NE and SE verticals cancel leaving pure
East. No special diagonal handling is needed.

**Bit values** (from `wfsource/source/hal/sjoystic.h`):

| Bit symbol | Value |
|---|---|
| `EJ_BUTTONF_UP` | `0x0800` |
| `EJ_BUTTONF_DOWN` | `0x1000` |
| `EJ_BUTTONF_RIGHT` | `0x2000` |
| `EJ_BUTTONF_LEFT` | `0x4000` |

**zForth operator note:** zForth does NOT have `and` or `or` as named words.
Use the primitive symbols `&` (bitwise AND) and `|` (bitwise OR).
Using `and`/`or` compiles silently into a ZF_ABORT_NOT_A_WORD error (code 7)
that prints `zforth compile error 7 (defs): : cam-remap ...` at runtime —
the word is simply not executed every tick, leaving `INDEXOF_INPUT` at 0.

#### Mailbox scope rules

WF mailboxes form a hierarchy. Understanding scope prevents the most common cross-actor scripting bugs.

| Range | Name | Scope | Notes |
|---|---|---|---|
| 0–1 | `EMAILBOX_FALSE` / `EMAILBOX_TRUE` | Global, read-only | Set by engine at level load; write attempts are silently dropped (assert in debug builds). Use mb[1] as a "always-true" visibility mailbox. |
| 2–999 | Global user | **Shared across all actors** | Director, player, cube actors, etc. all read/write the same cells. Q✱bert's cube-state mailboxes (200–227), round counter (425), etc. live here. |
| 1000–1021 | Global system | Global, side-effects | `INDEXOF_CAMSHOT` = 1021 writes the active camera. |
| 2000–2099 | Local user | Per-actor | Each actor has its own storage at this range. Rarely needed for game logic. |
| 3000–3036 | Local system | Per-actor, side-effects | **`INDEXOF_X_POS` = 3009, `INDEXOF_Y_POS` = 3010, `INDEXOF_Z_POS` = 3011.** Writing here moves the *calling actor's* position. |
| 4000–4099 | Scratch | Per-script-call | Temporary storage within a single script execution. |

**Critical implication — you cannot teleport another actor from the director:**

```forth
\ WRONG: executed in the director's context — moves the director, not the player
0 INDEXOF_X_POS write-mailbox
```

`INDEXOF_X_POS` = 3009 is in the local-system range. A `write-mailbox` syscall routes through `LookupMailboxes(callerActorIndex)` → that actor's `WriteSystemMailbox` → moves *that* actor. From the director script, this moves the (invisible) director, not Q✱bert.

**Pattern for cross-actor teleport — use a signal mailbox:**

```forth
\ Director script: set a signal in the shared global range
1 426 write-mailbox   ( 426 = RESPAWN_REQUESTED )

\ Player script: handle the signal in player context
426 read-mailbox 1 = if
  0 INDEXOF_X_POS write-mailbox   ( these now move the player )
  6 INDEXOF_Y_POS write-mailbox
  15 INDEXOF_Z_POS write-mailbox
  0 426 write-mailbox             ( clear signal )
then
```

**Visibility mailbox (`wf_Visibility Mailbox`):**

Most gameplay actors (platform, statplat) default to `VisibilityMailbox = 1` (reads mb[1] = always 1 = always visible). Infrastructure actors (target, camshot, light, actboxor) default to `VisibilityMailbox = 0` (reads mb[0] = always 0 = always invisible). Cube variant actors use custom mailbox slots (300–383 in `qbert_practice`) so the director can switch which variant renders. Scripts cannot make a gameplay actor invisible: mb[1] is protected from writes.

#### Director / ActBoxOR pattern

- **Director script** (per frame): reads mailboxes 98/99/100 and writes to `$INDEXOF_CAMSHOT`.
  These mailboxes are set by ActBoxOR trigger zones.
- **ActBoxOR objects**: write a named object's index to a mailbox when the Player enters
  their trigger volume. In snowgoons, one ActBoxOR writes `CamShot01`'s index to mailbox 1021
  (`EMAILBOX_CAMSHOT`) when the Player enters.
- **NullInterpreter stub**: `wftools/engine/stubs/scripting_stub.cc` — replaces Tcl scripting
  with a no-op. All `RunScript()` calls return 0. This is intentional pending replacement
  with a non-Tcl scripting system.

#### Per-tick execution order (and why signal chains pick up a 1-tick lag)

There is **no priority/phase/dependency mechanism for actor scripts.** Execution order per tick is:

1. **Main update loop** ([`level.cc:876`](../wfsource/source/game/level.cc) — `UpdatePhysics(...)`) — iterates every active actor in **actor-index order** (= the order the `.lev` file lists them = the order the Blender exporter wrote them = the creation order in the `blender_create_*.py` script). For each actor: physics step, then `Actor::update()` runs the actor's MovementHandler, then `EvalScript()` runs its Forth script.
2. **`updateRoomContents()`** (room-membership housekeeping).
3. **Director runs last, alone** ([`level.cc:881-888`](../wfsource/source/game/level.cc)) — hardcoded special case prefixed by the comment *"FIX - manually update director until we get priorities working in updates"*. The Director update is not part of the main loop; it gets its own slot after everything else.

**What this means for cross-actor signal mailbox chains** — the pattern of `actor A writes global → actor B reads, computes, writes another global → actor C reads, applies on self`:

- A producer that runs in the main loop will see its writes consumed by the Director on the **same** tick (Director runs after the main loop completes).
- A consumer that runs in the main loop will see the Director's writes only on the **next** tick (the Director hasn't run yet when the consumer fires in the main loop).
- **Net result:** any signal chain that crosses through the Director and back into a main-loop actor accumulates exactly **one tick of lag** at the final consumer. At 60 Hz that's 16 ms — invisible for camera positioning, score updates, colour pulses; potentially relevant for input-driven physics if you're stacking multiple chains.

**The alternative pattern — Director writes another actor's local mailbox directly via [`write-actor-mailbox`](../engine/stubs/scripting_zforth.cc) (custom syscall 2, signature `( val idx actor_idx -- )`)** — *also has the 1-tick lag*, because the target actor's update (which is what reads the changed mailbox) runs in the main loop before the Director's after-loop slot. The signal-chain design isn't slower than the direct-poke design on this metric; it's just architecturally cleaner. The direct-poke primitive is on the chopping block — see `TODO.md` § `SCRIPTING INFRASTRUCTURE`.

**Controlling actor-index order within the main loop** — actors run in the order the Blender script creates them. To get producer-before-consumer ordering inside one tick, create the producer actor first in the `blender_create_*.py` script. If you're not sure, dump actor indices with `--debug-print-actors` (see [§ `--debug-print-actors`](#--debug-print-actors-debug-builds-only) above) and read off the load-order column. Note that this only gates intra-main-loop chains; it can't shorten chains that cross through the Director.

**There is no way to declare a dependency like "run my script after actor X's script."** The closest workaround is to add the dependent logic to the Director's script (so it runs after every main-loop actor). Past that, you accept the 1-tick lag or restructure the chain. A real priority/phase mechanism is the right long-term fix; tracked in `TODO.md` § `SCRIPTING INFRASTRUCTURE` as "Finish 'priorities working in updates'".

#### Level Selection Without Scripts

`_desiredLevelNum` in `WFGame` must be set before `assert(_desiredLevelNum >= 0)` fires.
Normally the shell script (cubemenu) writes `EMAILBOX_LEVEL_TO_RUN` to choose a level.
**Fix (game.cc):** initialize `_desiredLevelNum = 4` (snowgoons) in the constructor
initializer list, and move the `_overrideLevelNum` check to BEFORE the asserts.

### Camera System

#### Camera State Machine

- **DelayCameraHandler**: waits up to 5 frames for `EMAILBOX_CAMSHOT > 0` then transitions.
  Assertion at `movecam.cc:885` fires if nobody writes a valid CamShot index within 5 frames.
- **BungeeCameraHandler**: main follow camera. Each frame reads `EMAILBOX_CAMSHOT` (mailbox 1021)
  to get the active CamShot object's index. Originally cleared the mailbox after reading
  (relied on ActBoxOR to re-write each frame).
- **NormalCameraHandler**: validates that the stored shot index is a real CamShot object.

#### EMAILBOX_CAMSHOT Bootstrap (scripting disabled)

With scripting disabled, ActBoxOR trigger zones never fire. Fix in `level.cc::constructObject`:
when a `CamShot_KIND` object is constructed and the mailbox is still 0, write the CamShot's
actor index to `EMAILBOX_CAMSHOT`. This is a one-time bootstrap; the value persists.

`BungeeCameraHandler::predictPosition()` originally cleared the mailbox after use (line 988).
With scripting disabled this is suppressed — the mailbox stays set to the initial CamShot
so the camera keeps working without per-frame ActBoxOR writes.

#### Per-frame camera slew clamp (10 units/frame, hardcoded)

`NormalCameraHandler::_update()` ([`movecam.cc:495-511`](../wfsource/source/game/movecam.cc)) applies a slew clamp to the final camera position vector every tick the active CamShot index is unchanged from last frame:

```cpp
#define XSLEW SCALAR_CONSTANT(10)
#define YSLEW SCALAR_CONSTANT(10)
#define ZSLEW SCALAR_CONSTANT(10)
…
destCam.position = LimitRelativeMovementMagnitude(
    destCam.position, cd.oldCameraPosition, Vector3(XSLEW, YSLEW, ZSLEW));
```

`LimitRelativeMovementMagnitude` is per-axis: each axis can move at most 10 units between consecutive frames. The clamp is applied **after** the per-axis Absolute/Relative mux (lines 235-248 in `SetCameraParametersFromShot`), so it constrains all three axes regardless of which mode each is in — an Absolute axis is just as clamped as a Relative one.

The original author left a comment beside the constants: *"I don't understand why they are necessary, since we specify the pan time in seconds in the OAD. So, I'm defining them as constants here just to get this code working. — Phil"*. Take this as licence to tune the numbers when a level design needs to.

**When it doesn't bite:**

- **Player-driven follow cameras.** Mario's `Max Ground Speed` is 6 (`wflevels/smb_w1_1/blender_create_smb.py:274`); any speed under 10 leaves the slew dormant for normal tracking. SMB-style scroll, MM iso, and standard 3rd-person follow all stay well under budget.
- **First-frame handler activation.** Line 510 guards the clamp with `if(cd.idxOldCamShotActor)`, so the very first frame after `DelayCameraHandler` hands off (or after a CamShot switch) is exempt. A script can seed a fresh camera position with any delta on its first tick.
- **`gBungeeCam` global true.** Line 499 short-circuits the entire else-branch when set, skipping the slew. This is the existing knob for "I want the camera to teleport".

**When it does bite:**

- **Per-frame mailbox-driven camera moves** (e.g. a Director Forth script writing to a CamShot's `INDEXOF_X_POS` via `write-actor-mailbox` to drive scroll behaviour from script). The CamShot's authored position changes per tick, and the slew clamps the resulting camera delta. Fine if per-frame delta < 10; otherwise the camera lags visibly behind the script's intended position.
- **Cutscene-style jumps mid-level.** A Director that wants to snap the camera 50 units to set up a cutscene will see ~5 frames of slew-limited drift unless it flips `gBungeeCam` true or relies on a CamShot switch (which also resets the slew via the `idxOldCamShotActor != idxShot` else-branch that transitions to `PanCameraHandler`).

**Raising or removing the limit if a game design requires it:**

The slew limit is a 1996-vintage workaround, not a load-bearing invariant. Three routes to change it:

| Route | Mechanism | Trade-off |
|-------|-----------|-----------|
| **Edit C++ constants** | Bump `XSLEW`/`YSLEW`/`ZSLEW` at [`movecam.cc:495-497`](../wfsource/source/game/movecam.cc) | One-line engine edit. Affects every level. Easy, blunt instrument. |
| **Per-CamShot OAS field** | Add `Slew X/Y/Z` (or a single `Slew Max`) to [`camshot.oas`](../wfsource/source/oas/camshot.oas) and read them in `_update()` | Per-CamShot tunability. Currently gated by the "no new OAS fields pre-merge" rule until the first level ships ([`feedback_no_new_oas_fields_premerge`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_no_new_oas_fields_premerge.md)). |
| **Toggle `gBungeeCam`** | Set the existing `extern bool gBungeeCam` true (line 49); the slew else-branch is skipped entirely | No engine code change. Crude — bypasses slew globally, not per-axis. Use as runtime escape hatch. |

If a level design hits this clamp, prefer the C++-constant bump for one-off relief and reserve the OAS field for when per-CamShot tuning becomes a recurring need across multiple games.

For deeper camera investigation (per-axis Absolute/Relative, runtime switching via
`INDEXOF_CAMSHOT`, target tracking) see [docs/investigations/2026-04-29-camera-system.md](investigations/2026-04-29-camera-system.md).

### Physics-mobility actor authoring rules

Actors with `wf_Mobility = 'Physics'` are driven by [Jolt's `CharacterVirtual`](https://jrouwe.github.io/JoltPhysics/class_character_virtual.html) (set up in [`jolt_backend.cc:JoltCharacterCreate`](../wfsource/source/physics/jolt/jolt_backend.cc)). The first level to exercise this code path was SMB W1-1 (Mario, 2026-05-17); the diagnosis that produced these rules is in [`docs/investigations/2026-05-17-colspace-authoring.md`](investigations/2026-05-17-colspace-authoring.md).

**Three rules, all level-side:**

1. **Mesh-local feet at z=0.** WF's convention is `actor.pos = feet position`. The Jolt character settles with `actor.pos.z = ground_top_z`, so anything with mesh-local z < 0 ends up *inside* the ground. In a Blender script, after joining multi-primitive bodies, call `bpy.ops.object.transform_apply(location=True, ...)` so the joined mesh origin sits at the lowest vertex (the feet), then assign `player.data = body.data`. Otherwise the body inherits the active object's pre-join location and the mesh-local feet drift below z=0.

2. **Collision shape = visual-mesh AABB (auto-derived).** The Blender exporter writes a `Global Bounding Box` (BOX3) per actor from the visual mesh AABB, and the engine turns it into a Z-up [`CapsuleShape`](../wfsource/source/physics/jolt/jolt_backend.cc) (radius = `min(halfX, halfY)`, halfHeight = `halfZ − radius`). For Mario-shaped actors (taller than wide) you get a capsule that fills the silhouette; for short, wide actors (halfZ ≤ radiusXY) the engine falls back to a single-radius sphere. There is no separate `wf_ColSpace` override field yet — see [`docs/investigations/2026-05-17-colspace-authoring.md`](investigations/2026-05-17-colspace-authoring.md) for when one might be worth adding.

3. **One Physics actor per level minimum** (today). Mario in `smb_w1_1` is the only Physics actor in any committed level — `qbert_practice`, `mm_practice`, `snowgoons-blender` all use `Anchored` (the script handles all movement). Every aspect of the Physics path is currently exercised by exactly one actor.

**What to verify after authoring a Physics actor:**

| Test | What to watch on the bridge |
|---|---|
| Resting on flat ground | `idx=N` Z should equal ground top z, not negative |
| Walking off a ledge | Z drops, then settles on the next platform |
| Walking *up* onto a 1-tile box (e.g. SMB `qblock`) | Step-up should work or feel like jumping into a wall — both are valid game-design choices, just be intentional |
| Jumping | Z arcs up then back down to the resting Z |
| Head-bonking a low ceiling | Capsule top hits, Z dips, no fall-through |
| Wall blocking (pipes / actboxor) | X stops at the wall, Z stays constant |

**Mobility values and their physics semantics:**

| Value | What drives position | Use for |
|---|---|---|
| `Anchored` | Forth script writes `INDEXOF_X/Y/Z_POS` mailboxes | Most arcade ports (no real physics — Q*bert, MM, snowgoons) |
| `Physics` | Jolt `CharacterVirtual` with gravity from `wf_Falling Acceleration` | Mario-style platformers, anything needing real ground collision + jump arcs |
| `Path` | An OAD path animates the actor | Moving platforms, scripted enemy paths |
| `Camera` | Camera handler in `movecam.cc` | Camera actors only |
| `Follow` | Follows another actor | Trailing camera, second-player |

---

### Debug bridge

Run with `--debug-port 7777` (or use `task run-debug -- wflevels/<level>.iff`) to
expose a TCP/JSON port. The bridge broadcasts per-frame state and accepts
commands (`ping`, `pause`, `step`, `resume`, `pick`, `screenshot`, `set_mailbox`,
`reload_script`).

#### Identifier spaces — three different "id" fields

When debugging a physics issue you will see **three distinct identifier spaces**
in the logs, with similar-looking small integers. They are not interchangeable
and confusing them sends you down the wrong rabbit hole.

| Identifier | Where it appears | What it indexes | Example |
|---|---|---|---|
| **WF actor `idx`** | Bridge `{"op":"state","idx":N,"pos":[…]}` and `{"op":"perf","actors":N}` | The current level's actor table (load order) | `idx=9` = "the 9th actor in this level" |
| **Jolt body `id`** | `jolt_backend.cc` stderr: `jolt: body STATIC pos=… id=N`, `jolt: body MESH_STATIC … id=N` | `JPH::BodyID` — Jolt's internal rigid-body handle (large numbers with high bits set) | `id=8388608` = "Jolt body #0 in the STATIC pool" |
| **Jolt character `handle`** | `jolt: character N created at (…) ctr=(…)` | Index into `gCharacters` in [`jolt_backend.cc:443`](../wfsource/source/physics/jolt/jolt_backend.cc) — separate namespace from body ids | `handle=0` = "the first `Mobility=Physics` actor" |

**A bridge `idx` is not a Jolt id.** Static colliders have ids; characters have
handles; bridge events use WF actor indices. There's no direct cross-reference
printed — correlate by position.

**Practical example.** Investigating the SMB W1-1 invisible-player on
2026-05-17, the bridge reported `idx=9 pos=(4.5, 0, -0.67)` (player below
ground). The Jolt log showed `character 0 created at (4.50, 0.00, 1.50)`
(handle=0) and `body STATIC … id=8388608` (ground). Three different
identifiers for two real things (player + ground). Diagnosis only worked
because we kept the spaces separated.

#### `--debug-print-actors` (debug builds only)

Add `--debug-print-actors` to the engine command line (already wired into
`task run-debug`) and the engine prints one stderr line per actor at
construction time. The flag and its supporting code are guarded by
`#if DO_TEST_CODE` and so don't exist in `safe-fast`, `release`, `final`,
or `profile` builds — zero cost in production. See
[`docs/compile-time-switches.md`](compile-time-switches.md) for the build-mode
table.

```
actor idx=9  mesh=player.iff  mobility=Physics  pos=(4.50,0.00,1.50)
actor idx=19 mesh=(none)      mobility=Anchored pos=(4.50,0.00,1.50)   ← Target02 (camera lookat)
actor idx=15 mesh=ground.iff  mobility=Anchored pos=(33.75,0.00,-0.75)
…
```

This is the canonical way to map bridge `{"op":"state","idx":N}` events
back to specific WF actors. Off by default — opt-in to keep production
logs clean.

---

## Worked example — Marble Madness arcade-ROM pipeline

Marble Madness level paths are not hand-authored — they are faithfully reproduced from the
arcade ROM. The pipeline goes: **ROM → JSON → Blender mesh → WF level**. Treat this section
as a worked example of "reproducing arcade geometry from extracted data" — the Q✱bert MVP
is the worked example for "synthesising a pyramid from a Python loop", and `mm_practice` is
the worked example for "the simplest possible WF level."

### Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `decode_levels.py` | `wflevels/marble-madness/` | Extracts all 6 level segment records from the ROM ZIP into `levels.json` |
| `rom_to_blender.py` | `wflevels/marble-madness/` | Converts `levels.json` into a trough mesh in the live Blender scene |
| `blender_mm_fromscratch.py` | `wflevels/marble-madness/` | Full level build: clear scene, run converter, place all actors, export `.lev` |

### Step 1 — Extract ROM data

```bash
cd wflevels/marble-madness
python3 decode_levels.py ../../assets/arcade-roms/marble.zip
# → levels.json  (all 6 levels; h_left / h_right / h_center per segment)
```

`levels.json` is committed; only re-run if the ROM source changes.

### Step 2 — Build path mesh in Blender (via MCP)

With a Blender session open and MCP connected:

```python
import bpy, os
script = '/path/to/wflevels/marble-madness/blender_mm_fromscratch.py'
exec(open(script).read(), {'__file__': script, '__name__': 'blender_mm_fromscratch'})
# → mm_fromscratch.lev
```

Or run `rom_to_blender.py` alone to add just the path mesh to an existing scene:

```python
ns = {'__file__': '/path/to/rom_to_blender.py', '__name__': 'rom_to_blender', 'bpy': bpy}
exec(open('/path/to/rom_to_blender.py').read(), ns)
ns['build_path_mesh']('Practice', ns['load_levels']())
```

### Step 3 — Build pipeline (unchanged)

```bash
cd wflevels/marble-madness
bash build_level.sh
```

### ROM Segment Format

Level pointer table at `0x01DEC0` → per-level descriptor arrays (6-byte `[type:u16][addr:u32]`
entries, sentinel `0xFFFF`) → 24-byte segment records.

| Offset | Field | Notes |
|--------|-------|-------|
| `+02` | `h_left` | Wall/edge height — left side |
| `+04` | `h_right` | Wall/edge height — right side |
| `+0A` | `h_center` | Floor height at path centre |

Segments with `h_center == H_ZERO (5)` are goal zones — replaced by a flat platform.

Full reverse-engineering notes: [`docs/investigations/2026-05-01-marble-madness-rom-level-data.md`](investigations/2026-05-01-marble-madness-rom-level-data.md).

### Coordinate Mapping

The 16-bit `type` field encodes the **path heading** in its lower byte:

```
heading_angle = (type & 0xFF) / 256 × 2π  radians, CCW from +X axis (East = 0°)
```

Cross-section positions accumulate along the heading:

```
pos_{i+1} = pos_i + SEG_LEN × (cos θ_i, sin θ_i, 0)
```

Each cross-section has 3 vertices perpendicular to the heading (`right_perp = (sin θ, −cos θ, 0)`):

```
left   = (pos − PATH_HALF × right_perp,  Z(h_left))
center = (pos,                            Z(h_center))
right  = (pos + PATH_HALF × right_perp,  Z(h_right))
```

Height conversion: `Z(h) = (h − H_ZERO) × GAME_UNIT`

#### Trough vs. crowned sections

- `h_edge > h_center` → **walled trough**: edges rise above floor — ball is contained.
- `h_edge < h_center` → **crowned / open-sided**: edges drop below centre — ball rolls off without joystick steering (correct arcade geometry).

#### Practice level heading table

| Segments | `type` | Lower byte | Heading | Geometry |
|----------|--------|------------|---------|----------|
| 0–8 | `0x000D` | 13 | 18.28° (ENE) | Crowned S-curve — requires joystick |
| 9–10 | `0x0320` | 32 | 45.00° (NE) | Walled trough — rolls to goal unaided |
| 11–12 | `0x0D20` | 32 | — | Goal sentinel (`h_center=5`) → flat platform |

### Calibration Constants (`rom_to_blender.py`)

```python
H_ZERO    = 5      # goal h_center; subtracting puts goal at Z=0
GAME_UNIT = 0.05   # metres per game height unit  ← tune this
SEG_LEN   = 2.5    # metres per path segment       ← tune this
PATH_HALF = 2.0    # metres, centre → edge vertex  ← tune this
```

`GAME_UNIT=0.05` and `PATH_HALF=2.0` (calibrated 2026-05-02 against MAME screenshot):
trough walls at ΔH≈46–89 units over `PATH_HALF=2.0 m` give 30–48° slope angles, matching
the ~30–50° trough profiles in `assets/arcade-roms/reference/practice_start.png`.
`PATH_HALF=4.0` was visually too wide; `GAME_UNIT=0.1` produced 49–66° walls, too steep.

Compare viewport screenshots against `assets/arcade-roms/reference/practice_start.png` and
iterate GAME_UNIT / SEG_LEN until proportions match.

### Actor Spawn Placement

Spawn the Player above the **first walled (trough) segment** so the ball rolls toward the goal
without requiring joystick input during testing. For Practice this is seg 9:

```python
# heading-based position of seg-9 start: 9 segs × SEG_LEN × (cos 18.28°, sin 18.28°)
SPAWN_POS = (21.364, 7.058, 3.2)   # 0.6 m above seg-9 floor at Z=2.6
```

To play the full S-curve (segs 0–8), a joystick must be connected.

### Camera Setup for Marble Madness (SW Isometric)

The arcade original uses a fixed SW isometric view: camera is above-and-SW of the marble,
looking NE+down at roughly 45° elevation. All three BungeeCam axes must be `Relative` so
the camera offset stays fixed relative to the player position each frame.

**CamShot offset** (`CAMSHOT_POS`): `(-6, -8, 10)` from the marble works for Practice.
This gives ~45° elevation, camera is SW, and the sight line clears the west trough wall
(camera z=7.9 at wall crossing vs. wall top z≈5.1).

```python
SPAWN_POS    = (21.364, 7.058, 3.2)   # marble spawn
CAMSHOT_POS  = (-6.0, -8.0, 10.0)    # offset from marble
CAMERA_POS   = tuple(s + c for s, c in zip(SPAWN_POS, CAMSHOT_POS))
# → (-15.636+21.364, -0.942+7.058, 13.2) = approx (−15.6, −0.9, 13.2)
```

**CamShot `Target` field must be `'Player'`**, not a fixed Target02 empty. A fixed world
point causes the camera to look through the trough walls as the marble moves away from spawn.
With `Target='Player'` the camera always rotates to face the ball directly.

```python
props={
    'X Axis': 'Relative', 'Y Axis': 'Relative', 'Z Axis': 'Relative',
    'Target': 'Player',
    'Track Object': 'Target01',  # origin anchor at (0,0,0)
    'Follow': 'Target01',
    ...
}
```

**Sight-line geometry rule**: camera clears a wall of height `wall_z` when:
`cam_z - 0.5*(cam_z - marble_z) > wall_z`
i.e. the midpoint of the sight line is above the wall top.
With CAMSHOT_Z=10 and marble_z≈3.2: midpoint z = 10+3.2)/2 ≈ 6.6 > 5.1 ✓.

The camera-relative input bit-rotation Forth word for this SW iso view is in
[§4 — Camera-relative input (SW iso pattern)](#camera-relative-input-sw-iso-pattern) above.

### Marble Physics: Friction and Deceleration

The player OAD fields that most affect rolling feel:

| Field | Value | Rationale |
|-------|-------|-----------|
| `Running Deceleration` | `0.0` | Let physics (friction) handle braking; non-zero values easily exceed gravity on shallow slopes and freeze the ball |
| `Surface Friction` (player) | `0.3` | Low enough to roll down grades up to ~2° |
| `Surface Friction` (mesh) | `0.2` | Combined friction = player × mesh; keep low for smooth rolling |

`Running Deceleration` is applied as an artificial brake every frame when no joystick input
is present. On a 2.2° slope gravity = 0.38 m/s²; any `Running Deceleration` above ~0.35
will freeze the ball. Setting it to `0.0` leaves all braking to surface friction.

### Goal Platform: Back Wall

`rom_to_blender.py` adds a 2 m tall vertical quad face at the far end of the goal platform
(`PATH_HALF * 1.5` wide) to stop the marble rolling off. This is separate from the trough
walls and is always emitted when `goal_segs` is non-empty. If the marble still escapes,
increase `wall_h` in `build_path_mesh()`.

### Marble Actor: Use `sphere.iff`, Not `player.iff`

`player.iff` in the `marble-madness/` directory is a cube (8 verts, 576 bytes). The
marble must use `sphere.iff` (pre-built UV sphere, 21 KB):

```python
obj['wf_Mesh Name'] = 'sphere.iff'
```

`sphere.iff` is committed in `wflevels/marble-madness/` alongside `mm_fromscratch.ini`.

---

## Engine internals

These sections are for engine maintainers, not level designers. They cover the binary
file format, the LP64 port, and a load-bearing constructor-ordering bug fix. Skip
unless you're modifying the engine itself.

### Level File Format

#### LVAS — Level Assets (per-level container)

**LVAS = "Level Assets".** The IFF container chunk that bundles one level
together with the binary assets it needs — effectively a list of the IFF
(binary) files that make up a playable level: the level data (`LVL`) plus its
asset blobs (`PERM`, `RM0`, `RM1`, … the permanent + per-room texture/mesh
bundles), indexed by a table of contents (`TOC`) and an asset map (`ASMP`).

Layout (per [`levcomp-rs/decompile.rs`](../wftools/levcomp-rs/src/decompile.rs)):

```
L4   → [ ALGN, RAM, ALGN, LVAS ]
LVAS → [ TOC, ALGN, ASMP, ALGN, LVL, PERM, RM0, RM1, … ]
```

The authored `.lev` text source roots at **`LVL`** (the level data alone);
**`LVAS`** is the downstream binary wrapper produced when the level and its
assets are packaged for the engine. `cd.iff` (below) is in turn an archive of
many such per-level files.

#### cd.iff — Multi-Level Archive

`cd.iff` is an IFF-format table-of-contents archive containing all game levels.

**Structure:**
- LVLHDR `{lvasTag, fileSize}` at byte offset 0
- TOC IFF chunk: array of `TOCENTRYONDISK {tag, offset, size}` entries

**Level index in cd.iff (snowgoons project):**
| Index | Tag  | Name       |
|-------|------|------------|
| 0     | SHEL | cubemenu shell |
| 1     | L0   | cubemenu   |
| 2     | L1   | primitives |
| 3     | L2   | cyberthug  |
| 4     | L3   | geosphere  |
| 5     | L4   | snowgoons  |
| 6     | L5   | whitestar  |
| 7     | L6   | whitestar2 |

`GAMEFILE_LEVELSTART` offset is added to the level index when seeking via DiskTOC.

#### DO_CD_IFF

Defined at `game/game.cc:26`. When defined, loads levels from `cd.iff` via DiskTOC.
When undefined, loads `level%d.iff` from disk directly.

#### Level Object Count

Each `.iff` level embeds `_levelData->objectCount` (37 in snowgoons). Temporary objects
(tools, shadows, projectiles) occupy `objectCount .. objectCount + NumberOfTemporaryObjects - 1`.
`NumberOfTemporaryObjects` comes from the levelobj OAD; default is 200.

### LP64 Port Issues

The engine was written for 32-bit PSX/Win32 where `long` = 4 bytes. On Linux 64-bit, `long` = 8 bytes.

#### Known LP64 fixes

- **`gfx/rmuv.cc`**: `long* pRMUV` → `int32* pRMUV`; IFFTAG comparison cast to `(int32)`.
- **`gfx/ccyc.cc`**: same fix — `long* pCCYC` → `int32* pCCYC`.

#### How to spot LP64 issues

Assertions of the form `assert(*ptr == IFFTAG('x','y','z','w'))` that fail at startup
usually mean a `long*` is being used to read a 4-byte IFF tag/size pair — it reads 8 bytes
instead of 4, so the tag value is wrong. Fix: use `int32*` and cast IFFTAG to `(int32)`.

### Level Constructor Ordering Bug (fixed)

**Symptom:** Tools and shadows are constructed in `Actor::reset()`, added as temp objects,
but then `Level::reset()` immediately deletes all temp objects. The Actor still holds dangling
`_tool[]` pointers → vtable corruption → SIGSEGV in `Tool::trigger()`.

**Root cause:** In the Level constructor, the per-actor `reset()` loop ran BEFORE `Level::reset()`.

**Fix (`level.cc`):** Move the per-actor `reset()` loop to AFTER `Level::reset()`, so that tools
and shadows are created AFTER the temp-object slots are cleared and the active rooms are set up.

```cpp
// BEFORE (broken):
for each actor: actor->reset();   // creates temp objects (tools, shadows)
Level::reset();                    // deletes all temp objects → dangling pointers

// AFTER (fixed):
Level::reset();                    // clears temp slots, initializes active rooms
for each actor: actor->reset();   // creates temp objects AFTER rooms are ready
```

The `Actor::reset()` / `_InitTools()` pattern:
- `Actor::reset()` calls `_InitTools()` and `_InitShadow()`
- `_InitTools()` calls `ConstructTemplateObject()` for each tool slot, then `AddObject()`
- Tools are added as temp objects (index >= `_levelData->objectCount`)
