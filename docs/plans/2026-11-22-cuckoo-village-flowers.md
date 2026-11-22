# Cuckoo Village window boxes: trailing petunias and edelweiss

**Status:** proposal for review, 2026‑11‑22. Nothing is in the level yet: the geometry and the renders below are a prototype, and the level build is untouched. Revised 2026‑11‑22: the flowers sit behind a settings toggle, so one APK can be profiled both ways, and a script writes the before-and-after report.

## Context

The cottage window boxes in the Cuckoo Village are two rows of blocks: each box carries seven green posts topped with seven coloured cubes (14 cubes, about 164 triangles), textured from the shared atlas. Close up they read as bricks, not flowers (compare the first picture below). There are 26 boxes: two on the front of each of the 13 cottages.

Will asked for them to be modelled with more polygons, in flat coloured materials instead of textured ones, with a plan showing before and after renderings, budgets, materials and render time. The flowers were chosen in discussion (Will, 2026‑11‑22: "i don't like geraniums", then "Petunias and Edelweiss", then "make 1/3 of the flowerboxes germaniums and edelweiss, so need a new model for germanium after all"). So two kinds of box alternate, two in three petunia and one in three geranium, and every box has edelweiss. The ones I considered and set aside: pansies, marigolds and lavender.

Measured today with [`flowers_prototype.py`](../../wflevels/cuckoo_village_assets/flowers_prototype.py): the cottage mesh `standard_house` is 1,724 triangles, of which 328 are the plants of its two window boxes. The whole village layout is 67,364 triangles, and the Christmas candles add about 3,600, so the level is about 71,000 today.

## Approach

**Geometry.** [`flowers.py`](../../wflevels/cuckoo_village_assets/flowers.py) builds one box of flowers as plain triangles per material, in code, so it is unit-tested without Blender ([`test_cuckoo_village_flowers.py`](../../tests/test_cuckoo_village_flowers.py), 10 tests passing). **One box in three is a geranium box** (boxes 0, 3, 6 and so on: 9 of the 26), the other 17 are petunia boxes, and every box has a soil bed and edelweiss. A box holds:

- a **soil bed**, a four-triangle mound just above the box top;
- **2 edelweiss tufts** nearer the ends, each with narrow silver leaves and two stems ending in a star (both kinds of box);
- on a **petunia box**, 3 mounded petunias along the middle (three round leaves and three blooms each) and 4 trailing petunia stems that arch over the front rim and hang down the front (two leaves and three blooms each);
- on a **geranium box**, 5 upright (zonal) geraniums along the middle (three round leaves, three florets and a bud each) and 2 trailing ivy geranium stems that hang down the front (two leaves and three florets each). The ivy geranium is the hanging flower on Bavarian balconies; the trailing stems give the street camera a hanging mass of colour on both kinds of box.

A **petunia bloom** is a funnel: ten petal triangles round a recessed rim of five lobes, plus five triangles of yellow throat (15 triangles). A **geranium floret** is five petals as a ten-point star cupped towards the viewer, with a four-triangle yellow heart (14 triangles). An **edelweiss head** is a flat star of seven pointed felty bracts (14 triangles) round a five-triangle yellow heart (19 triangles). Petunias rotate through magenta, violet and white; geraniums are mostly red, with pink and white ones among them. Everything is seeded by the box number, so a rebuild gives the same flowers.

**The setting.** A new field, **Detailed flowers** (Off / On, default On), is appended to `CuckooVillageSettings`, a live field like the other six: it shows in the hold-A form on the TV and in the phone's Dream form. On shows the petunias and edelweiss. Off shows today's blocks. It exists so that one APK can be measured both ways: the same build, the same device, the same camera lap, with only this field changed. Whether it stays as a permanent option or is retired once the flowers are accepted is a decision for Will (see Out of scope).

**Build.** In `blender_create_cuckoo_village.py`, after the candles:

1. Take the old plant faces out of the one shared `standard_house` mesh (the 13 cottages share it, so this is one edit), asserting that exactly 328 triangles went, and bake them into a second static actor, **`cottage_flower_blocks`**, one mesh for all 26 boxes, with the village atlas material they have today. With the setting Off the village looks exactly as it does now.
2. For each of the 26 boxes, take its world position, heading and scale from the cottage actor, and place the box's new flowers with `placed()`.
3. Join all 26 into **one static actor, `cottage_flowers`**, with ten flat-coloured material slots. The materials have a Base Color and no texture, which the exporter already writes as a flat colour; the eight thin petal and leaf materials carry `wf_double_sided`, which the engine honours by skipping back-face culling for them.
4. The director script (`forth.py`) reads the field with `property@`, like the six existing ones, and drives two visibility cells every tick: `cottage_flowers` shows when the field is 1 and `cottage_flower_blocks` when it is 0. A hidden actor draws no triangles.

