# Aquarium: clumped plant growth, gentle water motion and an A3 poster

**Status:** researched plan and poster draft; the revised growth layout and sway are not implemented. This supersedes the row-based composition in the [first dense planting pass](2026-10-03-aquarium-dense-planted-tank.md), while retaining its geometry and profiling evidence as a reference.

Replace obvious rows with **connected, irregular patches of growth**. Keep the tank mostly full: overlapping clumps should cover roughly 75–85% of the submerged interior in the whole-tank view, with local gaps and a small, winding substrate route for the sea urchin. Add subtle, coherent water-driven bending with anchored roots. Make an **A3 portrait poster**, split into saltwater on the left and freshwater on the right; reserve the **bottom 25% of the page** for diagrams and explanations of clumping and branching.

## Poster draft and review

[Open the A3 PDF](2026-10-03-aquatic-plant-clumps-and-poster/aquatic-plants-a3.pdf) · [Vector SVG](2026-10-03-aquatic-plant-clumps-and-poster/aquatic-plants-a3.svg) · [Browser review](2026-10-03-aquatic-plant-clumps-and-poster/index.html).

![A3 poster draft](2026-10-03-aquatic-plant-clumps-and-poster/aquatic-plants-a3-preview.png)

The page is **297 × 420 mm**, portrait. Its upper 75% has equal left/right subject areas; the lower band starts at exactly **315 mm**. Use original botanical schematics rather than photos copied from sources. Illustrations show growth forms, not diagnostic identification plates or literal scale. Source identifiers on the poster map to the linked bibliography below and in the browser review. [Compact Forth snippets](2026-10-03-aquatic-plant-clumps-and-poster/plant-helpers.fth) are [checked in the actual zForth VM](2026-10-03-aquatic-plant-clumps-and-poster/forth-verification.json) (nine arithmetic/boundary cases with balanced stacks); they are not complete botanical simulations or existing plant-deformation APIs.

Print the PDF at **actual size / 100% on A3 portrait**, without additional printer margins or fit-to-page scaling. The SVG remains the editable vector master.

## What the research supports

