# Plan: Moon-surface Tier 2 — walkable Artemis south-pole site

**Status:** Not started
**Date:** 2026-05-30
**Estimate:** 5–10 days (average-programmer scale)
**Background:** [Moon mapping data investigation](../investigations/2026-05-30-moon-mapping-data.md)

## Goal

Recreate a real piece of the lunar south pole as a walkable level in
WorldFoundry. Player avatar drops onto real LOLA-derived terrain, walks
around under correct lunar gravity, can see real LROC imagery as the
ground texture.

Scope is **Tier 2** from the investigation: one Artemis III candidate site,
PGDA 5 m/pix DEM, ~1 km × 1 km initial play area (expand later), single
static terrain mesh — no streaming/LOD/tile system yet.

## Approach

Follow the same pipeline as `smb_w1_1`: a Blender script is the golden
source. It builds the level geometry; the existing `wf_blender` exporter
emits a `.lev`; `levcomp-rs` + `iffcomp-rs` produce the `.lvl` and `.iff`.

The only WF-side novelty is reading a GeoTIFF DEM at *Blender-script
authoring time* and turning it into a subdivided plane. No new actor
types, no new collider primitives — Jolt's existing triangle-mesh collider
already handles arbitrary static geometry, which is what the SMB ground
slabs use. Lunar gravity needs one engine change (per-level gravity
override).

## Phases

### Phase 1 — Data acquisition (~0.5 day)

Pick one Artemis III candidate site. **PGDA Site 01 = Connecting Ridge
near Shackleton** is the best-mapped — PGDA publishes a 5 m/pix DEM and
NCCS has its derived illumination products. (PGDA Site 04 is Shackleton
Rim, a different region.) Same Connecting Ridge that Blue Origin's
Blue Moon MK1 Endurance lander is targeting in fall 2026.

- Download the site's 5 m/pix LDEM (GeoTIFF) from PGDA product 78:
  `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif`
- Download the LROC WAC south polar mosaic (100 m/pix) as a coarse
  texture fallback.
- Identify which LROC NAC frames cover the chosen ~1 km × 1 km extent;
  download those (typically 2–4 frames at 0.5 m/pix).
- Inspect with `gdalinfo` and a quick render in QGIS or matplotlib —
  confirm extent, projection (south polar stereographic), no-data values.

Store under `wflevels/moon_site04/data/` (gitignored if files are large;
add a `README.md` with the exact URLs and SHA256s).

**Verify:** `gdalinfo` shows the expected extent and CRS; a quick
matplotlib hillshade looks like the south pole.

### Phase 2 — DEM → Blender mesh (~1–2 days)

