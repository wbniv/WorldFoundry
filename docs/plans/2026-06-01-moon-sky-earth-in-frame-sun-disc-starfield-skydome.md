# Plan: Moon sky — Earth in frame, Sun disc, starfield skydome

## Context

The sky-actor commit was reverted 2026-06-01 because three things were broken.
All three are now either solved or solvable without engine changes:

| # | Problem | Then | Now |
|---|---------|------|-----|
| 1 | Camera tilt didn't take effect | Used `Track` rotation (no-op for Absolute camshots) | Use `Fixed` — baked at export; raising `LOOK_TARGET` Z actually works |
| 2 | Earth lost in terrain tonality | No texture, only ambient fill | Earth has Blue Marble texture; N·L ≈ 0.93 on camera-facing side |
| 3 | Skydome occluded terrain (R=200 m) | Terrain > 200 m from origin was behind dome surface | R=2000 m: min dome distance 1872 m, max terrain distance 785 m → terrain always wins depth test |

**No engine changes required.** Yon increases 500 m → 2500 m.

## Geometry / framing math (verified)

```
Camera at (0, −100, 80).  CamTarget raised to (0, 0, 50).
  Look pitch: 38.7° down → 16.7° down  (more sky)
  Earth (0,200,50):  32.9° off-center → 11.0° off-center  (half-FOV=30° → now IN frame)
  Sun disc (205,563,21):  20.6° off-center, 697 m away, angular dia 1.32°  (IN frame)
  Skydome R=2000 m:  min 1872 m from cam, terrain max 785 m → depth-safe ✓
```

## cs_chase mockup (after changes)

```
┌──────────────────────────────────────────────────────────────────┐
│ SCORE 0          TIME 0          LAT 26.13  LON -3.62           │
│  ✦ ✦  ✦   ✦  ✦ ☀ ✦  ✦   ✦  ✦  ✦   ✦  ✦  ✦           ┌───┐│
│   ✦     ✦    ✦    ✦  ✦   🌍   ✦  ✦    ✦  ✦   ✦          │ ◉ ││
│     ✦   ✦  ✦    ✦    ✦   ✦    ✦   ✦   ✦     ✦           └───┘│
│                                                                  │
│─────── horizon ──────────────────────────────────────────────── │
│                                                                  │
│         ████    ← lander tower                                   │
│        ██████                                                    │
│─────────┬──┬────────────────────────────────────────────────────│
│         │  │   ← lunar terrain (NAC texture)                     │
│       🧑‍🚀                                                         │
└──────────────────────────────────────────────────────────────────┘
  sky ~40% of frame; starfield in sky band; Earth disc upper-center;
  Sun disc upper-right (along directional-light direction)
```

## Changes — all in `blender_create_moon.py`

### 1. Raise `LOOK_TARGET` and `CamTarget`

```python
LOOK_TARGET = (0.0, 0.0, 50.0)   # was (0.0, 0.0, 0.0)
```

`CamTarget` actor location is set from `LOOK_TARGET`, so this flows through automatically.

### 2. Increase Yon on both camshots

```python
camshot['wf_Yon']        = 2500.0   # cs_chase  (was 500.0)
cs_earth_obj['wf_Yon']   = 2500.0   # cs_earth  (was 500.0)
```

### 3. Restore Sun actor

Add `_build_sun()` helper (UV-sphere R=8 m, white/yellow material) and place along
the existing `SUN_AZ_DEG` / `SUN_ALT_DEG` direction at 600 m from origin:

```python
SUN_DIST_M  = 600.0
sun_x = math.cos(math.radians(SUN_ALT_DEG)) * math.sin(math.radians(SUN_AZ_DEG)) * SUN_DIST_M
sun_y = math.cos(math.radians(SUN_ALT_DEG)) * math.cos(math.radians(SUN_AZ_DEG)) * SUN_DIST_M
sun_z = math.sin(math.radians(SUN_ALT_DEG))                                       * SUN_DIST_M
```

Use `_place_prop()` to wire as Anchored PERM platform with Model Type=Mesh.

### 4. Starfield skydome

**Recover `make_starfield.py`** from git history:
```bash
git show 36febc91:wflevels/moon_site01/make_starfield.py > wflevels/moon_site01/make_starfield.py
python3 wflevels/moon_site01/make_starfield.py   # → starfield.tga (512×256)
```

Add `_build_skydome()` in blender_create_moon.py:
- `bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=2000.0)`
- Flip all normals: `bmesh.ops.reverse_faces(bm, faces=bm.faces)` → inner surface visible from inside
- `starfield.tga` material (white BSDF base so texture is sampled by the engine shader)
- Placed as PERM platform (Anchored, Model Type=Mesh, wf_Moves Between Rooms=True)
- Center at world origin

`starfield.tga` (512×256) goes in PERM atlas alongside `earth.tga` (128×64).
Combined: 131 072 + 8 192 = 139 264 texels — well under the 1024² = 1 048 576 page. ✓

### 5. PERM pool

Current used: ~501 KB of 1 000 000. Adding sun (~20 KB) + skydome (~75 KB) → ~596 KB. Fine.

## Files changed

- `wflevels/moon_site01/blender_create_moon.py` — LOOK_TARGET, Yon, _build_sun, _build_skydome
- `wflevels/moon_site01/make_starfield.py` — recovered from git
- `wflevels/moon_site01/starfield.tga` — generated, committed
- Rebuilt: `moon_site01.lev`, `moon_site01.lvl`, `moon_site01.iff`, `moon_site01-standalone.iff`

## Build & verify

```bash
git show 36febc91:wflevels/moon_site01/make_starfield.py > wflevels/moon_site01/make_starfield.py
python3 wflevels/moon_site01/make_starfield.py
blender --background --python wflevels/moon_site01/blender_create_moon.py
task build-level -- moon_site01
task run-moon
```

Expected at t=0 in cs_chase: terrain in lower ~60% of frame, sky ~40%, Earth disc visible
upper-center, Sun disc upper-right, stars in the sky band.
At t=10s: cs_earth — lander + Earth in telephoto. At t=23s: back to cs_chase.

Add first-light screenshot to `docs/plans/2026-06-03-moon-earth-cutscene.md`.
