# Aquarium: clumped plant growth, gentle water motion and an A3 poster

**Status:** researched plant-level implementation plan with completed A3 portrait poster. Runtime colony generation, revised plant forms and sway are not implemented. This supersedes the row-based composition in the [first dense planting pass](2026-10-03-aquarium-dense-planted-tank.md), while retaining its geometry and profiling evidence as a reference.

Replace obvious rows with **connected, irregular patches of growth**. Grow toward a mostly-full mature tank: overlapping clumps should eventually cover roughly 75–85% of the submerged interior in the whole-tank view, with local gaps and a small, winding substrate route for the sea urchin. Add subtle, coherent water-driven bending with anchored roots. Make an **A3 portrait poster**, split into saltwater on the left and freshwater on the right; reserve the **bottom 25% of the page** for diagrams and explanations of clumping and branching.

## Plant-level behavior

**Every time the player selects Planted Tank, start a new seeded ecosystem and let the player watch it grow.** Begin with 12–18 small young founder colonies. Runners extend, daughter shoots emerge, leaves unfurl, stems elongate and side branches/whorls appear; the scene gradually becomes the mostly-full mature tank. Returning to the selector and selecting it again starts different founders and growth choices. Changing camera keeps the current ecosystem; pause freezes growth and sway, and resume continues without a large catch-up jump. The eight-tank selector, sea urchin and existing controls remain the content baseline.

Growth is visibly accelerated and authored, not presented as real biological time. Initial tuning target: clearly noticeable development within 5–10 seconds, several expanding colonies by 30 seconds, and a mostly-full canopy around 90–180 seconds. These are adjustable design targets awaiting visual review and device measurements. Mature growth slows or stops at bounded density; indefinite turnover is deferred. Keep the urchin route usable at every stage.

Use a fresh engine-owned seed per entry and log/display it. Allow player seed entry and expose a developer fixed-seed override for reproducible captures, regression checks and matched profiling. Same seed, settings and generator version must reproduce positions, lineage, shapes and colours. Independent random streams for growth choices, morphology and sway prevent a new leaf rule from unexpectedly relocating every colony. A fresh seed changes the scene while bounded density and spacing rules keep every result usable.

![Runtime generation and ownership](2026-10-03-aquatic-plant-clumps-and-poster/runtime-generation-diagram.svg)

![Young colonies growing into a mature canopy](2026-10-03-aquatic-plant-clumps-and-poster/growth-stages-mockup.svg)

![Three different seeded tank compositions](2026-10-03-aquatic-plant-clumps-and-poster/seed-variation-mockups.svg)

These are design diagrams and mockups, not engine captures or claims that runtime mesh construction already exists. New runtime interfaces must be implemented and measured. Visible runtime growth is required, alongside gentle sway. Continued mature-tank turnover is a possible later phase.

## Player seed and growth-speed controls

Show **`Seed: 713`** (the actual current value) at the **bottom left** of the planted-level view, inside the TV safe area. Use readable high-contrast text with a restrained dark backing; reserve the bottom-right area for the existing WF badge/FPS. Keep the seed visible while plants grow, after switching cameras and when reopening a replay. The number stays constant during one ecosystem's lifetime.

Players can enter a seed and **regenerate the level**:

- **TV remote / gamepad in the level:** hold **A / the remote centre button** for about one second to open the seed editor. A short press retains its existing camera action; distinguish tap versus hold and never perform the camera action after a recognized hold. Show the concise `Hold A: change seed` hint beside the seed. This is proposed input work to implement and check on Chromecast, including key-repeat/release behavior.
- **Selector:** with Planted Tank highlighted, **→** opens the same seed editor before entering. Normal selection starts a fresh random ecosystem. Seed-entry regeneration selects Planted Tank with the submitted seed; other level controls remain unchanged.
- **Phone controller:** provide a `Seed…` action opening the same editor; allow phone numeric text input as an additional convenience. Open the phone’s numeric keyboard for direct seed entry, with the same field validation and regenerate action as the TV. The TV 10-key keypad remains sufficient without a phone.

