# Moon mapping data — topography & imagery (2026-05-30)

**Goal:** use real lunar data to recreate the Moon's surface as a walkable
terrain in WorldFoundry — players and physics objects rest on it, collide with
it, traverse it.

Summary of what publicly available datasets exist for lunar topography (DEM)
and imagery, their resolutions, how much of the Moon they cover, and how that
maps to a game-engine collision surface.

## Topography (DEM)

The reference instrument is **LOLA** (Lunar Orbiter Laser Altimeter) on LRO,
operating since 2009. As of 2026 LOLA has collected **>6.5 billion** range
measurements with **~10 cm vertical precision** and **~1 m absolute accuracy**.
LOLA's framework is now the de-facto lunar geodetic reference.

### Global products

| Product | Pixel scale | Coverage | Notes |
|---|---|---|---|
| LOLA global DEM | **118 m/pix** | 100% (gridded), ±60° N/S high quality | Gridded from LOLA shots; equatorial gaps between LRO ground tracks up to several km, infilled by interpolation. |
| LOLA + SELENE/Kaguya TC merged DEM (SLDEM2015) | **~59 m/pix** (effective ~60 m at equator) | **±60° latitude** (most of nearside + farside) | Adds Japanese Kaguya stereo to fill equatorial LOLA gaps. Highest-resolution **global** topography. |
| LROC WAC GLD100 (stereo photogrammetry) | **100 m/pix** | **98.2%** of the surface (79°S–79°N) | Computed from ~69,000 WAC stereo models. Not laser altimetry — photogrammetric heights. |

### Polar / Artemis-grade products

LOLA's polar orbit gives dense ground-track crossings near the poles, so the
best topography is at the poles, exactly where Artemis needs it.

| Product | Pixel scale | Coverage | Notes |
|---|---|---|---|
| South pole LDEM (PGDA) | **20 m/pix** | 80°–90° S | Reference Artemis-zone topography. RMS height uncertainty 0.3–0.5 m, slope 1.5–2.5°. |
| Site-specific LDEMs | **5 m/pix** | Discrete Artemis III candidate sites | GeoTIFF, south polar stereographic, MOON_ME / DE421 frame. |

### Gaps

Even after 17 years there are equatorial swath gaps between LOLA ground tracks
(few-km width); SLDEM2015 backfills these from Kaguya stereo. No gridded gaps
remain — but the *effective* topographic resolution falls from ~5 m at the
poles to ~60 m at the equator.

## Imagery

Two instruments dominate: LROC's **NAC** (Narrow Angle Camera, 0.5 m/pix at 50 km
orbit) and **WAC** (Wide Angle Camera, ~100 m/pix).

### Wide-angle (full coverage)

- **LROC WAC global morphology mosaic**: 100 m/pix, near-100% coverage,
  uniform illumination. The standard "this is what the Moon looks like" basemap.

### Narrow-angle (high-res)

- **NAC raw coverage**: as of 2026, ~**99.98%** of the Moon has at least one
  NAC frame (only ~0.018% never imaged at slews <30°). **Sub-meter pixel scale
  (0.5–2 m)**.
- **NAC at favorable illumination (incidence ≤20°)**: only **~29.7%** of the
  surface. This matters because shadows and lighting geometry change what's
  visible — most regions have NAC frames, but not always under flattering
  light.
- **Controlled global NAC mosaic**: does **not** exist. The program produces
  ~50 regional controlled mosaics (Constellation regions of interest) at
  ~1 m/pix; everything else is uncontrolled / per-frame.

### Other imagery sources

- **Chandrayaan-2 OHRC** (India, 2019–): **0.25–0.32 m/pix**, the highest-
  resolution lunar imagery available. Selected strips only — not global. Used
  recently for sub-meter DEMs over Artemis candidate sites.
- **SELENE/Kaguya TC**: ~10 m/pix stereo imagery, near-global, feeds SLDEM2015.

## Overall status (2026)

- **Topography**: solved to first order. Global gridded DEM exists at 59 m/pix
  (±60° lat) and 118 m/pix elsewhere; polar Artemis sites are mapped to 5 m/pix.
  The remaining frontier is sub-5 m DEMs from stereo imagery (Chandrayaan-2
  OHRC pipelines) over specific sites.
- **Imagery**: essentially 100% of the surface has been photographed. ~99.98%
  has NAC sub-meter pixels at *some* lighting; ~30% has favorable-illumination
  NAC; ~100% has WAC at 100 m/pix. No global mosaic exists at NAC resolution —
  only regional controlled mosaics — because matching seams across 99.98% of
  the Moon at 0.5 m/pix is a much larger problem than capturing the pixels.
- **Practical takeaway for a game/sim**: SLDEM2015 (59 m/pix global) + LROC
  WAC mosaic (100 m/pix global texture) gives you a complete, seamless Moon.
  Drop in PGDA's 5 m polar DEMs + regional NAC mosaics for landing-site
  detail.

## Using this for a walkable game surface

### Tier 1 — full Moon, hike anywhere

**Dataset:** SLDEM2015 (59 m/pix, ±60° lat) + LOLA 118 m polar caps + LROC
WAC 100 m color/morphology mosaic for texture.

- Heightfield collision is the right primitive: a single regular grid of
  Z-values, sampled bilinearly by Jolt's `HeightFieldShape`.
- Whole-Moon at 59 m/pix is **~190k × ~95k samples ≈ 72 GB** as float32.
  Streamable as tiles; not loadable all at once.
