# Betta — the art of flowing fins

Finished A3 portrait poster: [HTML](poster.html), [PDF](betta-history-and-biomechanics-a3.pdf), [PNG](poster.png). Includes original side and oblique 3D fish renders, four published locality labels on a geographic map, history, habitat, paternal care and fin-motion schematics.

## Fish render and its limits

The current images use the **actual 4,076-triangle runtime geometry** from `wflevels/aquarium_betta/detailed_model.py`: body plus seven closed opaque fin meshes. The scene and native-equivalent pose settings are retained in [runtime-betta.blend](assets/runtime-betta.blend) and [runtime-model-manifest.json](assets/runtime-model-manifest.json). Studio smooth lighting differs from the engine's prelit fin materials; neither uses translucent membranes.

The original 40,060-triangle poster study remains archived as [betta-study.blend](assets/betta-study.blend), [OBJ](assets/betta-study.obj) and [model manifest](assets/model-manifest.json). It is not the installed fish. The motion diagrams illustrate game design; they are not measured betta kinematics. The fish is halfmoon-inspired, without claiming exhibition-standard classification.

## Sources and geographic precision

- [Kwon et al. (2022), Science Advances 8:eabm4950](https://api.repository.cam.ac.uk/server/api/core/bitstreams/bda0af65-2fcf-4502-ac6f-6f47c1102462/content): reported history of selective breeding, ornamental origins and Fig. 1’s four wild-population names. The historical 14th-century report is not a proven exact domestication date. Ornamental forms are primarily derived from *B. splendens* with genetic contributions from related species.
- [Sermwatanakul (2019), SEAFDEC](https://repository.seafdec.org/bitstream/handle/20.500.12066/5516/Siamese-fighting-fish.pdf): 5 February 2019 national designation; habitat and labyrinth air breathing.
- [Panijpan et al. (2017), Thai Natural History Museum Journal 11(1)](https://journal.nsm.or.th/sites/default/files/2023-10/THNHMJ01-2017.compressed.pdf): paternal nest care and the distinction between bubble-nesting and mouthbrooding species.
- [Flammang et al. (2013), J. Morphology](https://pubmed.ncbi.nlm.nih.gov/23720195/): general fin-ray flexibility studied in **bluegill**, not measured betta fin-wave settings.

The geographic basemap uses Natural Earth 1:110m data, shared with the adjacent arowana poster’s [downloaded GeoJSON](../asian-arowana-poster/assets/countries.geojson). Natural Earth’s [public-domain terms](https://www.naturalearthdata.com/about/terms-of-use/) apply. The map is equirectangular and restricted to mainland context; country outlines are not species-range shading.

[map-localities.json](map-localities.json) records the four published wild-population labels: Chiang Mai, Kanchanaburi, Bang Phlat and Phetchaburi. Representative centres are manually placed, rounded to 0.1 degree, and compared with the primary figure’s regional arrangement. They are **not the paper’s sampling coordinates**, not a complete distribution, and not confirmation that each population remains extant in 2026. The long-fin ornamental hero does not portray the wild phenotype at those points.

## Rebuild

Run `blender --background --python wflevels/aquarium_betta/render_detailed.py` for the runtime views, editable scene and pose manifest. Cycles CPU, 24 samples, 3200 × 1900 pixels. The script reads the runtime geometry and reproduces its root-weighted native fin deformation, leaving game files unchanged. `render_fish.py` reproduces only the archived studio study.

Then run `python3 docs/reference/betta-history-and-biomechanics-poster/make_poster.py`. It embeds both PNGs, writes the map and native diagrams and produces offline `poster.html`. Print with Chrome using a fresh profile, no PDF headers/footers and the CSS A3 size. Generate `poster.png` with `pdftoppm -r 150 -png -singlefile betta-history-and-biomechanics-a3.pdf poster`.

- [x] Two genuine Blender model renders included; editable assets and triangle counts retained.
- [x] History, habitat, locality evidence and motion provenance cited.
- [x] Runtime geometry and studio lighting difference disclosed on the poster.
- [x] Final regenerated PDF/page geometry and browser overflow checks complete: one A3 page, embedded fonts, loaded images and no text/page overflow.

Related [betta implementation plan](../../plans/2026-10-02-betta-poster-and-flowing-fins.md).
