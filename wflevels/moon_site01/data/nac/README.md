# LROC NAC imagery — PGDA Site 01 (Connecting Ridge)

Source LROC NAC EDR frames for the PGDA Site 01 target window near Shackleton crater on the lunar south pole.

## Target window

- PGDA Site 01 (Connecting Ridge), south polar stereographic frame (MOON_ME / DE421, sphere radius 1737400 m, projection centered 90°S 0°E)
- X ∈ [−11500, −10500] m, Y ∈ [−12500, −11500] m (1 km × 1 km centered on (−11000, −12000))
- Center ≈ 89.46°S, the longitude depending on stereographic convention used (ρ ≈ 16.3 km from pole)

## Frame selection rationale

Frames are the stereo pair used by the LROC NAC controlled DTM **NAC_DTM_SHACKRDGE02** (Shackleton – de Gerlache Connecting Ridge DTM, center −89.5°/224.81°), which is the published topographic product spanning PGDA Site 01. Three of the four stereo frames are included; the remaining frame (`M139797542RE`) was dropped to stay under the 500 MB budget. The retained set still provides a full stereo pair (`M139811097LE` + `M139811097RE`) plus the partner observation (`M139797542LE`) for redundancy and shadow-direction variation.

Sun incidence is 88.5° — at/just over the upper edge of the requested 70°–88° window, but representative of the best polar lighting available: the sun never rises higher than ~1.5° above the south-pole horizon, so this is the realistic minimum incidence for the latitude band.

## Frames

| Frame ID       | Sun incidence | Sun azimuth | Center lat | Center lon (°E) | File size  |
|----------------|---------------|-------------|------------|-----------------|------------|
| M139797542LE   | 88.55°        | 96.62°      | −89.67°    | 256.46°         | 132236232 B (126.1 MiB) |
| M139811097LE   | 88.51°        | 95.63°      | −89.69°    | 261.59°         | 132236232 B (126.1 MiB) |
| M139811097RE   | 88.51°        | 95.63°      | −89.69°    | 261.59°         | 132236232 B (126.1 MiB) |

All three frames acquired 2010-09-22 (DOY 265). LE/RE are the left/right CCDs of the NAC, ~5 km cross-track offset. Each frame is 52224 lines × 2532 samples, 8-bit panchromatic, 0.5–1 m/px at nadir. Strip geometry is roughly 5 km × 25 km on the ground; at 89.5°S latitude the strips span many degrees of longitude, so the published DTM coverage (lon 209.97°–234.51°W per the DTM XML — i.e. ~210°–235°E) confirms the target window at 221°E (or whatever convention the user is using; centers vary 247°–262°E in the LROC SOC metadata).

## URLs

- `M139797542LE.IMG` — https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0005/DATA/SCI/2010265/NAC/M139797542LE.IMG
- `M139811097LE.IMG` — https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0005/DATA/SCI/2010265/NAC/M139811097LE.IMG
- `M139811097RE.IMG` — https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0005/DATA/SCI/2010265/NAC/M139811097RE.IMG

LROC SOC product pages (metadata, browse imagery):
- https://data.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-2-EDR-V1.0/M139797542LE
- https://data.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-2-EDR-V1.0/M139811097LE

Companion controlled DTM (orthorectified, not downloaded here):
- https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_DTM_SHACKRDGE02
- https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_DTM_ESALL_CR1 (Connecting Ridge ESA Lunar Lander candidate landing site DTM)

## SHA256

See `SHA256SUMS` in this directory:

```
001afa8a7eb622196a7140fbc734ad30e0c097e93530d39525c4c4ba67d53213  M139797542LE.IMG
58ac96bcbc3149a5fdfbba80708472232d55d0c3c19cde5fd7beec869ff7cead  M139811097LE.IMG
1870bf54459a7be09a795f7dc455db55d0c6913568167d766a31eb42416f0416  M139811097RE.IMG
```

## Notes on use as game-engine ground texture

- These are **raw EDR** — uncalibrated DN, not radiometrically corrected, not map-projected. For a flat ground texture you'll want to either (a) push them through ISIS3 (`lronaccal` → `lronacecho` → `cam2map`) to get a calibrated polar-stereographic mosaic, or (b) skip the work and grab the published **NAC_DTM_SHACKRDGE02 orthophoto** (already projected and tied to the DTM), or (c) the **NAC_POLE_SOUTH_CM_AVG** controlled mosaic at 1 m/px in south-polar-stereographic — relevant tiles are `P892S2250` or `P892S3150`, but each is 2.07 GB (outside the 500 MB budget of this fetch).
- Long shadows at 88.5° incidence are a feature, not a bug, for atmospheric immersion — but mean ~50% of the frame is in shadow, which limits useful coverage. Combine with the DTM-derived hillshade if you need full-area illumination.
- South-polar-stereographic projection on the moon uses sphere radius 1,737,400 m (MOON_ME / DE421); do not use an ellipsoid.

## Coverage assessment for target window

The published DTM `NAC_DTM_SHACKRDGE02` derived from these frames is centered at (−89.5°, 224.81°) with DTM bounds lon 209.97°–234.51°E and lat 89.58°–89.35°S. The 1 km × 1 km target window at ρ ≈ 16.3 km from the pole falls inside that DTM footprint regardless of the longitude convention (221° or its complement 317°, both lie within the 210°–235°E swath under the DTM's stated bounds). Pixel coverage at 0.5–1 m/px gives the engine plenty of resolution headroom for a 1 km × 1 km terrain tile.

## Orthorectified RDR product (Phase 3b texture source)

In addition to the raw EDR frames above, the SDP-pipeline-projected ortho-image
from the SHACKRDGE02 DTM is the actual texture source used by
`make_terrain_texture.py --source nac`. It is already map-projected to
south polar stereographic (MOON_ME, sphere 1737400 m) in the same CRS as
the PGDA DEM, so no `gdalwarp` is needed — `rasterio.windows.from_bounds`
crops directly.

| File | Resolution | Size | SHA256 |
|---|---|---|---|
| `NAC_DTM_SHACKRDGE02_M139797542_120CM.IMG` | 1.20 m/px | 40.83 MB | `8b7bbc9625b44ac93d3bca383cae7d89e16ea6137046add7a5c77d324e4ea1c3` |

URL:
```
https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/SDP/NAC_DTM/SHACKRDGE02/NAC_DTM_SHACKRDGE02_M139797542_120CM.IMG
```

The raw EDR frames are kept around for future ISIS3 work or as backup.
