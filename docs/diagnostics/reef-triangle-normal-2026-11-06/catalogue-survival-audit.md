# Audit: catalogue pages 1–18

The descriptions below are transcribed from the existing catalogue, not judgments that the changes improved appearance. All 18 were described as making detail survive export; each is a candidate for restoration after the loader correction and removal of the blanket filter are verified. No geometry was changed by this audit.

| Page | Catalogue entry | Recorded reason | Current source to investigate |
|---:|---|---|---|
| 1 | Leather coral | Thicker polyps retained end caps | `reef/corals.py` `leather_coral` |
| 2 | Flowerpot coral | Thicker crown tentacles retained end caps | `reef/corals.py` `flowerpot` |
| 3 | Giant clam shell ribs | Thicker ribs survived export | `reef/life.py` `_clam` |
| 4 | Mushroom coral | Thicker ridges retained faces | `reef/life.py` `_mushroom_coral` |
| 5 | Cup coral | Thicker polyp tentacles retained faces | `reef/life.py` `_cup` |
| 6 | Zoanthids | Thicker tentacle tips retained faces | `reef/life.py` `_zoanthids` |
| 7 | Giant clam mantle | Reshaped markings retained faces | `reef/life.py` `_clam` |
| 8 | Boxfish markings | Reshaped small markings retained faces | `reef/fishes.py` `boxfish` and `reef/life.py` `_juvenile_boxfish` |
| 9 | Humbug markings | Reshaped small markings retained faces | `reef/fishes.py` `humbug` and `reef/life.py` `_humbug` |
| 10 | Hermit crab | Adjusted body, shell lip and legs retained faces | `reef/invertebrates.py` `hermit_crab` |
| 11 | Guard crab claws | Adjusted proportions retained faces | `reef/invertebrates.py` `guard_crab` |
| 12 | Shrimp eyes | Replaced tiny subdivided eyes | `reef/invertebrates.py` `banded_shrimp` |
| 13 | Guard crab eyes | Replaced tiny subdivided eyes | `reef/invertebrates.py` `guard_crab` |
| 14 | Sea fan | Thicker cross-branches retained end caps | `reef/life.py` `_sea_fan` |
| 15 | Worm crown | Extended radioles retained triangles | `reef/life.py` `_worm_crowns` |
| 16 | Feather star | Thicker pinnules retained end caps | `reef/life.py` `_feather_star` |
| 17 | Shrimp legs and antennae | Thicker details preserved more faces | `reef/invertebrates.py` `banded_shrimp` |
| 18 | Guard crab legs and pincers | Thicker details preserved more faces | `reef/invertebrates.py` `guard_crab` |

Paths are relative to `wflevels/aquarium_thai_reef/`. Source mapping is a starting point, not proof of which exact parameters each individual page changed. Most model, catalogue and rig changes landed together in commit `2e8c25c0`, so blindly reverting entire files to its parent would also discard independent improvements and later rig integration. Compare the original source, the page images and current source feature by feature. Check deformation bindings for affected animated parts and export the actual mesh with true degeneracies reported. Record each restoration with before/after renders and update the catalogue immediately.

Page 1 restoration: the retained catalogue source snapshots record the leather polyps changing from radius 0.010 to 0.013 for export survival; the current source has been returned to 0.010 while keeping the later deflation rig. Page 49 compares the source meshes and page 50 shows both in-game styles. Both pinned production builds completed and the reef test suite passed (34 tests). Both styles retained 240 leather triangles below the old filter and both rig curves. Their smallest exported face area was approximately 0.0000656, above the original release loader's theoretical area threshold of 0.0000305; the baseline and corrected release loaders both produced unit normals for this particular restored mesh. The old exporter cutoff was therefore more conservative than necessary for these faces. Pixel close-up captures show the slim polyps, although the player and neighboring coral overlap portions of the view.

The cutoff was also removed from the generator. It now writes `triangle-diagnostics.json`, recording object and face indices for small valid, truly zero-area and quantization-degenerate triangles. In the pinned output, the 240 leather triangles and the previously identified reef and fan faces survived; no exported face was quantization-degenerate. The largest exported object has 15,552 vertices in realistic and 29,668 in anime, within the signed 16-bit face-index limit. For the five affected exported objects in each style, [actual-loader checks](restored-loader-normals.csv) found 26 non-unit normals in the old realistic loader and five in the old anime loader, all on reef rock meshes; the corrected loader produced unit normals for every tested face. This is a correctness check, not a benchmark of extra geometry.

The full Aquarium release APK with these rebuilt levels was assembled and frozen as `/tmp/reef-leather-restored-full.apk` (SHA-256 `19494386dde336f7ebcacd778f875815e60d2809b67d1b0312b9c3446ea32174`). Its packed CD matches the rebuilt menu bundle, and its arm64 and armeabi-v7a engine libraries match the previously profiled candidate. Temporary review APKs for both styles were built from that release. Pixel recording jobs J‑1bf53ab515de (realistic) and J‑72adf85f4436 (anime) show each scene staying open in its wide view. Camera-only close-up jobs J‑9c7a31d43692 (realistic) and J‑d6ca4a4f3e72 (anime) captured the production mesh and textures with a diagnostic camera and player placement. The full menu APK was reinstalled and launcher-verified on the Pixel by J‑bb9dc46aa83c. The Lenovo was unavailable and has not received this build.

## Scratch export without the cutoff

On 2026‑11‑07, a scratch copy of the current generator retained rather than deleted the under-threshold faces; the real generator and checked-in assets were not modified. Host Blender 5.0.1 generated both styles with rock remeshing and lighting bake. This is a diagnostic, not a pinned-container production build or an in-game review. [make-unfiltered-probe.py](make-unfiltered-probe.py) creates the scratch generator; [audit-exported-faces.py](audit-exported-faces.py) counts actual exported triangles using exact integer cross products on 16.16 positions.

| Export | Current checked-in faces / quantized-degenerate / small nonzero | Scratch unfiltered faces / quantized-degenerate / small nonzero |
|---|---:|---:|
| Realistic | 89,684 / 0 / 0 | 89,740 / 0 / 56 |
| Anime | 96,676 / 0 / 0 | 96,696 / 0 / 20 |

The realistic scratch export retained 19 small nonzero faces in `reef_left`, 14 in `reef_right`, 22 in `reef_arch` and one in `seafan`. The anime retained 7, 7, 5 and one respectively. Before export, Blender reported eight exactly zero-area clam faces per style; the resulting MODLs contain no quantized-degenerate faces. This does not by itself identify the exporter step that handled those eight faces. See the per-object CSVs alongside this report. The counts describe geometry survival only; they are not performance or memory comparisons. Small-detail geometry already thickened in the 18 catalogue changes still needs the separate restoration audit above.
