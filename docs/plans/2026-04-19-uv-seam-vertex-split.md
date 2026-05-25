# ✅ DONE: Fix UV Seam Distortion in Mesh Exporter (commit b760feb)

**Status:** DONE (commit `b760feb1`) — vertex splitting at UV seams fixes the cylinder round-trip.

## Context

The World Foundry MODL binary `.iff` format stores one UV coordinate pair per vertex
in the VRTX chunk. Blender's mesh model stores UVs per *loop* (per face-corner), so a
vertex that sits on a UV seam has a different UV on each side of the seam. The previous
exporter used a "first-loop-wins" strategy — it iterated loops and kept the last UV
written to each vertex index. This meant seam-edge vertices got whichever UV happened
to be written last, causing severe texture distortion on and near the seam.

---

## The Problem

A UV seam is a deliberate cut in the UV map — the same geometric vertex has UV (1.0, y)
on one side and (0.0, y) on the other. With one UV slot per vertex, one of those values
must be discarded. "First-loop-wins" picks arbitrarily, so the triangles crossing the
seam interpolate across the full texture width instead of wrapping cleanly.

![Before/after comparison](../../../SRC/WorldFoundry-wbniv/wftools/wf_blender/docs/uv_seam_fix_comparison.png)

**Before (top row):** the round-trip cylinder (right) shows severe zigzag distortion at
the UV seam. The original (left) is correct.

**After (bottom row):** both cylinders look identical — the seam is preserved.

---

## Fix — vertex splitting at UV seams

**File:** `wftools/wf_blender/export_level.py` — `_write_mesh_iff`

Instead of one VRTX entry per geometric vertex, build entries keyed by
`(orig_vertex_index, u_fixed, v_fixed)`. When the same geometric vertex appears with
two different UVs (i.e. it sits on a seam), two VRTX entries are created. FACE indices
reference the split entries.

```python
split_verts = []          # list of (co, u, v)
split_map   = {}          # (orig_vi, u_key, v_key) → new_vi

for face in bm.faces:
    tri = []
    for loop in face.loops:
        orig_vi = loop.vert.index
        u = loop[uv_layer].uv.x if uv_layer else 0.0
        v = loop[uv_layer].uv.y if uv_layer else 0.0
        u_key = int(round(u * 65536))   # quantise to fixed-point to avoid float noise
        v_key = int(round(v * 65536))
        key = (orig_vi, u_key, v_key)
        if key not in split_map:
            split_map[key] = len(split_verts)
            split_verts.append((bm.verts[orig_vi].co.copy(), u, v))
        tri.append(split_map[key])
    face_triples.append((tri[0], tri[1], tri[2], face.material_index))
```

Vertex count impact: a 16-sided cylinder goes from 32 → 66 vertices (seam + cap splits).
Worst case is a mesh with many seams, but typical game-art meshes are modest.

---

## Verification

- **Cylinder test:** 32 → 66 vertices; round-tripped checkerboard texture matches original
- **Render:** `docs/uv_seam_fix_comparison.png` — top row before (distorted), bottom row after (clean)
- **snowgoons round-trip:** `house.iff` still exports 28 MATL entries correctly; no regression
