# Aquarium — 55 gal acrylic tank, one fish, one anemone

A 55 gallon acrylic tank (48 × 13 × 21 in, ½ in walls) on a stand in a dark room. It has sand, a rock, a bubble-tip
anemone, and a fish you swim with the arrows. The plan, its evidence, and the verification record are in
[`docs/plans/2026-09-30-aquarium-level.md`](../../docs/plans/2026-09-30-aquarium-level.md).

<img src="../../docs/plans/2026-09-30-aquarium-level/phase2-frame-a.png" width="640">

**Status (2026‑09‑30): Phase 2.** The scene is static and correct, and the fish is a **placeholder**: the Phase 1
spike's orange ellipsoid with a white tail. Phase 3 replaces it with the canonical clownfish from
`wflevels/aquarium/clownfish.py`, and adds the anemone close-up camera and the dart.

## Build and run

```
task aquarium-level     # Blender → aquarium.lev → aquarium.iff + aquarium-standalone.iff (deps: tools-build)
task run-aquarium       # wf_game on wflevels/aquarium-standalone.iff (deps: ensure-build, aquarium-level)
python3 -m pytest tests/test_aquarium_level.py            # regression guard
python3 wflevels/aquarium/run_aquarium_checks.py          # frame A + every wall held 5 s, over the debug bridge
```

`task aquarium-level` needs the `wf_blender` add-on installed. A second run is a no-op. `run_aquarium_checks.py`
runs the already-built level under `-rate20`. It uses `engine/wf_game`, falling back to the main checkout's
(`WF_GAME=` overrides that), and writes its screenshots to `~/tmp/aquarium-phase2`. The game window opens on the
real desktop, so a key typed while it has focus reaches the fish. The script detects that (un-commanded motion)
and marks the run `CONTAMINATED`, so leave the window alone while it runs.

## Controls (Phase 2)

| Input | Action |
|---|---|
| ← / → | Swim left / right; the fish turns to face the way it swims |
| ↑ / ↓ | Swim up / down |
| B (`2`) / C (`3`) held | Swim toward / away from the glass |
| release | Glide to a stop (air drag, × 0.9 per tick) |

Dart (A) is Phase 3. The fish is held under the water line and 0.25 in off each end wall by its script. The sand,
the back wall and the invisible front collider stop it physically.

## What is modelled

All sizes come from [`aquarium_constants.py`](aquarium_constants.py) at `WORLD_SCALE = 10`, so 1 in = 0.254 m. The
origin is the centre of the tank's footprint, and z = 0 is the outer base.

| Actor | What it is |
|---|---|
| `Player` | Placeholder fish, 3.5 in, `Physics` with no gravity, spawns at (−1.6, 0, 2.4) m. Its bbox is authored symmetric (0.889 × 0.26 × 0.356 m) so levcomp's 0.25 m rule never shifts the capsule |
| `tank-shell` | Bottom, back and two end walls as one Mesh `statplat`, open at the front and top. Pale-cyan outer faces, brighter front edges. The inner faces are water-blue below the water line (the back film), a light band at the line, and dark above it |
| `tank-front-collider` | Invisible slab in the front-glass plane. Plan B has no front face, so this keeps the fish in |
| `tank-rim` | Chamfered ring round the top. It overhangs the walls, so no rim face is coplanar with a wall face |
| `sand` | 2 in deep, top at 2.5 in; 24 × 6 flat quads in three shades |
| `rock` | Low-poly convex hull, 1.7 × 1.3 × 0.55 m, with a flat top at x +2.5 m |
| `anemone` | Static bubble-tip about 7.5 in across: a base disc, a faceted column, an oral disc, and 17 two-tone tentacles with bulb tips. They are split into a back set (y +0.36 m) and a front set (y −0.36 m), so a fish at y = 0 swims between them without touching (checked: no deflection) |
| `anemone-zone` | Invisible `target` carrying a ±2.2 m box round the anemone, for the Phase 3 camera switch |
| `stand`, `room-backdrop` | Dark-brown stand and a navy wall, so the camera never sees the void |
| `SunLight`, `AmbientLight` | Directional 0.72, from above (65°) on the camera side; cool ambient (0.36, 0.43, 0.50) |
| `cs_front` + `Camera` + `LookAt` | Camshot A: locked at (0, −11, 2.667) m, looking at the tank's centre. Fog `0x0d5f7a`, 6 → 40 m |

## What is not modelled

- **No front pane, and nothing translucent (Plan B).** The engine drops texture alpha (plan § Phase 0 verdict), so a
  pane would draw opaque and hide the fish. The water is carried by the fog, the water-coloured inner faces and the
  water-line band. Plan A, a translucent pane, waits on its own engine TODO.
- The anemone does not sway (optional, Phase 4). There is no water surface, no lid, no bubbles and no caustics.
- There is no camshot B (the anemone close-up), no Director zone switch and no dart. Those are Phase 3.

## Findings worth keeping

- **The light aim is mirrored here.** The doc's recipe for outward-wound geometry (`B = −alt`, `C = −90°`) left every
  face at exactly the ambient term in the first capture. This level uses `B = +alt`, `C = +90°`, which is
  `wf_light_aim`'s form. As `docs/level-building.md` says: verify every light with a capture.
- **Leave clearance between tentacle sets.** With the sets at ±0.22 m, a fish at y = 0 was pushed 0.27 m sideways and
  rode 0.6 m up over the bulbs. The gap has to clear the capsule radius (0.13 m), the padding (0.02 m) and Jolt's
  0.1 m predictive contact distance. ±0.36 m does.
- **The `Player` must come before `tank-shell`.** It does, because it is imported with the scaffold. The regression
  test asserts it, since Jolt ignores a static body whose bbox already encloses the character.