- Practical: page in **~10 km × 10 km tiles** (170×170 samples each) around
  the player, LOD farther ones to 472 m/pix / 944 m/pix. ~MB per tile.
- 59 m/pix is **coarse for footstep-scale gameplay** — boulders, small
  craters, rover-scale obstacles are below the sampling limit. Fine for
  driving / flying / orbital views; weak for "walk up to this rock."

### Tier 2 — a single landing site, photorealistic walking

**Dataset:** PGDA 5 m/pix south-pole site DEMs + LROC NAC frames (0.5 m/pix)
at that site, optionally Chandrayaan-2 OHRC stereo for sub-meter DEM.

- A 10 km × 10 km Artemis candidate site at 5 m/pix = **2000 × 2000 = 16 MB**
  heightfield. Trivially fits a level.
- 5 m sampling resolves crater rims and large boulders but **misses
  sub-meter rocks**. For those you'd either (a) procedurally scatter rocks
  using NAC imagery as a density map, or (b) generate a sub-meter DEM from
  OHRC stereo (Chandrayaan-2 pipeline) for the immediate landing area only.
- Texture: NAC 0.5 m/pix for the playable zone, WAC 100 m/pix for the skybox
  / distant terrain.

### Tier 3 — sub-meter, "walk up to this individual rock"

**Dataset:** Chandrayaan-2 OHRC sub-meter DEMs (selected sites only) +
procedural rock-field augmentation calibrated against NAC imagery.

- Only exists for a handful of pre-selected sites (Artemis candidates, CLPS
  landing zones). Not even close to global.
- Below ~1 m, **no real data exists anywhere on the Moon** — you're
  procedurally generating, with NAC images as the ground-truth for
  appearance and rock-size distribution.

### Format & import path

The standard data products are all GeoTIFF / IMG (PDS3/PDS4):

- **Heightmap**: GeoTIFF float32, meters above lunar reference radius
  (1737.4 km). Convert to WF heightfield by sampling on a regular grid;
  Jolt `HeightFieldShape` consumes this directly.
- **Texture**: GeoTIFF uint8, equirectangular or polar stereographic. Project
  onto the heightfield using the same map projection.
- **Tools**: GDAL handles all the projection math (`gdalwarp` to reproject
  polar stereographic → equirectangular, `gdal_translate` to tile).
- **WF-side**: this is a generic terrain/heightfield problem — same on
  Earth DEMs, fictional landscapes, Mars, anywhere. Two paths: (a) ship
  the DEM through Blender as a triangle mesh and reuse the existing
  static-mesh collider (what Tier 2 uses — no new asset type), or (b)
  introduce a generic heightfield asset (`HFLD` IFF chunk?) that streams
  the raw float grid and is backed by Jolt's `HeightFieldShape`. (b) is
  better at scale; (a) is faster for the first level.

### Curvature

The Moon's radius is 1737 km. Over a 10 km × 10 km tile, curvature drops
the corners by ~7 m — significant enough that a *flat* heightfield will
look wrong at the horizon. Either:
- Keep tiles flat-projected and accept horizon weirdness (cheap; fine for
  small play areas), or
- Sample heights into a curved manifold (sphere patch), which Jolt doesn't
  do natively — you'd build a mesh collider per tile from the DEM samples
  laid on the sphere.

### Recommendation

For a first pass, **Tier 2**: pick one Artemis south-pole site, ingest the
PGDA 5 m DEM as a single heightfield (~16 MB), texture with NAC frames at
0.5 m/pix where available and WAC elsewhere. That's a defensible "real
piece of Moon you can walk on" in one level. Tier 1 (global) is a streaming
terrain system, much bigger build. Tier 3 (sub-meter) needs a custom
photogrammetry pipeline and is research-grade.

## Sources

- [LOLA global DEM 118 m (USGS Astropedia)](https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m)
- [SLDEM2015 — LOLA+Kaguya TC merged DEM (PGDA)](https://pgda.gsfc.nasa.gov/products/54)
- [SLDEM2015 paper (Barker et al., Icarus 2016)](https://www.sciencedirect.com/science/article/pii/S0019103515003450)
- [LROC WAC GLD100 global stereo DEM](https://astrogeology.usgs.gov/search/map/moon_lroc_wac_gld100_colorshade_79s79n_118m)
- [LROC WAC global morphology mosaic 100 m](https://astrogeology.usgs.gov/search/map/moon_lro_lroc_wac_global_morphology_mosaic_100m)
- [High-resolution LOLA south pole topography (PGDA)](https://pgda.gsfc.nasa.gov/products/78)
- [South Pole LOLA DEM mosaic (PGDA)](https://pgda.gsfc.nasa.gov/products/81)
- [A New View of the Lunar South Pole from LOLA (Planetary Science Journal)](https://iopscience.iop.org/article/10.3847/PSJ/acf3e1)
- [NCCS high-resolution south pole elevation maps](https://www.nccs.nasa.gov/news-events/nccs-highlights/moon-south-pole)
- [LROC instrument overview](http://lroc.sese.asu.edu/about/objectives)
- [Lunar Reconnaissance Orbiter (Wikipedia)](https://en.wikipedia.org/wiki/Lunar_Reconnaissance_Orbiter)
- [Chandrayaan-2 OHRC sub-meter DEM pipeline (arXiv 2604.01032)](https://arxiv.org/pdf/2604.01032)
- [LPI Lunar South Pole Atlas](https://www.lpi.usra.edu/lunar/lunar-south-pole-atlas/)