The settings panel has a seed field, a standard **10-key numeric keypad** laid out `1 2 3 / 4 5 6 / 7 8 9 / ⌫ 0 Clear`, a **Growth speed** slider, **Regenerate**, **New random seed**, and cancel. Enter the number through the 10-key keypad or phone numeric field; a connected physical numeric keyboard may also type digits directly. Direction arrows move keypad focus; A selects a key or action; **↶** cancels. Pause growth, sway and the urchin while editing. Cancel resumes the same tank at the same growth time, without a new seed or resource replacement. Keep current seed visible/pre-filled; entering a new value replaces it through normal editing.

Accept decimal unsigned seeds **0–4,294,967,295**, at most ten digits; zero is valid. Reject empty, non-integer and out-of-range input with a short inline explanation, preserving the current tank. Normalize leading zeros after successful submission. Handle the seed as an exact native integer: do not silently round it through a single float-valued Forth cell. Pass deterministic PRNG state to Forth in an exact supported representation, or keep PRNG state native with explicit bounded-number operations.

**Regenerate** resets the growth clock, safely releases/replaces level-owned growth and mesh buffers, and starts young founders from the submitted seed. Re-entering the same seed replays the same growth choices at the same simulation time, rather than restoring the previous plant ages. **New random seed** chooses and displays a fresh seed and starts a new ecosystem immediately. Log seed, generator version and growth settings for reproduction. Repeated regeneration must not leak buffers or disturb the other aquarium levels.

### Growth-speed slider

Default **1×**: author the mature canopy to appear around **90–180 seconds**, with a visible change in 5–10 seconds. Add selectable **Paused, 0.25×, 0.5×, 1×, 2×, 4× and 8×** positions, initially proposed pending runtime profiling. At 0.25× the target becomes approximately 6–12 minutes; at 2×, 45–90 seconds; at 8×, roughly 11–23 seconds, **if the measured update budget can sustain that rate**. Do not promise unsupported maximum rates: measure them and revise the offered range if necessary.

When the slider is focused, ←/→ decreases/increases the rate; touch dragging chooses a position. Show the selected multiplier beside the track. Changing speed preserves seed, plants, current growth time and growth history. Keep it as a session setting for subsequent regenerations/selections. Cancelling the settings panel discards unsubmitted seed/speed edits. **Regenerate** commits both settings and restarts from young founders; add an **Apply speed** action that commits only speed and resumes the existing ecosystem. A displayed **Paused** growth setting stops growth but leaves gentle water sway and urchin controls active after closing the panel; opening the modal panel still pauses the whole tank.

The slider scales only the fixed-step **growth clock**, not water motion, player movement, camera response or render frame rate. Derive development from accumulated growth time; use seeded fixed-step events so different rates reach the same botanical state at the same growth time. Root-pinned sway uses its own real-time clock. High speeds must respect bounded dirty-group construction/upload budgets and avoid bursts of mesh replacements; measure worst-frame pacing while dragging/changing speed and during rapid growth. Profiles specify seed, multiplier, growth time and young/intermediate/mature snapshot explicitly.

![Seed display and numeric editor mockup](2026-10-03-aquatic-plant-clumps-and-poster/seed-editor-mockup.svg)

![Seed validation and regeneration flow](2026-10-03-aquatic-plant-clumps-and-poster/seed-regeneration-diagram.svg)

## Poster and research reference

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

On each entry, start from around **12–18 founder patches**, with irregular sizes and outlines. Allocate most plants to a few substantial colonies and fewer to small satellite patches. Grow daughter plants from existing parent nodes using species-specific step lengths and correlated heading changes; avoid random jitter of the old rows. Stop or divert growth at tank margins, the crawl route and excessive local crowding. Use bounded parent-to-daughter rhizome/stolon walks in the first version, with minimum spacing and local crowding checks. Independent random dots around founders are useful for a prototype mockup but are not the final growth model.

Correlate species, age, height and colour within each patch, then vary them among individuals. Younger daughters tend to occupy expanding edges in the simplified authored model. Blend adjoining patches and create local pockets rather than dividing the scene into eight rectangular botanical zones. **Render chunks are independent of biological clumps:** partition the finished geometry for mesh limits, but do not let chunk boundaries determine planting positions.

### Plant palette and growth rules

Use the freshwater side of the poster as **shape and architecture references** for the current authored plant tank. This does not assert an exact biotope or change the existing sea urchin. Keep marine examples in the poster as a distinct future palette; do not put temperate Fucus into a supposed tropical freshwater habitat.

