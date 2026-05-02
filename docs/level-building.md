# WF Level Building & Engine Knowledge

## Blender MCP Connector

The official Blender MCP server (released 2026-04-28, Blender + Anthropic) lets Claude
directly manipulate a live Blender session — execute Python, introspect the scene, and
capture viewport screenshots — instead of round-tripping through `blender --background`
scripts.

### One-time setup

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

### What this replaces

| Before | After |
|--------|-------|
| Edit `blender_update_player_sphere.py`, run `blender --background --python …` | Ask Claude to modify the scene directly in the open Blender window |
| Blind iteration — no visual feedback until game runs | Viewport screenshot available immediately after each change |
| Script must handle import, export, and reload | Claude issues targeted Python API calls; you trigger export when ready |

### Notes

- Only one MCP client may connect at a time (don't run Claude Desktop and Claude Code
  simultaneously against the same Blender session).
- The server process (`uvx blender-mcp`) is managed by Claude Code; don't launch it
  manually in a terminal.
- The Blender addon listens on `localhost:9876` by default.

---

## Blender Viewport Display by Object Type

Objects whose `wf_Model Type` is `None` (or that have no OAD at all) do not render in the
game engine. Set their Blender **Display As** to **Wire** so they appear as cages rather
than solid meshes — otherwise they obscure the actual level geometry in the viewport.

To apply in one shot (run via MCP or in the Blender scripting console):

```python
import bpy
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.get('wf_Model Type') in ('None', None):
        obj.display_type = 'WIRE'
```

### mm_fromscratch / mm_practice object table

| Object | Class | `wf_Model Type` | Wireframe? |
|--------|-------|-----------------|-----------|
| Practice_path | statplat | Mesh | ✗ |
| Player | player | Mesh | ✗ |
| Room01 | room | *(no OAD)* | ✓ |
| ActBoxOR | actboxor | None | ✓ |
| CamShot01 | camshot | Box | ✗ |
| Camera | camera | Box | ✗ |
| Director | director | None | ✗ (EMPTY) |
| LevelObj | levelobj | Box | ✗ |
| Light01 | light | None | ✗ (EMPTY) |
| Matte | matte | Box | ✗ |
| Target01 | target | Box | ✗ |
| Target02 | target | Box | ✗ |

`Box` means the object has a bounding box used for physics/triggers but no visual mesh;
`EMPTY` objects already show as small axis markers regardless of `Display As`.

---

## Arcade ROM Level Geometry (Marble Madness)

Level paths are not hand-authored — they are faithfully reproduced from the arcade ROM.
The pipeline goes: **ROM → JSON → Blender mesh → WF level**.

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

---

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

---

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

---

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

---

### Actor Spawn Placement

Spawn the Player above the **first walled (trough) segment** so the ball rolls toward the goal
without requiring joystick input during testing.  For Practice this is seg 9:

```python
# heading-based position of seg-9 start: 9 segs × SEG_LEN × (cos 18.28°, sin 18.28°)
SPAWN_POS = (21.364, 7.058, 3.2)   # 0.6 m above seg-9 floor at Z=2.6
```

To play the full S-curve (segs 0–8), a joystick must be connected.

---

### Camera Setup for Marble Madness (SW Isometric)

The arcade original uses a fixed SW isometric view: camera is above-and-SW of the marble,
looking NE+down at roughly 45° elevation.  All three BungeeCam axes must be `Relative` so
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

**CamShot `Target` field must be `'Player'`**, not a fixed Target02 empty.  A fixed world
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

---

### Marble Physics: Friction and Deceleration

The player OAD fields that most affect rolling feel:

| Field | Value | Rationale |
|-------|-------|-----------|
| `Running Deceleration` | `0.0` | Let physics (friction) handle braking; non-zero values easily exceed gravity on shallow slopes and freeze the ball |
| `Surface Friction` (player) | `0.3` | Low enough to roll down grades up to ~2° |
| `Surface Friction` (mesh) | `0.2` | Combined friction = player × mesh; keep low for smooth rolling |

