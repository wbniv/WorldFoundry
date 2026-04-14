# UV Seam Fix in Mesh Exporter

## Problem

The World Foundry MODL `.iff` format stores one UV coordinate pair per vertex in the
VRTX chunk. Blender stores UVs per *loop* (per face-corner), so a vertex on a UV seam
has a different UV on each side. The previous exporter used a "first-loop-wins"
strategy — keeping the last UV written to each vertex index — causing severe texture
distortion at seams.

## Before / After

![UV seam comparison](uv_seam_fix_comparison.png)

**Before (top row):** the round-trip cylinder (right) shows zigzag distortion at the
UV seam. The original (left) is correct.

**After (bottom row):** both cylinders look identical — the seam is preserved.

## Fix

Split vertices at UV seams: build VRTX entries keyed by
`(orig_vertex_index, u_fixed, v_fixed)`. A vertex on a seam produces two VRTX entries —
one for each UV value — and the FACE indices reference the correct split entry.

UV values are quantised to fixed-point (`int(round(u * 65536))`) to avoid spurious
splits from floating-point noise.

**Vertex count impact:** a 16-sided cylinder expands from 32 → 66 vertices (seam + cap
splits). Typical game-art meshes are modest; the increase is proportional to seam length.

## Commit

`b760feb` — `wf_blender: fix UV seam distortion in mesh exporter via vertex splitting`
