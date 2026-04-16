# WF Level Viewer — Design Notes

## Goal

Get World Foundry level geometry visually running — an X11 window, geometry on screen.
No audio, no ODE physics, no Tcl/Perl/Lua scripting required for this milestone.

---

## Approach: standalone viewer

Rather than building the full WF game engine, `wftools/wf_viewer/` is a standalone
C++17 GLX + X11 program (~300 lines) that parses WF MODL `.iff` files directly and
renders them with legacy OpenGL.

### Why standalone over engine boot

The WF game engine startup chain has several hard dependencies that add complexity
without adding value to a geometry viewer:

| Blocker | Location |
|---------|----------|
| `ScriptInterpreterFactory` always creates a `TCLInterpreter` | `source/scripting/scriptinterpreter.cc:62` |
| `#define DO_CD_IFF` in `game.cc` requires `cd.iff` on disk | `source/game/game.cc:26` |
| `BUILDMODE=tool` explicitly errors when `LIB_NAME=game` | `GNUMakefile.bld:222` |
| 13 pre-built `.a` archives are tool-mode, incompatible with game build flags | `objtoolglglwffloatss.linux/` |

The startup chain would be:
```
platform.cc:main() → HALStart() → PIGSMain() → WFGame::RunGameScript()
  → ScriptInterpreterFactory() → TCLInterpreter  ← requires Tcl
  → DO_CD_IFF: load cd.iff                        ← requires full game data
  → RunLevel()
```

Since the MODL binary format is fully self-contained and already well-understood
from the Blender importer/exporter work, a standalone parser avoids all of that.

---

## MODL IFF format

WF uses a simple chunk format (not standard EA IFF): 4-byte ASCII tag +
4-byte LE payload size + payload + padding to 4-byte boundary.

The root chunk is `MODL`, containing:

| Sub-chunk | Layout | Description |
|-----------|--------|-------------|
| `SRC`  | string | Source tool name |
| `TRGT` | string | Target platform string |
| `NAME` | string | Mesh name |
| `ORGN` | 3× int32 | Origin (fixed-point ×65536) |
| `VRTX` | `(iiIiii)` × N | u, v, color, x, y, z — int32 fixed-point ×65536 |
| `MATL` | `(iI + char[256])` × N | flags, color (0xRRGGBB), texture filename |
| `FACE` | `(hhhh)` × N | v1, v2, v3, mat_idx — int16 |

Fixed-point conversion: divide any value by 65536.0 to get game units / UV [0,1].

MATL flags: `0x02` = textured (texture filename is valid), `0x00` = vertex colour only.

---

## Coordinate system

The Blender exporter applies a Y-up transform (`bl_to_wf`):

```python
wf_x =  bl_x
wf_y =  bl_z    # Blender Z → WF Y (up)
wf_z = -bl_y    # Blender Y → WF -Z (depth)
```

The viewer renders in WF space directly; the orbit camera uses Y-up.

---

## Build notes

GL/GLX development headers are not installed system-wide. They are available
in a Podman container overlay:

```
/home/will/.local/share/containers/storage/overlay/eb44d.../diff/usr/include/GL/
```

`build.sh` uses `-idirafter` (not `-I`) so the system's glibc headers take
priority — using `-I` caused the container's older `stdio.h` to shadow the
system one, producing hundreds of `L_tmpnam` / `__fprintf_chk` errors.

Runtime GL libraries (`libGL.so.1`, `libGLX_mesa.so.0`) are already installed
system-wide at `/lib/x86_64-linux-gnu/`.

---

## Verification

Tested with:
- `wflevels/minecart/*.iff` — 8 meshes, 1250+ verts, 550+ faces
- `wflevels/snowgoons/*.iff` — 17 meshes including house, trees, snowmen

Confirmed via strace:
- IFF file opened successfully
- X display connection via `@/tmp/.X11-unix/X0`
- Mesa loaded (`libGLX_mesa.so.0`, `libgallium-25.2.8...so`)
- Process runs cleanly until killed (exit 143 = SIGTERM)

---

## Resuming the engine path

If full engine boot is needed later, the minimal changes are:

1. **Replace `scriptinterpreter.cc`** with a stub that returns a no-op
   `ScriptInterpreter` subclass (don't include `tcl.hp`).
2. **Undefine `DO_CD_IFF`** in `game.cc` so the engine loads `level1.iff`
   from disk instead of seeking into `cd.iff`.
3. **Rebuild** libgame, libgfx, libhal from source with game-mode flags
   (`-DWF_TARGET_LINUX -DGL_RENDERER -DSCALAR_TYPE=float`), not tool-mode.
4. `platform.cc` already provides `main()` — no separate entry point needed.

## Commit

`4581865` — `wf_viewer: standalone OpenGL viewer for WF MODL .iff files`