`Running Deceleration` is applied as an artificial brake every frame when no joystick input
is present.  On a 2.2° slope gravity = 0.38 m/s²; any `Running Deceleration` above ~0.35
will freeze the ball.  Setting it to `0.0` leaves all braking to surface friction.

---

### Goal Platform: Back Wall

`rom_to_blender.py` adds a 2 m tall vertical quad face at the far end of the goal platform
(`PATH_HALF * 1.5` wide) to stop the marble rolling off.  This is separate from the trough
walls and is always emitted when `goal_segs` is non-empty.  If the marble still escapes,
increase `wall_h` in `build_path_mesh()`.

---

### Headless Blender Export Fallback

`bpy.ops.wf.export_level` is only registered when MCP is connected (the `debug_bridge`
module injected by the MCP server is needed by `wf_blender/__init__.py`).  For headless
`blender --background --python` runs, use the direct module loader:

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

This bypasses `__init__.py` entirely and calls `export_scene_to_lev` directly.

---

### Marble Actor: Use `sphere.iff`, Not `player.iff`

`player.iff` in the `marble-madness/` directory is a cube (8 verts, 576 bytes).  The
marble must use `sphere.iff` (pre-built UV sphere, 21 KB):

```python
obj['wf_Mesh Name'] = 'sphere.iff'
```

`sphere.iff` is committed in `wflevels/marble-madness/` alongside `mm_fromscratch.ini`.

---

## Level File Format

### cd.iff — Multi-Level Archive
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

### DO_CD_IFF
Defined at `game/game.cc:26`. When defined, loads levels from `cd.iff` via DiskTOC.
When undefined, loads `level%d.iff` from disk directly.

### Level Object Count
Each `.iff` level embeds `_levelData->objectCount` (37 in snowgoons). Temporary objects
(tools, shadows, projectiles) occupy `objectCount .. objectCount + NumberOfTemporaryObjects - 1`.
`NumberOfTemporaryObjects` comes from the levelobj OAD; default is 200.

---

## Scripting System

### Original Design
- **Player script** (per frame): `write-mailbox $INDEXOF_INPUT [read-mailbox $INDEXOF_HARDWARE_JOYSTICK1_RAW]`
  — just forwards raw joystick to the input mailbox.  For an isometric camera
  where screen-up ≠ world-N, use a bit-rotation word instead (see below).

### Camera-Relative Input (SW Isometric)

The WF `MarbleHandler` applies button bits as world-axis impulses:
`EJ_BUTTONF_UP` → world +Y (North), `EJ_BUTTONF_RIGHT` → world +X (East),
etc.  Arrow keys map to these bits via `INDEXOF_HARDWARE_JOYSTICK1_RAW`.

For the MM SW isometric camera (offset −6,−8,+10 looking NE), screen-up =
world NE and screen-right = world SE.  The player expects pressing Up to move
the ball "up the screen" (NE), not world-North.  The fix is to rotate the
four direction bits 45° CW in a Forth word before writing to `INDEXOF_INPUT`:

```forth
\ zForth — use & and | for bitwise ops, NOT "and"/"or"
: cam-remap  0
  over 2048  & if 10240 | then    \ UP    → UP|RIGHT  (2048+8192)  = NE
  over 4096  & if 20480 | then    \ DOWN  → DOWN|LEFT (4096+16384) = SW
  over 8192  & if 12288 | then    \ RIGHT → DOWN|RIGHT(4096+8192)  = SE
  over 16384 & if 18432 | then    \ LEFT  → UP|LEFT  (2048+16384) = NW
  swap drop ;

INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox cam-remap INDEXOF_INPUT write-mailbox
```

Diagonal combos cancel correctly: pressing Up+Right produces
NE+SE = (UP|RIGHT)|(DOWN|RIGHT) — the NE and SE verticals cancel leaving pure
East.  No special diagonal handling is needed.

**Bit values** (from `wfsource/source/hal/sjoystic.h`):

| Bit symbol | Value |
|---|---|
| `EJ_BUTTONF_UP` | 2048 |
| `EJ_BUTTONF_DOWN` | 4096 |
| `EJ_BUTTONF_RIGHT` | 8192 |
| `EJ_BUTTONF_LEFT` | 16384 |

