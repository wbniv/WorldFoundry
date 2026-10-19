# moon_site01 — source data

External lunar datasets used to build the Moon Site 01 (Connecting Ridge,
near Shackleton crater) walkable level. Site 01 is an Artemis III crewed
landing candidate region and the target of Blue Origin's uncrewed Blue
Moon MK1 Endurance lander (fall 2026).

See [docs/plans/2026-05-30-moon-surface-tier2.md](../../../docs/plans/2026-05-30-moon-surface-tier2.md)
and [docs/investigations/2026-05-30-moon-mapping-data.md](../../../docs/investigations/2026-05-30-moon-mapping-data.md).

## Files

| File | Source | Size | SHA256 |
|---|---|---|---|
| Site01_final_adj_5mpp_surf.tif | [PGDA product 78](https://pgda.gsfc.nasa.gov/products/78) | 39 MB | `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e` |

Direct URL:
```
https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_final_adj_5mpp_surf.tif
```

## Site01_final_adj_5mpp_surf.tif

- **Format:** GeoTIFF, single float32 band, NaN nodata.
- **Resolution:** 5 m/pix.
- **Extent:** 3200 × 3200 pixels = 16 km × 16 km.
- **CRS:** South polar stereographic (origin at lunar South Pole),
  spheroid radius 1 737 400 m, units = metres.
- **Bounds (polar stereographic, metres):** X ∈ [−19000, −3000],
  Y ∈ [−20000, −4000]. Centre of tile ≈ (−11000, −12000) m → ≈ 89.5° S,
  227° E in lat/lon, the Connecting Ridge between Shackleton and de
  Gerlache.
- **Elevation values:** metres above the lunar reference radius
  (1737.4 km), range −523.18 to +1959.50 m, mean +1139.06 m. The high
  ground around Shackleton is at ~+1950 m; the lows are inside crater
  floors.

## Reference frame

PGDA documents the DEM in the MOON_ME body-fixed mean-Earth frame with
ephemeris DE421. For game purposes we only need the local X/Y/Z metres;
the frame definition matters if we ever fuse other lunar datasets.

## Verification

```
python3 -c "import rasterio; \
    src = rasterio.open('Site01_final_adj_5mpp_surf.tif'); \
    print(src.bounds, src.res, src.crs)"
```
