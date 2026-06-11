# Moon Surface Asset — 3D Model Source Survey

**Date:** 2026-06-03  
**Author:** Claude (research)  
**Context:** Before building Artemis lunar surface assets from primitives for `wflevels/moon_site01/`, searched for existing downloadable 3D models from NASA, contractors, and community sites. None were used (all are either unreleased, behind purchase, or wrong vehicle). Recorded here so we don't repeat the search and can purchase when ready.

---

## Conclusion

No official NASA or contractor model exists for any of the six priority assets. All six are being built from primitives in `blender_create_moon.py`. Community/commercial paid models exist for the Lunar Cruiser and Blue Moon MK1 and are deferred for later purchase.

---

## Per-Asset Findings

### 1. Moon RACER (Intuitive Machines LTV)

**Official model:** None. NASA LTV page and gallery contain photos/renders only. Intuitive Machines website has no model downloads.

**Community:**
- Printables.com — "NASA Artemis Lunar Terrain Vehicle (Moon buggy) V1B104"
  - URL: https://www.printables.com/model/1021319-nasa-artemis-lunar-terrain-vehicle-moon-buggy-v1b1
  - Also: https://makerworld.com/en/models/770027-nasa-artemis-lunar-terrain-vehicle-moon-buggy-v1
  - Format: 3MF (print-optimized). License: Printables standard (non-commercial).
  - Detail: Low-poly print file. Based on generic early concept art, **not** the Moon RACER / Intuitive Machines design specifically.

**Verdict:** No usable model. Build from primitives.

---

### 2. LunaGrid VSAT Tower (Astrobotic)

**Official model:** None. Astrobotic site has press photos and PDFs only.

**Community:** Nothing found on any platform (Sketchfab, GrabCAD, CGTrader, Printables).

**Verdict:** No model of any kind. Build from primitives.

---

### 3. Toyota / JAXA Lunar Cruiser

**Official model:** None. Toyota's official page (global.toyota/en/mobility/technology/lunarcruiser/) has no downloads. JAXA has no model. A previously-public Sketchfab model by "Space Explorers" has been **deleted** (https://sketchfab.com/3d-models/jaxatoyota-lunar-cruiser-67e8ce14be394d2f8e6809dd8793f64a).

**Community / commercial (all by same artist — Sergey Koznov, cross-listed):**

| Source | URL | Formats | Price | License | Detail |
|--------|-----|---------|-------|---------|--------|
| CGTrader (8K textured, animated, rigged) | https://www.cgtrader.com/3d-models/vehicle/sci-fi-vehicle/toyota-lunar-cruiser-jaxa-moon-rover-3d | FBX, BLEND, GLTF | paid | Royalty-free | 8K textures |
| CGTrader (rigged + textures) | https://www.cgtrader.com/3d-models/vehicle/sci-fi-vehicle/toyota-lunar-cruiser-jaxa-moon-rover-3d-textures | FBX, BLEND, GLTF | paid | Royalty-free | 4K textures |
| ArtStation (no textures) | https://www.artstation.com/marketplace/p/ed0wX/toyota-lunar-cruiser-jaxa-moon-rover-3d-model-source-files | FBX, SPP | ~$45 | Commercial use | high detail |
| ArtStation (with textures) | https://www.artstation.com/marketplace/p/6NM37/toyota-lunar-cruiser-jaxa-moon-rover-3d-model-with-textures-source-files | FBX, SPP, HDRI | paid | Commercial use | high detail |
| Superhive / Blender Market | https://superhivemarket.com/products/toyota-lunar-cruiser-jaxa-moon-rover | FBX, BLEND | paid | per-site license | — |

**If/when purchasing:** CGTrader BLEND is the best format (direct Blender import; textures stripped → `_make_mat()` flat colours; Decimate to < 8k faces).

**Verdict:** Build from primitives for now. Purchase CGTrader BLEND when ready to upgrade.

---

### 4. Blue Origin Blue Moon Mark 1

