# wf_viewer

Standalone OpenGL viewer for World Foundry MODL `.iff` geometry files.

Reads one or more binary WF MODL IFF files and renders all meshes together in a
GLX/X11 window with flat colour shading and wireframe overlay.

## Build

GL/GLX development headers are not in the default system path on this machine —
they live in a Podman container overlay. `build.sh` handles this automatically:

```bash
cd wftools/wf_viewer
./build.sh
```

Output: `wf_viewer` binary in the same directory.

## Usage

```bash
# Single mesh
DISPLAY=:0 ./wf_viewer ../../wflevels/minecart/cart.iff

# All meshes in a level directory (rendered together)
DISPLAY=:0 ./wf_viewer ../../wflevels/minecart/*.iff
DISPLAY=:0 ./wf_viewer ../../wflevels/snowgoons/*.iff
DISPLAY=:0 ./wf_viewer ../../wflevels/streetback/*.iff
```

## Controls

| Input | Action |
|-------|--------|
| Left mouse drag | Orbit (tumble) |
| Scroll wheel | Zoom in/out |
| `R` | Reset view |
| `Q` / `Esc` | Quit |

## File format parsed

WF MODL IFF uses a simple chunk structure: 4-byte ASCII tag + 4-byte LE payload
size + payload + padding to 4-byte boundary.

| Chunk | Layout | Notes |
|-------|--------|-------|
| `VRTX` | `iiiiii` × N | u, v, color, x, y, z — all `int32` fixed-point ×65536 |
| `MATL` | `(iI + char[256])` × N | flags, RGBA color, texture filename |
| `FACE` | `hhhh` × N | v1, v2, v3, mat_idx — all `int16` |

Coordinates: divide any fixed-point value by 65536.0 to get game units.
Texture mapping: divide u/v by 65536.0 for the [0, 1] UV range.

## Why standalone instead of the WF engine

The WF game engine startup chain (`HALStart` → `PIGSMain` → `WFGame` →
`RunGameScript`) requires Tcl scripting (`ScriptInterpreterFactory` always
creates a `TCLInterpreter`), a `cd.iff` game data file, and game-mode build
flags that are incompatible with the already-built tool-mode `.a` archives.

For a geometry viewer those dependencies add no value — the MODL binary format
is fully self-contained and well-understood from the Blender importer/exporter work.

## Commit

`4581865` — `wf_viewer: standalone OpenGL viewer for WF MODL .iff files`