| Form | Colony model | Mesh silhouette | Variation and crowding |
|---|---|---|---|
| Crypt-like broad rosette | Short connected runner steps produce compact daughter groups | Curved oval/cordate leaves emerge radially from each base; varied petiole lengths | Mixed young/small and mature/broad rosettes; taper density near patch edges |
| Vallisneria-like ribbon tuft | Longer stolon steps with occasional side daughters spread through neighbouring space | Long flexible ribbons, varied width, bend and tip height | Clustered bases, individually curved blades; avoid parallel equal-height fences |
| Limnophila-like fine stem | Local stem colonies with variable internodes and bounded side branches | Feathery submerged whorls around nodes, rather than identical paired leaves | Vary whorl count, orientation, branch length and age; retain gaps between stems |

Begin around the existing 384 rooted shoots, but distribute them unevenly between 12–18 colonies. Colony quotas, footprint, species mix and age distribution vary per seed; global shoot/leaf/vertex limits stay bounded. These quotas and 75–85% coverage are authoring targets, not measured botanical population ratios. Grow most tall foliage through the back and middle depth, mixed broad colonies in front/middle, and low daughter growth around edges. Preserve a winding substrate route and local pockets for the urchin instead of one bare straight strip. Nearby colonies can interlock; avoid both rectangular botanical partitions and evenly spaced decorative islands.

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

Initialize founder colonies on entry, then advance the growth network and geometry **at runtime while the level is active**. Forth supplies the species growth policy and advances bounded growth steps; native code owns graph/vertex buffers and performs bounded incremental mesh construction. During play, Forth computes shared phase, amplitude and a handful of coefficients for the mesh chunks. Prefer a small native deformation operation over interpreting a loop across ~38,000 vertices in Forth. Inspect the existing fin/fish deformation paths for reusable rest-vertex storage and packed weights; **there is currently no verified plant-sway syscall to print as working code**. Do not rotate an entire merged chunk around the world origin, lift roots or allocate a controller for each plant. Smooth whole-mesh deformation should leave collisions and the urchin controller unchanged.

## Runtime implementation and profiling phases

**Measured reference:** the static dense trial is complete. Its matched Chromecast runs produced 39.87 FPS for the 57-plant baseline, 29.94 FPS for 384 plants with simple closed leaves, and 20.21 FPS for 384 detailed plants / 66,048 triangles. Render CPU time rose 3.70 → 18.16 → 42.88 ms while actor CPU stayed near 1.3 ms. These are render-path CPU measurements, not GPU timings. [Full comparison and receipts](2026-10-03-aquarium-dense-planted-tank.md), [machine-readable data](2026-10-03-aquarium-dense-planted-tank/performance.json).

1. **Seeded growth graph and static controls:** add a level-entry seed and bounded growth service, with Forth policy and native graph/mesh storage. Support a developer fast-forward/freeze control to compare a mature generated layout against the fixed row-based reference. Match counts, mesh grouping and native binaries. Capture young, intermediate and mature states across at least three seeds; measure entry-to-playable latency separately.
2. **Botanical forms and geometry efficiency:** replace generic paired stems with whorls, introduce ribbon tufts and age variation, and tune branch/leaf silhouettes. Preserve the mostly-full tank rather than reducing plant density to regain FPS. Compare curved leaf section counts, hidden/redundant faces and branch detail at matched seeds. The 66k-triangle reference is a comparison point, not proof it is a good final budget. Test an intermediate geometry budget as well, and show the visual tradeoff before selecting it.
3. **Watch colonies grow:** advance a deterministic fixed-step growth clock. Spread daughters from existing parents with species-specific spacers and branching rules. Animate young leaves/stems from small forms to mature rest shapes smoothly; do not pop full-sized plants into view or rebuild every group each frame. Batch topology changes only for dirty groups, with a measured per-update budget and fair scheduling. Compare frozen versus growing young/intermediate/mature states at identical seed, topology and camera. Record update spikes and worst-frame pacing, not only average FPS.
4. **Gentle shared water:** add native root-pinned vertex bending to the same generated meshes. Forth controls shared phase and coefficients; avoid per-vertex interpreted loops and per-plant actors. Compare static versus sway at identical seed and geometry. Use the same startup seed for normal and instrumented builds.
5. **Player seed editing:** add bottom-left display, tap/hold input handling, selector entry, numeric editor, growth-speed slider and exact integer validation. Verify same-seed replay, new random seed, cancelling without changing the tank, zero/max/invalid inputs, phone/remote navigation, apply-speed versus regenerate, and deterministic growth across speed settings.
6. **Repeated-entry stability and variation:** repeatedly enter/leave the level, checking new seeds, allocator ownership, peak memory, return-to-selector behavior and regeneration latency. Confirm all other seven level payloads are unaffected. Restore the normal eight-tank release after profiling and verify its installed hash. Continue to test growth through the mature cap, then freeze topology cleanly. Continuous mature turnover is a later option; visible growth from founders is part of this plan.

