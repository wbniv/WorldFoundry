# Plan: build a primitive astronaut for the moon-Site-01 player

**Status:** Not started
**Date:** 2026-05-31
**Estimate:** 30–45 min
**Move-to:** `docs/plans/2026-05-31-moon-astronaut-mesh.md` once plan mode exits.

## Context

The moon Site 01 player avatar is the snowgoons-imported `player` mesh — a placeholder unit shape (current `player.scale = (1.8, 1.8, 1.8)` blanket-stretches it into a 1.8 × 1.8 × 1.8 m cube-ish capsule, which is wrong for a humanoid). The astronaut-from-an-asset-pack path tried first hit dead ends: our `blender_asset_finder` package's OpenGameArt provider is bit-rotted (dead JSON API — already logged as a separate TODO), Polyhaven/Kenney/Quaternius don't carry character models, and Sketchfab needs an API key the user doesn't want to set up. Easier and faster path: **build the astronaut in `blender_create_moon.py` from primitives**, the same way [SMB Mario is assembled in-script](../../../home/will/WorldFoundry.2026-new-level/wflevels/smb_w1_1/blender_create_smb.py) (`_build_mario` at lines 1028-1080) and [Q*bert in `wflevels/qbert_practice/blender_create_qbert.py`](../../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py). No external asset, no license attribution, headless reproducible from the script alone.

## Approach