**zForth operator note:** zForth does NOT have `and` or `or` as named words.
Use the primitive symbols `&` (bitwise AND) and `|` (bitwise OR).
Using `and`/`or` compiles silently into a ZF_ABORT_NOT_A_WORD error (code 7)
that prints `zforth compile error 7 (defs): : cam-remap ...` at runtime —
the word is simply not executed every tick, leaving `INDEXOF_INPUT` at 0.
- **Director script** (per frame): reads mailboxes 98/99/100 and writes to `$INDEXOF_CAMSHOT`.
  These mailboxes are set by ActBoxOR trigger zones.
- **ActBoxOR objects**: write a named object's index to a mailbox when the Player enters
  their trigger volume. In snowgoons, one ActBoxOR writes `CamShot01`'s index to mailbox 1021
  (`EMAILBOX_CAMSHOT`) when the Player enters.
- **NullInterpreter stub**: `wftools/engine/stubs/scripting_stub.cc` — replaces Tcl scripting
  with a no-op. All `RunScript()` calls return 0. This is intentional pending replacement
  with a non-Tcl scripting system.

### Level Selection Without Scripts
`_desiredLevelNum` in `WFGame` must be set before `assert(_desiredLevelNum >= 0)` fires.
Normally the shell script (cubemenu) writes `EMAILBOX_LEVEL_TO_RUN` to choose a level.
**Fix (game.cc):** initialize `_desiredLevelNum = 4` (snowgoons) in the constructor
initializer list, and move the `_overrideLevelNum` check to BEFORE the asserts.

---

## Camera System

### Camera State Machine
- **DelayCameraHandler**: waits up to 5 frames for `EMAILBOX_CAMSHOT > 0` then transitions.
  Assertion at `movecam.cc:885` fires if nobody writes a valid CamShot index within 5 frames.
- **BungeeCameraHandler**: main follow camera. Each frame reads `EMAILBOX_CAMSHOT` (mailbox 1021)
  to get the active CamShot object's index. Originally cleared the mailbox after reading
  (relied on ActBoxOR to re-write each frame).
- **NormalCameraHandler**: validates that the stored shot index is a real CamShot object.

### EMAILBOX_CAMSHOT Bootstrap (scripting disabled)
With scripting disabled, ActBoxOR trigger zones never fire. Fix in `level.cc::constructObject`:
when a `CamShot_KIND` object is constructed and the mailbox is still 0, write the CamShot's
actor index to `EMAILBOX_CAMSHOT`. This is a one-time bootstrap; the value persists.

`BungeeCameraHandler::predictPosition()` originally cleared the mailbox after use (line 988).
With scripting disabled this is suppressed — the mailbox stays set to the initial CamShot
so the camera keeps working without per-frame ActBoxOR writes.

---

## LP64 Port Issues

The engine was written for 32-bit PSX/Win32 where `long` = 4 bytes. On Linux 64-bit, `long` = 8 bytes.

### Known LP64 fixes
- **`gfx/rmuv.cc`**: `long* pRMUV` → `int32* pRMUV`; IFFTAG comparison cast to `(int32)`.
- **`gfx/ccyc.cc`**: same fix — `long* pCCYC` → `int32* pCCYC`.

### How to spot LP64 issues
Assertions of the form `assert(*ptr == IFFTAG('x','y','z','w'))` that fail at startup
usually mean a `long*` is being used to read a 4-byte IFF tag/size pair — it reads 8 bytes
instead of 4, so the tag value is wrong. Fix: use `int32*` and cast IFFTAG to `(int32)`.

---

## Level Constructor Ordering Bug (fixed)

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

---

## Build & Run

```bash
cd engine
bash build_game.sh

# Run:
cd wfsource/source/game
LD_LIBRARY_PATH=../../../engine/libs DISPLAY=:0 ../../../engine/wf_game
```

`build_game.sh` compiles all source dirs, skips test/Windows files, uses the scripting stub
and platform stubs from `wftools/engine/stubs/`.