New script `wflevels/moon_site04/blender_create_moon.py`, modeled on
[smb_w1_1's blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py).
At authoring time it:

1. Opens the LDEM GeoTIFF via GDAL Python bindings (`from osgeo import gdal`).
   Read into a NumPy array of float32 elevations in metres.
2. Crops to the playable extent (initially 1 km × 1 km = 200 × 200
   samples at 5 m/pix).
3. Subtracts the mean elevation so the play area centres on `Z = 0` in
   WF-space.
4. Creates a Blender plane subdivided to 200 × 200 (40k quads → 80k tris).
   Sets vertex `co.z = sampled_height` from the array. Recompute normals.
5. Applies the basic material (texture-baked stub for now; see Phase 3).
6. Adds a Player spawn at `(0, 0, 100)` — the gravity drop is the proof
   of collision.
7. Adds a CamShot 50 m up looking down at the spawn (free-look fallback
   pending Phase 4 polish).

**Resolution choice:** 5 m horizontal sampling gives 40k quads — well under
typical WF level budgets. A future expansion to 10 km × 10 km at 5 m/pix
would be 2000 × 2000 = 4M quads; that's the threshold where we need LOD or
tiling. Out of scope for Tier 2 — we'll cap at 1–2 km on a side.

**Verify:** open the resulting `.blend` headlessly, render a top-down
preview, confirm the surface resembles the hillshade from Phase 1.

### Phase 3 — Texture bake (~1 day)

The DEM provides shape, not colour. Texture comes from LROC imagery
reprojected to match the play area's coordinate frame.

1. `gdalwarp` the NAC + WAC imagery from south polar stereographic to a
   local flat projection centred on the site, matching the heightfield's
   sample grid.
2. Composite NAC (where available) over WAC (everywhere else) into a
   single GeoTIFF of the playable extent.
3. Convert to a PNG / TGA at 4096×4096 or 2048×2048 (fits WF texture
   budget per memory; SMB uses 512² textures).
4. In `blender_create_moon.py`, UV-unwrap the terrain plane to a single
   atlas, assign the baked texture.

**Verify:** render the textured terrain in Blender; rocks and crater rims
in the texture should line up with elevation peaks/dips.

### Phase 4 — Lunar gravity (**RESOLVED — no engine change required**)

Initial plan called for a per-level `Gravity` field through the OAS
schema feeding `JoltBackendSetGravity()`. On inspection, WF gravity is
already **per-actor** — `MovementBlock::FallingAcceleration`
(`wfsource/source/oas/movebloc.inc:67`) — and Jolt's global gravity is
explicitly passed as zero to character updates
(`jolt_backend.cc:744-745`) so the backend default never leaks through.
Setting `player['wf_Falling Acceleration'] = 1.62` in
`blender_create_moon.py` is the complete fix.

Aligns with the [OAD/IFF compat policy](../../wfsource/source/oas/) of
not adding new OAS fields ahead of the Blender-export-primary cutover.

**Verify:** in Phase 5's drop test, time-to-impact from h=5 m should be
~2.5 s under lunar g (`sqrt(2h/g)`), vs ~1.0 s under Earth g — easily
distinguishable.

Future per-level gravity (atmospheric drag, varying-g sequences) can
revisit this through the OAS schema once the post-Blender cutover lifts
the field-add freeze.

### Phase 5 — Build & first drop (~0.5–1 day)

Use existing build pipeline:

```
blender --background --python wflevels/moon_site04/blender_create_moon.py
bash wflevels/moon_site04/build_level_binary.sh
task build
task run -- wflevels/moon_site04/moon_site04-standalone.iff
```

(The `build_level_binary.sh` script is per-level — copy & adapt from
`smb_w1_1/`.)

- Confirm engine loads the level without abort.
- Confirm player avatar drops, rests on terrain (not falls through,
  not sinks below).
- Walk around with joystick, confirm collision is stable across crater
  rims and slope changes.
- Screenshot.

**Verify:** debug-bridge headless test (`tests/verify_moon_landing.py`):
spawn player at Z=100, step ~10 s of frames, confirm player Z stabilises
near terrain height, X/Y stays inside extent.

### Phase 6 — Astronaut polish (~1 day, optional)

Cheap visual upgrades that sell the level:

- Black skybox (no atmosphere) — override the default sky asset.
- Single hard directional sunlight at low angle (south pole sun
  geometry — sun stays ~1–2° above horizon).
- No ambient fill except a faint earthshine term.
- Player avatar: reuse Mario placeholder initially; astronaut sprite
  is its own art task.

**Verify:** screenshot looks plausibly "Moon-like" — hard shadows, black
sky, low-contrast grey terrain matching NAC imagery.

## Open questions

- **Player avatar scale:** astronaut is ~1.8 m tall (decision: 2026-05-30).
  Use 1.8 m from the first build — collision capsule sized to match —
  even if the placeholder visual is still a Mario-style sprite. Final
  astronaut art is its own task.
- **Curvature:** at 1 km × 1 km, curvature drop is ~70 cm — visible at
  the horizon but not gameplay-affecting. At 10 km it's ~7 m and starts
  to matter. Tier 2 defers this; flat-projected is fine for the first
  level. Tier 1 (global) must address it.
- **NAC seams:** if the play area spans two NAC frames with different
  lighting, the seam will be visible. Pick a site/extent covered by a
  single frame for v1.
- **Real-world distance unit:** **WF 1 unit = 1 m** (confirmed
  2026-05-30). DEM elevations and X/Y meters from GeoTIFF map 1:1 onto
  WF coordinates — no scale factor needed.

## Verification summary

| Phase | Method |
|---|---|
| 1 | gdalinfo + matplotlib hillshade |
| 2 | Blender top-down render matches hillshade |
| 3 | Textured Blender render: terrain texture aligns with shape |
| 4 | Drop test, 6× time-to-impact ratio vs. Earth-g level |
| 5 | Debug-bridge headless: player Z stabilises on terrain |
| 6 | Screenshot review |

## Out of scope (deferred to Tier 1 / Tier 3)

- Streaming / tiled terrain for the full Moon — Tier 1.
- Sub-meter rocks / boulders — Tier 3 (Chandrayaan-2 OHRC pipeline +
  procedural scatter).
- Curved-manifold collision for large extents — Tier 1.
- Multiple sites in one level — separate levels for now.
- Per-actor footstep audio / dust effects — gameplay polish, not Tier 2.

## Related

- [Moon mapping data investigation](../investigations/2026-05-30-moon-mapping-data.md)
- [smb_w1_1 blender source](../../wflevels/smb_w1_1/blender_create_smb.py) — pipeline template
- [Jolt physics integration](../investigations/2026-04-14-jolt-physics-integration.md)
