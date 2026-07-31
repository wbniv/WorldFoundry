# Plan: add an Artemis lunar lander to the moon Site 01 scene

**Status:** Done
**Date:** 2026-05-31
**Estimate:** 30 min · **Actual:** ~30 min

## Context

The moon level has a 1.8 m astronaut walking the LOLA terrain — but no other landmark to anchor the scene as an Artemis mission rather than a generic Apollo landing. Add a recognisable Artemis-era lunar lander. SpaceX Starship HLS (Human Landing System) is the iconic Artemis III/IV silhouette — towering white cylinder with nose cone, Raptor engines clustered at the base, no Apollo-style splayed legs. It's also visually clearly contemporary, not Apollo 11 nostalgia.

(Blue Origin's Blue Moon MK1 Endurance is the other Artemis-era lander and is the one literally landing at this site fall 2026 — could swap to that later as a level variant. Starship for v1 because its silhouette is more distinctive at vista distance.)

The target here is a **realistic simulation**: real Artemis-era vehicle, real 1:1 dimensions, and a real actor (not background scenery) so future work can drive it like the actual vehicle would behave — culminating in a launch sequence. The astronaut next to it should read at correct human-vs-Starship scale (1.8 m beside ~50 m).

## Approach

Same in-script primitive build pattern as `_build_astronaut()` / SMB Mario / Q*bert. New `_build_artemis_lander()` helper in `blender_create_moon.py` that stamps ~10 primitives, joins them, and places the lander as its **own actor** (reusing an existing movable actor class with a custom mesh — *not* the `statplat` background-scenery shortcut used for terrain) offset from the astronaut so both are framed by the vista camera.

The lander is an object, not part of the terrain — it's a proper actor so a future script can target it (the obvious v2 is a launch sequence: countdown, Raptor flame ignition, vertical thrust, ascent). For v1 it sits at rest on the regolith; the actor wrapper is the hook future work attaches to.

### Lander anatomy (1:1 real scale)

| Part | Primitive | Size | Centre (X, Y, Z) | Colour |
|---|---|---|---|---|
| Heat-shield base | Cylinder r=4.5, h=2.0 | — | (0, 0, 1.0) | dark grey |
| 3× Raptor nozzles | Cone r1=1.0 → r2=0.55, h=3.2 | — | 3 at angle [0°, 120°, 240°] @ r=2.4, z=−0.6 | dark grey |
| Main body | Cylinder r=4.5, h=36 | — | (0, 0, 20) | white |
| Crew access door | Cube | 1.8 × 0.3 × 2.0 | (−4.5, 0, 10) | dark grey |
| ARTEMIS stripe | Cube | 0.4 × 9.0 × 0.7 | (−4.6, 0, 28) | dark grey (NASA worm placeholder) |
| Nose cone | Cone r1=4.5 → r2=0.0, h=9.0 | — | (0, 0, 42.5) | white |

Total height ~47 m, base diameter ~9 m. From the (0, −100, 80) vista cam at distance ~151 m to (+30, +25, 0), the lander reads ~17.7° tall in frame — clearly the dominant landmark, as a 50 m vehicle on a 1 km play area should be.

### Placement

`(X, Y) = (+30, +25)` puts the lander to the astronaut's right (camera-left, since camera at -Y looking +Y) and slightly forward, so the vista cam catches both. `wf_Mobility = 'Anchored'` for v1 — gravity doesn't act on it and it stays put, but it's a discrete actor (own class entry, own OAD), so a future script can flip the mobility or drive position for a launch sequence.

## Files

- `wflevels/moon_site01/blender_create_moon.py` — add `_build_artemis_lander()` helper + a `lander` actor placement section before the export.
- Rebuild outputs (`moon_site01.lev`, `moon_site01-standalone.iff`, `lunar_terrain.iff`, `Room0.tga`, etc.)
- Eevee preview regenerates.

## Verification

1. `task build-level -- moon_site01` clean.
2. `task run-moon` boots; PPM via `WF_GAME_SCREENSHOT_PPM` shows the white Starship at frame-right with the astronaut on the left.
3. Lander is its own actor — visible in the debug-bridge actor list, distinct from terrain / `statplat`.
4. Lander stands upright at rest (`Anchored` for v1; doesn't drift, doesn't fall).
5. Mesh face count `< 32000` (this is ~10 primitives × ~50 tris ≈ 500 tris).
6. Astronaut-to-lander scale reads correctly in screenshot (1.8 m human dwarfed by ~47 m vehicle).

## Risks

- **Room bbox**: lander base at z=0, top at z=47. Current room z_max ~150 → ~100 m of headroom (enough for a future ascent animation before it leaves the level). X=30 / Y=25 are inside the ±505 room extent.
- **Tri count creep**: cones with too many vertices balloon — keep `vertices=8`.
- **Lighting**: at sun altitude 2°, vertical surfaces light unevenly. Will look correct for a low-sun moon scene.

## Follow-ups

- **Launch sequence (v2)**: countdown timer, Raptor exhaust effect at base, vertical ascent via scripted position or mobility flip to `Physics` + upward thrust. Lander being a proper actor (not `statplat`) is the foothold for this work.
- **Dedicated `lander` OAD (v2)**: v1 reuses an existing movable actor class with a custom mesh; v2 may want its own `lander.oad/.hp` for class-specific script hooks (ignition, throttle, abort).

## Related

- [Moon Tier 2 plan](2026-05-30-moon-surface-tier2.md) — Site 01 is the connecting ridge that Blue Moon MK1 actually targets fall 2026.
- [`docs/investigations/2026-05-30-moon-mapping-data.md`](../investigations/2026-05-30-moon-mapping-data.md) — site context.
- [Moon astronaut mesh plan](2026-05-31-moon-astronaut-mesh.md) — same primitive-build template.