**Why one actor of flowers.** One baked actor costs 10 draw calls for all 26 boxes. One actor per cottage would cost 13 × 10 = 130. Triangles are cheap on this GPU and draw calls are not, so I chose the single actor, which gives up per-cottage culling. If the profiling says that was the wrong call, the fallback is four actors by quarter of the village (40 draw calls).

**Fallback set.** `QUALITY["lean"]` is the same flowers with fewer parts (332 triangles on a petunia box instead of 649, 308 on a geranium box instead of 680: for example 2 mounds of 3 blooms, 2 vines of 2 blooms and 2 tufts of 1 head on a petunia box). It is a switch in code, not a setting. It is used only if the profiling gate fails (see Profiling).

Other files that change with the new field: `cuckoovillagesettings.oas` (+ the regenerated `.oad` and `.ht`), `timeline.py` (`SETTINGS_DEFAULTS` and the two cell numbers, 227 and 228, after the flame cells), the phone's capabilities asset (`scripts/gen-settings-capabilities.py` regenerates it from the `.oad`), and `test_cuckoo_village_settings.py` and `test_cuckoo_village_settings_effect.py` (seven fields instead of six).

### Build flow

```mermaid
flowchart LR
    G["flowers.py<br/>box_flowers(seed, quality)<br/>petunia and geranium boxes<br/>10 materials, triangles"] --> T["test_cuckoo_village_flowers.py<br/>budget, bounds, indices"]
    G --> B["blender_create_cuckoo_village.py"]
    H["standard_house mesh<br/>1,724 to 1,396 triangles"] --> B
    B --> K["actor cottage_flower_blocks<br/>the 328 old triangles x 13<br/>atlas texture, shown when Off"]
    B --> A["actor cottage_flowers<br/>10 flat-colour slots, 8 double-sided<br/>shown when On"]
    S["field Detailed flowers<br/>CuckooVillageSettings"] --> D["director script<br/>two visibility cells per tick"]
    D --> K
    D --> A
    K --> L["cuckoo_village.iff<br/>Clocks bundle and APK"]
    A --> L
    L --> C["cast1: profile, Off then On then Off<br/>same APK"]
    C --> R["flowers-profile-report.py<br/>report.md and chart"]
    R --> Q{{"gate: p50 and p95 within 1.0 ms<br/>60 fps held?"}}
    Q -- yes --> Y["keep full"]
    Q -- no --> N["switch to lean, remeasure"]
```

### Quality modes

```mermaid
stateDiagram-v2
    [*] --> Full: proposal, 649 to 680 triangles a box
    Full --> Lean: profiling gate fails
    Lean --> Trimmed: gate still fails
    Trimmed --> Quarters: gate still fails
    Full --> [*]: gate passes
    Lean --> [*]: gate passes
    Trimmed --> [*]: gate passes
    Quarters --> [*]: gate passes
    note right of Trimmed: drop the edelweiss, then the trailing stems
    note right of Quarters: four actors, one per quarter, culled separately
```

## Budgets

Counted from the code, not estimated (a test enforces the full set at 700 triangles a box and 18,200 in all).