**Official model:** None. Blue Origin press page has photos only. NASA gallery page (https://www.nasa.gov/gallery/blue-origin-blue-moon-mark-1/) has 4 images, no geometry files.

**Community / commercial:**

| Source | URL | Formats | Price | License | Detail |
|--------|-----|---------|-------|---------|--------|
| Sketchfab — @Soleg | https://sketchfab.com/3d-models/blue-moon-mk1-lunar-lander-7bb39ebee1904d87b5379d16d1a9c772 | varies | unknown | **not stated** — contact soleg.3d@gmail.com | 212k tris / 106k verts — medium-high |
| CGTrader MK1 | https://www.cgtrader.com/3d-models/space/spaceship/blue-moon-mk1-lunar-lander | OBJ, FBX, BLEND | paid | Royalty-free | 359k verts |
| CGTrader HLS (MK1 + Cislunar Transporter) | https://www.cgtrader.com/3d-models/space/spaceship/blue-moon-lunar-lander | OBJ, FBX, BLEND, PNG | paid | Royalty-free | 1.7M verts — very high |
| CGTrader Mark II (different vehicle — **free**) | https://www.cgtrader.com/free-3d-models/space/spaceship/blue-origin-blue-moon-mark-ii-lander | Maya .ma, Unreal | free | Royalty-free | rigged/animated |
| TurboSquid MK1 | https://www.turbosquid.com/3d-models/blue-moon-mk1-lunar-lnader-model-2150923 | — | ~$35 | Royalty-free | — |

**Note:** The CGTrader Mark II model is free but is the **Mark 2** (different vehicle). The MK1-specific options are all paid or license-unclear (Sketchfab @Soleg).

**If/when purchasing:** Check Sketchfab @Soleg download permission first (212k tris, free if downloadable). Fallback: CGTrader BLEND MK1 (359k verts, decimate to < 8k, strip textures).

**Verdict:** Build from primitives for now. Sketchfab @Soleg is the first thing to check when upgrading.

---

### 5. Foundation Surface Habitat (FSH)

**Official model:** None. Design is still in competition/concept phase as of 2025–2026; NASA has released only artist concept renders (NASA *Artemis Plan*, 2020).

**Community:** Nothing found. No model on Sketchfab, GrabCAD, or any commercial site specifically matching the FSH spec (3-storey hybrid metallic base + inflatable upper). A generic fan "lunar base" on Sketchfab (https://sketchfab.com/3d-models/lunar-base-a488c1c17eb149f5bae3121f16e24358, free, CC, by popo57) is unrelated.

**Verdict:** Build from primitives. May never have a public model until the design is awarded and the contractor publishes.

---

### 6. Fission Surface Power (FSP) Reactor

**Official model:** None. NASA Glenn Research Center has released only PDFs, presentations, and concept renders via NTRS. No geometry files.

**Community:**
- CGTrader — Kilopower Reactor: https://www.cgtrader.com/3d-models/space/spaceship/kilopower-reactor (paid, not confirmed available)
- 3D Warehouse — Kilopower: https://3dwarehouse.sketchup.com/model/b0a05df3-ecc0-489f-ad5f-d4c071513dfd/Kilopower-Reactor (free SKP, SketchUp ToS)

**Note:** Both are for the **Kilopower** (1–10 kW KRUSTY demo unit, ca. 2018). The Artemis-era **FSP** (40 kWe deployable system with Stirling engines on boom + radiator array) is a different design and has no public model.

**Verdict:** Build from primitives. The Kilopower SketchUp model is the wrong vehicle and wrong era.

---

## Sources Checked

- NASA 3D Resources: https://science.nasa.gov/3d-resources/
- NASA 3D Resources GitHub: https://github.com/nasa/NASA-3D-Resources/tree/master/3D%20Models
- NASA Sketchfab official account (44 models): https://sketchfab.com/NASA
- Sketchfab tags: lunar-rover, artemis, lunar-habitat, lunar-lander
- GrabCAD lunar tag: https://grabcad.com/library/tag/lunar
- CGTrader space/spaceship + vehicle categories
- ArtStation Marketplace
- Printables.com / MakerWorld
- TurboSquid
- Intuitive Machines: https://www.intuitivemachines.com
- Astrobotic: https://www.astrobotic.com
- Toyota Lunar Cruiser: https://global.toyota/en/mobility/technology/lunarcruiser/
- Blue Origin Blue Moon: https://www.blueorigin.com/blue-moon/mark-1
- NASA LTV page: https://www.nasa.gov/suits-and-rovers/lunar-terrain-vehicle/
- NASA FSP page: https://www.nasa.gov/space-technology-mission-directorate/tdm/fission-surface-power/