Mirror the SMB pattern exactly:
1. Add a `_build_astronaut()` helper to `blender_create_moon.py`.
2. Stamp out ~10–12 primitives (UV spheres + cylinders + cubes) at hardcoded Z offsets so the assembled silhouette is recognisable from the vista cam: helmet, visor, torso, PLSS backpack, two arms, two legs, two boots.
3. Each primitive gets a material via the existing `make_mat(name, rgb)` pattern (currently inline in SMB's script — duplicate the small helper into the moon script).
4. Select all parts → `bpy.ops.object.join()` to fold into a single mesh.
5. `bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)` to bake mesh-local origin to feet (`Z=0`) — the WF actor-position-is-feet convention.
6. Assign the built mesh to the snowgoons-imported `player` actor (`player.data = body.data`), drop the `player.scale = (PLAYER_HEIGHT,…)` line — the mesh is already authored at 1.8 m tall in its own coordinates.

### Astronaut anatomy (in metres, all Z relative to feet at 0)

| Part | Primitive | Size | Centre (X, Y, Z) | Colour |
|---|---|---|---|---|
| Boots (×2) | Cube | 0.18 × 0.15 × 0.10 | (0, ±0.12, 0.05) | white |
| Lower legs (×2) | Cylinder r=0.09, h=0.42 | — | (0, ±0.12, 0.31) | white |
| Upper legs (×2) | Cylinder r=0.10, h=0.42 | — | (0, ±0.12, 0.73) | white |
| Hips | Cylinder r=0.20, h=0.10 | — | (0, 0, 0.95) | white |
| Torso | Cylinder r=0.22, h=0.45 | — | (0, 0, 1.225) | white |
| Chest control panel | Cube | 0.20 × 0.08 × 0.12 | (-0.20, 0, 1.30) | dark grey |
| PLSS backpack | Cube | 0.30 × 0.18 × 0.50 | (+0.27, 0, 1.20) | white, slight off-white |
| Shoulders (×2) | UV sphere r=0.11 | — | (0, ±0.27, 1.42) | white |
| Upper arms (×2) | Cylinder r=0.08, h=0.30 | — | (0, ±0.27, 1.27) | white |
| Forearms (×2) | Cylinder r=0.08, h=0.28 | — | (0, ±0.27, 0.98) | white |
| Gloves (×2) | UV sphere r=0.09 | — | (0, ±0.27, 0.84) | white |
| Neck | Cylinder r=0.06, h=0.06 | — | (0, 0, 1.475) | dark grey |
| Helmet | UV sphere r=0.14 | — | (0, 0, 1.66) | white |
| Visor | UV sphere r=0.13, front half | — | (-0.05, 0, 1.66) | gold-amber (`0xc28840`) |

Total height ≈ 1.80 m. X is the level's "forward" (camera +Y), so the chest panel sits on the camera-facing side, backpack opposite, visor faces the camera. Width across shoulders ≈ 0.70 m (with arms), torso ≈ 0.44 m — humanoid proportions, not a cube.

Symmetry primitives use loop `for yo in (-..., +...)` like SMB's legs (`blender_create_smb.py:1054-1058`).

### Why X is "forward" / not "in front of camera"

The moon level's existing camera setup has `LOOK_TARGET = (0, 0, 0)` and the astronaut is at the play-area centre. The chest panel and visor are placed at `-X` so they face the vista camera at `(0, -100, 80)` looking toward origin. (If the camera moves to a chase cam later, the astronaut spins via `Track Object`; relative-to-mesh-local "forward" still points where we want.)

## Files

- `wflevels/moon_site01/blender_create_moon.py` — new `_build_astronaut()` function + `make_mat()` helper duplicated from SMB (a single-script helper, no need to factor into shared module yet); player section drops `player.scale = (PLAYER_HEIGHT, PLAYER_HEIGHT, PLAYER_HEIGHT)` and instead does `player.data = build_astronaut.data`.
- `wflevels/moon_site01/preview.png` — Eevee preview regenerates with the new mesh automatically.
- Outputs: `moon_site01.lev`, `moon_site01.lvl`, `moon_site01-standalone.iff`, `moon_site01.iff`, `Room0.tga`, `lunar_terrain.iff` — all rebuild via `task build-level -- moon_site01`.

## Verification

1. `task build-level -- moon_site01` succeeds. Mesh face count well under the 32000 cap (this is ~12 primitives × ~50 tris/each ≈ 600 tris).
2. `task run-moon` boots without crash. PPM via `WF_GAME_SCREENSHOT_PPM` from the existing `(0, -100, 80)` vista cam shows a recognisable astronaut silhouette in the centre of the frame: white humanoid with helmet + backpack, gold visor.
3. Astronaut feet sit on terrain (gravity-settled, not buried, not floating) — the `transform_apply(location=True)` step is what makes this happen; verifiable by reading `ball pos` from the engine log (Z should be near terrain height + tiny capsule offset).
4. Commit screenshot to `docs/plans/screenshots/2026-05-31-moon-astronaut-engine.png`.

## Risks

- **Tri count creep**: an over-segmented UV sphere (`segments=32, ring_count=16`) is ~1000 tris. Stay at `segments=8, ring_count=5` for the helmet/shoulders/gloves like SMB does (`blender_create_smb.py:1036-1038`). All primitives' segment counts noted in the table assume that range.
- **Origin-at-feet**: easy to forget the `transform_apply(location=True)` step → astronaut renders at chest-height-origin and gravity buries it. SMB's comment at `blender_create_smb.py:1073-1077` is the warning.
- **Material count**: the existing exporter ([`export_level.py:489-522`](../../../home/will/WorldFoundry.2026-new-level/wftools/wf_blender/export_level.py)) emits one MATL entry per Blender material. Keep distinct materials to ~3 (white, gold-amber, dark-grey) so the MATL chunk doesn't bloat.
- **Visor as a half-sphere**: clean half-sphere needs a boolean cut, which is fragile in headless Blender. Easier: use a smaller full sphere offset to the camera-facing side; from any viewpoint past the side of the helmet the gold sphere reads as the visor.

## Related

- [`wflevels/smb_w1_1/blender_create_smb.py:1028-1080`](../../../home/will/WorldFoundry.2026-new-level/wflevels/smb_w1_1/blender_create_smb.py) — Mario primitive build, template.
- [`wflevels/qbert_practice/blender_create_qbert.py:389-500`](../../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) — Q*bert primitive build, alternate template.
- [Moon Tier 2 plan](../../../home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-30-moon-surface-tier2.md) — "astronaut sprite is its own art task"; this closes that open question.
- [`docs/level-building.md` — Physics-mobility actor authoring rules](../../../home/will/WorldFoundry.2026-new-level/docs/level-building.md#physics-mobility-actor-authoring-rules) — feet-at-origin convention.