| | Today | Full (proposal) | Lean (fallback) |
|---|---|---|---|
| Triangles in one box | about 164 (14 cubes) | 649 (petunia), 680 (geranium) | 332 (petunia), 308 (geranium) |
| Triangles in all 26 boxes (17 petunia, 9 geranium) | 4,264 | 17,153 | 8,416 |
| Cottage mesh (shared by 13) | 1,724 | 1,396 | 1,396 |
| Whole level, setting On, about | 70,964 | 83,853 (+18.2 %) | 75,116 (+5.9 %) |
| Whole level, setting Off | 70,964 | 70,964 (same blocks, as a separate actor) | 70,964 |
| Draw calls added, On | 0 (shares the house's) | 10 | 10 |
| Actors added | 0 | 2 (flowers and blocks) | 2 |
| Level file, estimated, with the setting | 4.98 MB | about 5.58 MB (+0.60 MB) | about 5.33 MB (+0.35 MB) |
| Level file, estimated, after the setting is retired | 4.98 MB | about 5.45 MB (+0.47 MB) | about 5.2 MB (+0.23 MB) |

The file estimate uses the cost the candles measured: 27.9 bytes a triangle (4,882,432 to 4,982,784 bytes for about 3,600 triangles and 13 actors). The setting keeps both versions in the file, which adds the 4,264 triangles of blocks (about 0.12 MB). It is an estimate until the level is built. The Clocks bundle (8.56 MB) grows by the same amount.

None of these numbers is a frame time; the profiling below is.

## Profiling before and after

The setting makes this a like-for-like measurement: **one APK, one device, only the field changes.**

**Method.** On cast1 (`chromecast-test-01`, the Chromecast HD that is the performance target), with the coordinator's `profile` workflow:

1. Install the one APK, and select the village.
2. Set **Detailed flowers** Off with the `screensaver-setting-set` workflow, and run `profile` with `warmup` 15 s, `runs` 3 and `duration` 225 s. The Journey camera's lap is 225 s, so every run covers one whole lap and the flowers are on screen at their nearest and furthest in each.
3. Set the field On and run the same `profile`.
4. Set it Off again and run the same `profile` a third time, so any drift (heat, background load) shows up as the difference between the two Off sets instead of being credited to the flowers.
5. Run `scripts/flowers-profile-report.py` on the three evidence folders.

Each run records, per the profile job: achieved frames per second, the median, 90th, 95th and 99th percentile frame time, the worst frame, the percentage of missed refreshes, the memory (`meminfo`), the thermal status, and the per-frame present times. About 36 minutes of cast1 in all (3 × 3 runs × 4 minutes).

```mermaid
sequenceDiagram
    participant R as Report script
    participant C as Coordinator
    participant D as cast1
    C->>D: install the APK (once)
    C->>D: setting Detailed flowers = Off
    C->>D: profile, 3 runs x 225 s (A)
    C->>D: setting Detailed flowers = On
    C->>D: profile, 3 runs x 225 s (B)
    C->>D: setting Detailed flowers = Off
    C->>D: profile, 3 runs x 225 s (A again)
    C-->>R: evidence folders A, B, A again
    R->>R: medians, deltas, drift check, gate
    R-->>R: report.md and frame-time chart
```

**The gate.** The flowers pass if all of these hold: the median p50 and the median p95 frame time with the field On are each within **1.0 ms** of the median of the two Off sets; the frames per second with it On stay within 0.5 of the Off sets and at least 59 (the refresh is 59.94 Hz); the missed-refresh percentage rises by no more than 2 points; and the two Off sets agree with each other to within 0.5 ms, otherwise the run is thrown away as drifted. If it fails, step down the ladder in the quality diagram and measure again.

### The report

`scripts/flowers-profile-report.py` (to be written with the build, modelled on `summarise-plant-resolution-comparison.py`) reads the three evidence folders and writes `docs/diagnostics/cuckoo-village-flowers-<date>/report.md`, with a chart, so the difference after implementation is generated, not typed. It contains:

| Section | What it shows |
|---|---|
| Build facts | Triangles, actors and material slots in each state (read from the built level); the level file size now against the size at the commit before the change (`git show`); the APK checksum. |
| Frame times | A table of fps, p50, p95, p99, worst and missed refreshes: each run, the median of each set, and the On minus Off difference with the percentage. |
| Drift | The two Off sets side by side, and the thermal status of each run. |
| Memory | Total PSS (from `meminfo`) in each state. |
| Chart | A histogram of per-frame present times for Off and On over the same axis. |
| Pictures | A device capture in each state from the same camera moment, so the difference is visible next to the numbers. |
| Verdict | PASS or FAIL against the gate, with each condition and its measured value on its own line. |

The report is written once, after the build, from real evidence. It does not exist yet.

## Materials

All ten are flat colours (Base Color only, no texture). "Per piece" is the triangles in one petal set, leaf or stem, averaged where pieces vary; "Pieces per box" is how many of those a box holds, averaged over the 26 boxes (17 petunia, 9 geranium); "Total" is the whole village (26 boxes, full set).

| Material | Colour | Used for | Double-sided | Per piece | Pieces per box | Total |
|---|---|---|---|---|---|---|
| `bloom_red` | #C7120F | Geranium petals | yes | 10 per floret, 4 per bud | 4.4 florets, 1.0 buds | 1,248 |
| `bloom_magenta` | #CC1775 | Petunia petals, and the pink geraniums | yes | 10 per bloom or floret, 4 per bud | 5.4 blooms or florets, 0.3 buds | 1,446 |
| `bloom_violet` | #6E30B2 | Petunia petals | yes | 10 per bloom | 5.0 blooms | 1,290 |
| `bloom_white` | #F5F2EB | Petunia petals, and the white geraniums | yes | 10 per bloom or floret, 4 per bud | 6.2 blooms or florets, 0.3 buds | 1,656 |
| `flower_centre` | #F7CC29 | Petunia throats, geranium hearts, edelweiss hearts | yes | 5 per throat or edelweiss heart, 4 per geranium heart | 17.7 of 5, 7.3 of 4 | 3,061 |
| `edelweiss_felt` | #DBDBC9 | Edelweiss bracts | yes | 14 per head | 4.0 heads | 1,456 |
| `leaf_green` | #2B6E24 | Petunia and geranium leaves | yes | 6 per leaf | 17.7 leaves | 2,760 |
| `leaf_silver` | #809978 | Edelweiss leaves | yes | 4 per leaf | 6.0 leaves | 624 |
| `stem_green` | #174517 | Stems | no | 12.3 on average (8 for a mound or edelweiss stem, 16 for an upright geranium, 18 for a trailing stem) | 11.0 stems | 3,508 |
| `soil` | #331F12 | The soil bed in each box | no | 4 per bed | 1 bed | 104 |

### What one flower costs

A flower is its petals plus its yellow centre; the plant it sits on adds leaves and a stem.

| Piece | Triangles | Made of |
|---|---|---|
| One petunia bloom | 15 | 10 petal + 5 throat |
| One geranium floret | 14 | 10 petal + 4 heart |
| One geranium bud | 4 | a four-sided pyramid |
| One edelweiss head | 19 | 14 bract + 5 heart |
| A mounded petunia plant | 71 | stem 8, three leaves 18, three blooms 45 |
| An upright geranium plant | 80 | stem 16, three leaves 18, three florets 42, one bud 4 |
| A trailing petunia stem | 75 | stem 18, two leaves 12, three blooms 45 |
| A trailing ivy geranium stem | 72 | stem 18, two leaves 12, three florets 42 |
| An edelweiss tuft | 66 | three silver leaves 12, two stems 16, two heads 38 |
| One petunia box | 649 | 3 mounds 213, 4 trailing stems 300, 2 tufts 132, soil bed 4 |
| One geranium box | 680 | 5 upright plants 400, 2 trailing stems 144, 2 tufts 132, soil bed 4 |

The lean set uses the same pieces in smaller numbers.

## Renders, before and after

Cycles on the CPU, 48 samples, denoised, 1280 × 720, in the Blender container, from [`flowers_prototype.py`](../../wflevels/cuckoo_village_assets/flowers_prototype.py). The "before" is the committed `village_assets.blend` cottage; the "after" removes the old plant faces and adds the new flowers, with the same camera and lights. Box 0 (the left box) is a geranium box and box 1 (the right box) a petunia box.

**Close-up of a petunia box** (1.5 m away): this and the next picture are the decision this plan asks you to make.

[![Petunia box, before and after](2026-11-22-cuckoo-village-flowers/compare-closeup.png)](2026-11-22-cuckoo-village-flowers/compare-closeup.png)

**Close-up of a geranium box.**

[![Geranium box, before and after](2026-11-22-cuckoo-village-flowers/compare-geranium.png)](2026-11-22-cuckoo-village-flowers/compare-geranium.png)

**The whole cottage front**, a geranium box on the left and a petunia box on the right.

[![Cottage before and after](2026-11-22-cuckoo-village-flowers/compare-cottage.png)](2026-11-22-cuckoo-village-flowers/compare-cottage.png)

**Street distance**, in native pixels (about what the TV shows from the tower camera). The flowers read as colour, not as petals, which is the reason for the hanging stems: the colour mass is what survives the distance. The two box kinds are distinguishable by colour: mostly red on a geranium box, violet, magenta and white on a petunia box.

[![Street distance before and after](2026-11-22-cuckoo-village-flowers/compare-street.png)](2026-11-22-cuckoo-village-flowers/compare-street.png)

**The lean fallback next to the full set**, both box kinds.

[![Full and lean](2026-11-22-cuckoo-village-flowers/compare-lean.png)](2026-11-22-cuckoo-village-flowers/compare-lean.png)

There is no live mockup page here: the surface is a rendered 3D scene, so the five stills are the mockups.

### Render time

The render times come from one sequential run (before, then after, then lean) while other jobs were loading the machine (load average 18 to 31 on 8 cores, falling during the run), so **wall-clock seconds are not comparable between rows**: the first close-up "before" took 162 s and the same view "after" took 84 s with the same scene complexity. The **CPU seconds** (summed over every render thread) are the fair comparison, because another job on the machine barely changes them.

| View | Before: wall / CPU | After, full: wall / CPU | After, lean: wall / CPU |
|---|---|---|---|
| Close-up, petunia box | 162.2 s / 392 s | 83.5 s / 373 s | 79.3 s / 369 s |
| Close-up, geranium box | 151.8 s / 402 s | 75.1 s / 380 s | 81.5 s / 386 s |
| Cottage | 62.9 s / 293 s | 60.3 s / 296 s | not rendered |
| Street | 43.3 s / 222 s | 44.2 s / 230 s | not rendered |
| Total (the four views) | 420.2 s / 1,309 s | 263.1 s / 1,279 s | not comparable |

On CPU seconds the "after" is 2 % **less** than the "before" (1,279 s against 1,309 s), which is run-to-run noise: Cycles time is set by the samples, the resolution and the lighting, not by 1,329 more triangles on a scene of 1,700. **This is not the on-device cost.** The on-device cost is the profiling above.

## Out of scope

- **Retiring the setting.** Once the flowers are accepted, either keep **Detailed flowers** as a permanent user option (blocks on a slow device), or remove the field and the `cottage_flower_blocks` actor (about 0.12 MB and one more actor). It is Will's call; until then both are in the level. This becomes a TODO item when the plan lands.
- **Seasonal planting.** Pansies in spring, petunias in summer, asters or heather in autumn, fir sprigs with red berries in December, chosen by the date as the candles are. It needs extra meshes and cells and a place in the settings; this plan only makes the summer boxes good.
- **The Bavaria-mode chalet's boxes.** The chalet shares this geometry (the cuckoo-village plan lists flower boxes among its extra meshes). Rebuilding them is a follow-up once the village boxes are accepted.
- **Wind or sway on the trailing stems.** The engine poses actors, not vertices, so a sway needs one actor per stem group and a director word; it is not in this change.
- **A still-camera profile.** The Journey lap covers near and far views. A profile with Camera motion Still at the closest view would give a worst case; add it only if the lap result is close to the gate.
- **Flowers on the Tide Harbour and Aquarium levels.** Not part of this request.

## Verification

1. **The geometry tests pass.** `scripts/in-linux-container.sh python3 -m pytest tests/test_cuckoo_village_flowers.py -q` reports 10 passed. (Green today.)
2. **The prototype reproduces the renders and counts.** `WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background --python wflevels/cuckoo_village_assets/flowers_prototype.py -- /src/build-docker/flowers/render-full full` prints `MESH house tris before 1724 removed 328 after 1396` and `MESH flowers tris 1329` (two boxes: a geranium box of 680 and a petunia box of 649).
3. **The setting exists and is live.** `test_cuckoo_village_settings.py` and `test_cuckoo_village_settings_effect.py` pass with seven fields, and `Detailed flowers` is Off / On, default On, live. The regenerated `.oad` equals what `oas2oad` makes, and the phone's capabilities asset lists the field.
4. **The director follows the field.** `tests/verify_cuckoo_village_forth.py` in the real zForth VM: with the field On the flowers cell is 1 and the blocks cell 0, with it Off the reverse, with it unset (default) On, at noon, dusk, night and dawn on dates in and out of the candle season.
5. **The level builds with both versions.** `bash wflevels/cuckoo_village/build.sh` in the Blender container reports 88 actors (86 today plus `cottage_flowers` and `cottage_flower_blocks`) and the removed-triangle assertion holds (328).
6. **The exported materials are as designed.** `cottage_flowers` has ten slots, none naming a texture, eight with flag 8 set; `cottage_flower_blocks` has the one atlas material.
7. **The size is within the estimate.** `cuckoo_village-standalone.iff` is at most 0.75 MB larger than the 4,982,784 bytes it is today.
8. **The bundle and launcher tests still pass.** `tests/test_clocks_bundle.py`, `test_launcher_parity.py`, `test_audit_level_settings.py`, `test_cuckoo_village_forth.py`, `test_cuckoo_village_candles.py`.
9. **Both states show on cast1.** Build the Clocks APK, install it, and capture a frame near a cottage with the field Off (the blocks, as today) and On (petunias and edelweiss); the candles and window lights still work in both.
10. **The profile, Off then On then Off.** The three `profile` runs described under Profiling, each 3 runs × 225 s on `chromecast-test-01` with the one APK; the three job numbers are recorded here.
11. **The report is generated.** `python3 scripts/flowers-profile-report.py <the three evidence folders>` writes `docs/diagnostics/cuckoo-village-flowers-<date>/report.md` with every section in the table above filled from the evidence, and exits 0 only when the gate passes.
12. **The gate.** The report's verdict is PASS (or, on FAIL, the next step down the quality ladder is built and steps 10 and 11 are repeated).

<!--
When the work lands, this section becomes the permanent record: keep each step as written and paste the raw output under it, then PASS or FAIL.
-->
