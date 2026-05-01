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
  — just forwards raw joystick to the input mailbox.
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