**Marine seagrasses and seaweeds are different growth systems.** Seagrasses are flowering plants with roots and rhizomes; seaweeds are algae, commonly attached by holdfasts. The left panel includes eelgrass, paddle-leaf seagrass and a branching brown-algal form, with habitat distinctions. Sea anemones are animals and do not belong in the plant list. [NOAA seagrass overview](https://floridakeys.noaa.gov/plants/seagrass.html), [NOAA restoration guide](https://repository.library.noaa.gov/view/noaa/70998/noaa_70998_DS1.pdf).

**Clumps emerge from lineage and spacing.** A multi-species seagrass study found substantial variation in rhizome extension, internode spacing, and branching rate/angle. Short spacers and repeated branching can produce compact occupation; longer spacers spread shoots more widely. Do not assign one universal branch angle or spacing to every species. Research models explicitly generate connected rhizome structures, including density-dependent rules. [Marbà & Duarte: rhizome elongation and clonal growth](https://pure.knaw.nl/portal/en/publications/rhizome-elongation-and-seagrass-clonal-growth), [seagrass space occupation study](https://www.nature.com/articles/s43247-024-01758-0), [L-system seagrass model](https://pmc.ncbi.nlm.nih.gov/articles/PMC3189841/).

**Freshwater runner systems also connect neighbouring shoots.** Experiments on *Vallisneria spiralis* describe stolon-linked ramets and changes in spacer length and branching angle under sediment stress. This supports modelling local connected expansion rather than placing independent plants on a grid. [Vallisneria clonal architecture experiment](https://www.sciencedirect.com/science/article/abs/pii/S0304377009000771), [clonal integration experiment](https://www.sciencedirect.com/science/article/abs/pii/S0304377006001227).

**Regional plants for the fish we have made:** wild *Betta splendens* was observed among dense emergent vegetation near Thai rice-field margins; that habitat should not be reduced to an underwater garden of ornamental stems. *Cryptocoryne cordata* has a Southeast Asian range including Thailand and Sumatra, but regional overlap is not proof that a particular plant occurs with a particular fish at a particular site. *Vallisneria spiralis* is documented in Thailand, and *Limnophila sessiliflora* has finely divided submerged leaves in whorls. These are useful habitat-informed shape references, with their provenance stated accurately. [Wild betta habitat study](https://doi.org/10.1111/j.1095-8649.2001.tb02288.x), [Kew: C. cordata distribution](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:86676-1), [Kew: V. spiralis distribution](https://powo.science.kew.org/taxon/431996-1), [University of Florida: L. sessiliflora](https://plant-directory.ifas.ufl.edu/plant-directory/limnophila-sessiliflora/).

*Cryptocoryne cordata* descriptions include slender runners and variable leaves; this is a direct botanical basis for irregular daughter rosettes. Prefer the descriptive flora over an inconsistent aggregated web description. [Wong's Araceae of peat-swamp forests, pp. 59–60](https://www.aroid.org/gallery/wong/Araceae%20of%20Peat%20Swamp%20Forests%20-%20%5BBiodiversity%20of%20Tropical%20Peat%20Swamp%20Forests%20of%20Sarawak%2035-86%5D%20Wong%202016.pdf).

The tiger-barb panel emphasizes **Sumatran freshwater**, rather than claiming Thai betta and tiger barbs share one habitat. Published native-range accounts conflict and older records include congeners; the poster therefore avoids a precise unsupported plant/fish co-occurrence claim. Further fish levels can receive their own geographically matched flora later. [US Fish & Wildlife Service tiger-barb assessment](https://www.fws.gov/sites/default/files/documents/Ecological-Risk-Screening-Summary-Tiger-Barb.pdf).

**Branching seaweed is algorithmically interesting.** Research has modelled multiple seaweeds with L-systems. *Fucus vesiculosus* is a temperate brown alga with repeated dichotomous branching, not a tropical reef plant. Show a simple two-daughter tip grammar as a schematic, then add unequal growth, missed branches and species-specific attachment/shape. Do not present one grammar as the biology of every seaweed. [Corbit & Garbary: seaweed L-systems](https://doi.org/10.1016/0097-8493(93)90055-E), [University of Turku field-research thesis](https://www.utupub.fi/server/api/core/bitstreams/39593dae-44c6-4535-85e2-d398204c85a7/content).

**Gentle water motion should bend the plants, not move their roots.** Flexible vegetation reconfigures with flow, and neighbouring stems experience a shared flow field. Our proposed low-amplitude oscillation is a visual approximation, not a fluid simulation or measured current. [Flexible aquatic vegetation motion model](https://doi.org/10.1016/j.coastaleng.2019.04.009), [ecological biomechanics review](https://academic.oup.com/jxb/article/73/4/1104/6535216).

## Clumping and branching design

![Root networks and patch boundaries](2026-10-03-aquatic-plant-clumps-and-poster/clumping-diagram.svg)

Start from around **12–18 founder patches**, with irregular sizes and outlines. Allocate most plants to a few substantial colonies and fewer to small satellite patches. Grow daughter plants from existing parent nodes using species-specific step lengths and correlated heading changes; avoid random jitter of the old rows. Stop or divert growth at tank margins, the crawl route and excessive local crowding. For a fast first version, use clustered sampling around founders plus a spacing test; retain parent/child edges so the layout can later use true rhizome/stolon walks.

Correlate species, age, height and colour within each patch, then vary them among individuals. Younger daughters tend to occupy expanding edges in the simplified authored model. Blend adjoining patches and create local pockets rather than dividing the scene into eight rectangular botanical zones. **Render chunks are independent of biological clumps:** partition the finished geometry for mesh limits, but do not let chunk boundaries determine planting positions.

For branch structure, use bounded tip growth: extend a parent axis; optionally fork or form a side shoot; reduce daughter segment length/radius gradually; vary branching angles and node spacing; terminate below the minimum useful segment size. Keep leaf arrangement appropriate to the chosen form—basal rosette, ribbon tuft, paired leaves, or whorls. Preserve the curved leaf meshes from the dense pass where they fit the selected form.

![Proposed clumped tank, replacing rows](2026-10-03-aquatic-plant-clumps-and-poster/tank-clumps-mockup.svg)

This is a concept mockup, not an engine capture. The dense detailed pass remains the measurement reference. The present level contains a sea urchin alongside generic freshwater-style foliage; this is an established authored scene, not a validated freshwater biotope. The poster keeps marine and freshwater examples separate. Choosing a scientifically marine flora for the urchin tank is a separate content decision, not a silent change to the current cast.

## Water motion and Forth

![Shared flow and root-pinned bending](2026-10-03-aquatic-plant-clumps-and-poster/sway-diagram.svg)

Use a slow shared oscillation with a small secondary component. Initial **authored** tuning: a 5–9 second primary period, tall-tip displacement around 1–3% of plant height, much less for short carpet growth, and modest phase differences across space. Apply continuous interpolation and a root-to-tip weight such as `w²`. Pin root vertices exactly; retain each stem's base, material assignments and leaf shape. Neighbours should sway broadly together rather than perform independent metronomic dances. Clamp resumed-frame time and reinitialize safely after pauses.

The simple arithmetic fits Forth well:

```forth
: tip-weight ( height-fraction -- weight ) 0 max 1 min dup * ;
: cluster-j ( uniform-a uniform-b -- centred-offset ) + 1 - ;
: fork-angle ( heading signed-side -- daughter-heading ) .08 * + ;
: leaf-turn ( leaf-index leaf-count -- turns ) / ;
: ease ( current target dt -- next )
  0 max .8 * 1 min >r over - r> * + ;
```

The examples use cycles/turns where appropriate. `.08` turns is a schematic branching parameter, not a measured universal angle. `cluster-j` needs independent uniform inputs supplied by a deterministic generator; it creates a centre-heavy triangular distribution but is not by itself a full clumping model. `leaf-turn` describes a radial rosette before authored angular/length variation. `ease` is a simple stable interpolation rule, not a physical spring. The poster prints the smallest helpers; the accompanying Forth file contains comments and numeric checks.

Generate the growth network and meshes at build time. At runtime, let Forth compute shared phase, amplitude and a handful of coefficients for the mesh chunks. Prefer a small native deformation operation over interpreting a loop across ~38,000 vertices in Forth. Inspect the existing fin/fish deformation paths for reusable rest-vertex storage and packed weights; **there is currently no verified plant-sway syscall to print as working code**. Do not rotate an entire merged chunk around the world origin, lift roots or allocate a controller for each plant. Smooth whole-mesh deformation should leave collisions and the urchin controller unchanged.

## Implementation and evidence

1. Finish and archive the current baseline/density/detailed profiling, clearly labelling its row-based layout. Preserve the 384-plant, 66,048-triangle reference and valid native/device captures.
2. Implement clumped placement and form-specific branching, static first. Keep approximately the existing population/geometry budget so layout cost can be separated from a new detail increase. Review both cameras; verify local gaps, true irregular clump boundaries and anchored bases.
3. Add low-amplitude root-pinned sway with a shared water field. Compare static clumps against swaying clumps on Chromecast, with identical native libraries, plant locations, cameras and input traces. Record actor/script time, deformation time, render time, presented pacing, memory and deltas against the archived dense reference.
4. Verify the sea urchin remains controllable and locally visible, selector/back behaviour still works, and the other seven tank payloads are unchanged. Restore the normal menu APK after profiling. Regenerate the poster only when corrections or better verified botanical references justify it.

| Version | Layout | Motion | Measurement role |
|---|---|---|---|
| Original sparse tank | 57 plants / three groups | Static | Historical baseline |
| First dense detailed pass | 384 plants / eight groups / 66,048 triangles | Static | Row-based cost reference |
| Clumped growth | Founder colonies + connected daughters | Static | Isolate layout/branching change |
| Clumps + gentle water | Same colonies and meshes | Root-pinned shared sway | Isolate motion cost |

Acceptance: no obvious repeated rows, a tank mostly filled by overlapping colonies, readable botanical forms, subtle coherent bending with completely fixed roots, usable wide/close views, and measured rather than guessed performance. The A3 PDF must be one page at the correct dimensions, with the requested left/right division and bottom-quarter pattern band, readable text and source links.

## Poster bibliography

- **S1:** [NOAA: seagrass meadows and rhizomes](https://floridakeys.noaa.gov/plants/seagrass.html).
- **S2:** [Kew: Halophila ovalis morphology](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:431761-1/general-information).
- **S3:** [University of Turku: Fucus tip growth and dichotomous branching](https://www.utupub.fi/server/api/core/bitstreams/39593dae-44c6-4535-85e2-d398204c85a7/content).
- **S4:** [Kew: Cryptocoryne cordata regional distribution](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:86676-1); [Wong: runners and leaf morphology](https://www.aroid.org/gallery/wong/Araceae%20of%20Peat%20Swamp%20Forests%20-%20%5BBiodiversity%20of%20Tropical%20Peat%20Swamp%20Forests%20of%20Sarawak%2035-86%5D%20Wong%202016.pdf).
- **S5:** [Kew: Vallisneria spiralis in Thailand](https://powo.science.kew.org/taxon/431996-1); [Vallisneria spacer/branching experiment](https://www.sciencedirect.com/science/article/abs/pii/S0304377009000771).
- **S6:** [University of Florida: Limnophila leaf forms](https://plant-directory.ifas.ufl.edu/plant-directory/limnophila-sessiliflora/).
- **S7:** [Wild betta vegetation study](https://doi.org/10.1111/j.1095-8649.2001.tb02288.x); [USFWS tiger-barb distribution assessment](https://www.fws.gov/sites/default/files/documents/Ecological-Risk-Screening-Summary-Tiger-Barb.pdf).
- **S8:** [Rhizome branching across species](https://pure.knaw.nl/portal/en/publications/rhizome-elongation-and-seagrass-clonal-growth); [seaweed L-system modelling](https://doi.org/10.1016/0097-8493(93)90055-E).
- **S9:** [Flexible vegetation motion](https://doi.org/10.1016/j.coastaleng.2019.04.009).