### Runtime ownership and bounded work

Use a few level-owned mesh groups (initially eight), never one actor per rooted shoot. Retain rest positions, per-vertex local base/height weights and per-group bounds. The existing static exporter and fish-deformation path are useful references; runtime plant mesh creation and swapping are **new engine work**, not existing verified APIs. Keep render buffers/material references alive until replacement is safe, clear them on level exit, and never mutate shared meshes belonging to other tanks.

Bound founders, daughter attempts, shoot count, branch depth, leaves and total vertices. Stop or divert crowded growth instead of running an unbounded rejection loop. Validate index bounds, winding, triangle area, tank/water bounds and rooted bases before publishing each changed group. Check the existing mesh/index limit and split groups before exceeding it. Keep the last valid group until a complete validated replacement is ready; reject invalid growth additions cleanly. Seeded failure must be reproducible; do not turn a generation failure into a black screen.

The current detailed level uses a 24 MB room pool and one room slot. Runtime graph storage, rest vertices, deformation weights and temporary construction buffers add peak memory; measure those explicitly and reuse scratch buffers where practical. Bound generation batches so loading and ongoing controls remain responsive. Preallocate bounded capacity where useful, and update only changed groups. Smooth growth of existing vertices should use native local growth weights/rest geometry; topology additions and sway share the same root/base ownership contract. Apply sway after growth deformation so young and mature plants both keep their roots fixed. Keep the whole-tank growth clock independent of render frame rate. Profile Forth policy, graph construction, leaf/branch meshing, upload/publication, actor updates, deformation and render work independently. Do not claim a loading-time target until device measurements exist.

| Phase | Layout / geometry | Motion | Required comparison |
|---|---|---|---|
| Archived sparse / dense simple / dense detailed | Fixed row-based assets | Static | Completed 39.87 / 29.94 / 20.21 FPS references |
| Seeded colonies | Fresh founders; frozen mature control | Static | Startup, memory and mature layout delta versus fixed assets |
| Revised botanical forms | Same chosen seeds; variable detail budgets | Static | Silhouettes/coverage plus layout, geometry and rendering deltas |
| Visible growth | Young → spreading → mature; fixed seed/time snapshots | Smooth unfurling plus topology additions | Frozen vs growing CPU/pacing and allocation spikes at each stage |
| Shared gentle water | Same growing colonies and meshes | Root-pinned sway | Incremental native deformation and pacing cost |
| Repeat selections | New seeds; released/recreated level buffers | Same | Variation, bounded generation, no memory growth or leaked resources |

For each steady-state phase, use three repeated release runs with identical native binaries, seeded layout, camera positions and input trace: wide idle, close idle and close crawl. Record presented FPS/p95 pacing, actor/director time, construction/deformation/render CPU, memory, triangles/groups and absolute/percentage deltas. Report startup costs separately so they cannot be hidden inside a steady-state average. For growing captures, also match growth clock, node count and topology state; compare pauses at fixed young/intermediate/mature snapshots and active growth over the same interval. Use multiple seeds to report cost spread and worst observed composition, then replay the same seeds for comparisons.

Acceptance: bottom-left seed display and player-entered regeneration work on the remote; the same seed reproduces the growth sequence; each selection starts a different young ecosystem that visibly grows into a mostly-full tank; fixed-seed replay is reproducible; colonies have connected growth and irregular outlines; ribbon, rosette and whorled forms remain readable; tall foliage varies in height and age; roots remain fixed under slow coherent sway; the urchin has a usable local route; repeated level entry frees resources; and measured loading/rendering/motion costs are recorded. The A3 portrait PDF remains one page at 297 × 420 mm with its bottom-quarter pattern band and checked Forth examples.

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
