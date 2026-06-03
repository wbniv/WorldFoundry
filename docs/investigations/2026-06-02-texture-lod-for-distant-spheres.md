# Texture LOD sizing for distant spheres

**Date:** 2026-06-02
**Context:** Needed to pick the right `earth.tga` resolution for the Earth sphere
in `wflevels/moon_site01/`. Same method applies to any textured sky body (Moon,
Sun disc, distant planet) or any far-away prop.

---

## The question

> "Given a sphere of radius **R** metres placed **d** metres from the camera,
> displayed in a window **W** pixels wide at horizontal FOV **θ_fov**, what
> texture width (in texels) is actually needed?"

---

## Geometry diagram

```
                         ┌───────────────────────────────────────────────────┐
CAMERA                   │                SCREEN (W px wide)                 │
  ●──────────────────────┤◄─────────────────────── W ──────────────────────►│
  │        d             │         ┌───────────────────────────┐              │
  │◄───────────────────►│         │  Earth sphere: px_screen  │              │
  │                      │         └───────────────────────────┘              │
  │                      └───────────────────────────────────────────────────┘
  │
  │  half-angle α = arctan(R / d)
  │  full angle  θ_obj = 2α
  │
  │                    ╭──────────╮
  │                   ╱            ╲
  │         d        │      ●       │   radius R
  │◄────────────────►│      Earth   │
  │                   ╲            ╱
  │                    ╰──────────╯

```

## Texture coverage diagram

```
Equirectangular texture (2:1 aspect):

  ┌────────────────────────────────────────────────────────────────────────────┐
  │ΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩ OCEAN ΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩ│ 0°
  │░░░░░CLOUDS░░░░ AMERICAS ░░░░░░░░░░░░ EUROPE/AFRICA ░░░░░░░░░ ASIA ░░░░░░░│
  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│ equator
  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│
  │ΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩ OCEAN ΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩΩ│-90°
  └────────────────────────────────────────────────────────────────────────────┘
   ←──────────────────────── texture_width texels ────────────────────────────→

  Visible hemisphere face-on = half the equatorial circumference:

      ┌──────────────────────────────────────┐◄── visible arc ≈ π×px_screen/2
      │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│
      └──────────────────────────────────────┘
       ◄────── ~127 texels useful (@ 640px) ──────►

  Everything outside that band exists in the texture but is never magnified
  beyond 1:1 (you're viewing the back of the sphere).
```

---

## Formula

### Step 1 — angular diameter of the sphere (degrees)

```
θ_obj = 2 × arctan(R / d)
```

### Step 2 — screen pixels covered by the sphere diameter

```
px_screen = W × (θ_obj / θ_fov)
```

### Step 3 — useful texture width

The equatorial circumference of the sphere maps to the full texture width, but
you only ever see **one hemisphere** face-on, so the visible equatorial arc is
≈ half the circumference:

```
texels_needed = π × px_screen / 2   ≈ 1.57 × px_screen
```

Round **up** to the nearest power of two for GPU alignment.

One extra doubling as a sharpness margin (so edges don't magnify) gives the
**recommended** texture width. Anything beyond that is wasted atlas space.

---

## Earth sphere worked example (Moon Site 01)

| Parameter | Value |
|---|---|
| Sphere radius R | 20 m |
| Camera position | (0, −100, 80) |
| Earth position | (0, 200, 50) |
| Distance d | √(300² + 30²) ≈ **301 m** |
| Angular diameter θ_obj | 2 × arctan(20/301) ≈ **7.6°** |
| Window width W | 640 px (user's interactive window) |
| Horizontal FOV θ_fov | 60° |
| **Screen pixels covered** | 640 × (7.6/60) ≈ **81 px** |
| Useful texture width | 1.57 × 81 ≈ 127 texels → **128 texels** |
| Useful texture height | 128 / 2 = **64 texels** (equirectangular 2:1) |
| **Chosen resolution** | **128 × 64** |

At this resolution each texel ≈ 1 screen pixel at the equator — no
magnification blur, zero wasted capacity.

### What larger sizes would cost vs. gain

| Resolution | Atlas area | Gain over 128×64 |
|---|---|---|
| 128 × 64 | 8 192 texels | baseline (chosen) |
| 256 × 128 | 32 768 texels | visible only on a ~1280 px window |
| 512 × 256 | 131 072 texels | **none** — 16× cost, zero visible detail |
| 1024 × 512 | 524 288 texels | **none** — 64× cost |

---

## When to revisit

Rerun the math if any of these change:

- The sphere moves closer (smaller d → larger px_screen → bigger texture needed)
- The window resolution increases significantly (e.g. 4K display)
- The FOV narrows (telephoto → same object appears larger → more pixels → bigger texture)
- The sphere radius grows

---

## Texture setup in the WF Blender pipeline

WF's fragment shader (`backend_modern.cc kFS`) samples the mesh texture **only
when vertex color is white** (`step(0.99, min(r,g,b))`). The exported `MATL
_color` field drives per-vertex color. To activate texture sampling on a
Principled-BSDF material:

```python
mat = bpy.data.materials.new('earth_mat')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
tex_node.image = bpy.data.images.load('earth.tga')
mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
# Force white so exporter sets MATL _color = (1,1,1) → texture is sampled.
bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
```

The `.tga` file must live beside the `.lev` source (or referenced by full path
in the script); `levcomp-rs` picks it up via `asset.inc` and packs it into the
LVAS asset bundle.

UV spheres from `bpy.ops.mesh.primitive_uv_sphere_add` carry automatic
equirectangular UVs — no manual unwrap needed for a globe-mapped texture.
