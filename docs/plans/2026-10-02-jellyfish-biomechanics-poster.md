# Moon-jelly swimming poster — A3

Date: 2026-10-02. Status: **updated A3 poster complete; all six translucent jellyfish verified on desktop and Chromecast HD.**

Will requested jellyfish-motion research and an A3 poster, then specified that this plan should be saved in `docs/plans/` and opened in the browser for review and approval. Prepare an illustrated explanation of moon-jelly swimming, with the same clear evidence labels used in the clownfish biomechanics poster. The biological story dominates; a small panel connects it to the Aquarium animation.

- [x] Read primary research on propulsion, bell-margin flexibility, natural pulse variation and turning.
- [x] Define content, source boundaries, A3 layout and production checks.
- [x] Build a full-page layout mockup with original diagrams and an illustrative computed pulse curve.
- [x] Will authorized the poster update and translucent jellyfish on 2026-10-03.
- [x] Build the final data sheet, vector artwork, one-page A3 PDF and PNG preview, including actual Blender and game renderings.
- [x] Check source/parameter consistency, PDF dimensions, links, text size and clipping.
- [ ] Inspect a physical A3 print if one is available.

## Completed update — 2026-10-03

[Open the updated poster](../reference/jellyfish-biomechanics-poster/poster.html) · [one-page A3 PDF](../reference/jellyfish-biomechanics-poster/jellyfish-biomechanics-a3.pdf) · [PNG preview](../reference/jellyfish-biomechanics-poster/poster.png).

Added two real renderings: Blender 5.0.1/Cycles (48 samples) imports the exported bell and arms, while the updated game panel shows the actual six-jelly tank on Chromecast HD/GLES. The earlier desktop OpenGL capture is retained in the evidence folder. The original six biology diagrams and research boundaries remain. The print source embeds every image and needs no network assets.

**GAME material settings:** bell 22% opacity; bell margin and oral arms 32%; marginal tentacles 12%; internal motifs 72%. These are art choices, not tissue measurements. Materials export through the existing OPAC metadata and shared translucent compositor; this change needs no further renderer API or shader changes. Binary comparison confirms that every existing model chunk is unchanged; only OPAC is added. Existing controllers, native weighted bell deformation and appendage lag remain intact. The menu bundle's jellyfish entry is replaced at the same byte length, preserving its other tank entries. This uses alpha compositing, without refraction or a fluid simulation.

The local generator checks adopted cycle/deformation constants and writes [data.json](../reference/jellyfish-biomechanics-poster/data.json). Pulse timing is 20% contract, 30% recover, 50% coast; player 4 s (3.2 s with UP); residents 4–5.4 s. The height coefficient is weighted by the margin, with the apex pinned: it is not a uniform 28% height increase.

**Validation:** native motion/compositor and exported material tests pass (19 tests). [Engine capture checks](../reference/jellyfish-biomechanics-poster/engine/checks.json) confirm six animals, both camera views, initialized controller, and a full native contraction range of 0–1. The older generic tank checker expects changing actor Z scale; that assertion is obsolete since the pulse deforms mesh vertices. A focused capture checks native contraction state instead, and the existing native geometry tests validate apex/margin/rest behavior. The final PDF has one A3 page (841.92 × 1191.12 pt); its raster was visually inspected. A physical print remains unchecked. The final poster includes Blender and Chromecast renderings; the desktop capture and native deformation checks remain separate evidence.

## Browser review

[Open the A3 layout mockup](2026-10-02-jellyfish-biomechanics-poster/layout.html). It is a **composition mockup**, not the final print artifact. Its graphs are explicitly illustrative animation proposals, not digitized experimental results.

![Proposed A3 portrait layout with moon-jelly anatomy and swimming diagrams](2026-10-02-jellyfish-biomechanics-poster/layout.png)

Proposed title: **MOON JELLY — THE ART OF THE PULSE**. Subtitle: *Aurelia aurita*: contraction, recovery and coasting. The mockup uses A3 portrait, 297 × 420 mm, to match the existing clownfish poster. Portrait, paper colors and panel balance are reviewable design choices.

## The six panels

| Panel | Diagram | Main message and provenance |
|---|---|---|
| A — Anatomy | Original side-view bell with apex, margin, short marginal tentacles and central oral arms; inset for internal regions | Distinguish the fringe from oral arms. Anatomical reference: Xu & Dabiri 2020, Fig. 1D. Shapes are schematic, not measurements. |
| B — One swimming cycle | Three bell states and a timeline: contract → recover/refill → coast | Circular muscle contraction drives the active stroke; recovery and the interval before the next pulse matter. Sources: Gemmell et al. 2013 and Villanueva et al. 2014. |
| C — Motion can outlast the stroke | Bell outline above a simple vortex cross-section; active stroke versus continued travel | Fluid motion can provide extra propulsion after active bell motion. Original explanatory arrows, with no claim to a computed flow field. Source: Gemmell et al. 2013. |
| D — The margin matters | Overlay of relaxed/contracted profiles with the flexible edge highlighted | Bell motion is more complex than uniform scaling; the flexible margin matters. Source: Villanueva et al. 2014. |
| E — Turning and trailing | Curved path with rotated bell silhouettes; short side comparison of central arms versus fringe | Turning can involve left/right timing differences; direction and travel need not immediately align. Source: Costello et al. 2024. Appendage lag is an animation proposal, not a measured phase delay. |
| F — From observation to animation | Computed normalized contraction curve, evidence badges and a compact proposed/current parameter table | Use independent pulse and drift clocks, recovery/coast intervals and bounded state. Clearly distinguish study values from our game choices. |

The completed poster will include an original moon-jelly illustration, diagrams, readable captions, figure-level source markers and a footer bibliography. Do not substitute a screenshot of the low-poly game model for biological anatomy. Do not copy a published figure, photograph or movie frame into the poster. Original redraws describe mechanisms rather than reproduce specific experimental plots.

## Checked research and claims

**[1] Gemmell et al. (2013), PNAS — passive energy recapture.** The paper describes contraction, relaxation/refilling and an interpulse phase. Muscle contraction occupies only a relatively small part of the cycles studied (approximately 20% across their illustrated species); post-relaxation propulsion can continue without active bell motion. Reported post-relaxation travel is 32% (SD 0.6%) of distance per pulse in their experiment. If used, that number gets its study context and a source marker; it is not a universal efficiency figure or a rule for every jellyfish. [Paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3816424/), [author-hosted full text](https://static1.squarespace.com/static/55885cf4e4b04e6344662d6a/t/5589cc6ce4b09ddbc396cc74/1435094124705/Ge_etal_PNAS13.pdf), [DOI](https://doi.org/10.1073/pnas.1306983110).

**[2] Villanueva, Vlachos & Priya (2014), PLOS ONE — flexible margins.** Their 6 cm *A. aurita* reference was digitized through the swim cycle; the margin followed a different deformation pattern from the rest of the bell. The poster highlights that flexible edge and calls whole-bell scaling a simplified game representation. It will not invent a fitted margin angle or bend law from the paper. [Full text](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0098310), [DOI](https://doi.org/10.1371/journal.pone.0098310).

**[3] Costello et al. (2024), Bioinspiration & Biomimetics — turning.** They describe asymmetric bell-margin timing associated with turning and rotation while the body continues translating, described as skidding. The drawing will show a curved path and changing orientation without assigning a measured turn radius or claiming our rig reproduces the asymmetry. [Author-hosted paper](https://static1.squarespace.com/static/55885cf4e4b04e6344662d6a/t/65afe9d4bbe6d727cb6b8396/1706027477599/CoCoGeDaKa_BB2024.pdf), [DOI](https://doi.org/10.1088/1748-3190/ad1db8).

**[4] Xu & Dabiri (2020), Science Advances — anatomy and variable pulses.** Fig. 1D provides the anatomical reference. Their free-swimming endogenous trials report 0.24 ± 0.11 Hz (n = 8); those vertical swimming trials used resting bell diameters of 13–19 cm. State those conditions beside the number. Do not confuse it with the 0.16 Hz spectral peak from their separate constrained experiment, or with electrically driven pulse frequencies. Natural pulsation varies; there is no single universal moon-jelly beat rate. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC6989144/), [DOI](https://doi.org/10.1126/sciadv.aaz3194).

These four primary papers were opened/read during this task. Where a PMC page returned a browser challenge, the full paper was checked using the publisher or author-hosted version. Search summaries alone are not sufficient for a “checked” number. The research covers moon-jelly examples, not all jellyfish species or every life stage.

## Evidence labels and numerical discipline

Use three small, consistent badges: **STUDY** (a checked observation with conditions), **SCHEMATIC** (original explanatory geometry/curve) and **GAME** (an explicit modelling choice or measured engine result). Put a badge next to each quantitative annotation, not just once in the footer.

Proposed game cycle: 20% contraction, 30% recovery, 50% coasting; a 4.0 s player period and 4.0–5.4 s resident periods, with separate slower drift routes. These are **GAME proposals**, not fitted timing data. The approximately 20% active portion and substantial interpulse interval in [1] motivate the structure; [4] demonstrates why the poster must retain biological variability. A normalized contraction curve uses a smooth rise and recovery, then a flat open-bell interval. Bell width contracts while height increases modestly; the viewer must see a stroke rather than an inflating balloon.

Proposed radial contraction 18%, height change 28%, and appendage lag/tilt values remain labelled GAME. The completed poster must read the actual adopted values from the level's motion constants; if tuning selects different values, update the diagram and table before printing. If performance appears on the poster, label local desktop debug timings separately from release/device measurements. Current desktop timing is not a claim about jellyfish physiology.

Do not present schematic pressure/vorticity arrows as numerical CFD, invent a measured oral-arm delay, claim an exact turning law, or apply pulse frequencies from one size/condition to all animals. The simplified rig lacks full asymmetric margin deformation; document that limit in panel F.

## Final production after approval

Target directory: `docs/reference/jellyfish-biomechanics-poster/`, with `data.json`, a local generator, self-contained `poster.html`, one-page `poster.pdf`, editable figure SVGs and `poster.png`. Link each quantitative claim to a data-sheet row with value, units, study context, evidence badge, URL and optional game symbol. The generator reads adopted motion constants rather than maintaining a second numerical copy.

Use vector anatomy/mechanism drawings and standard plotting tools for curves. The mockup's curve is computed with Matplotlib from a proposed normalized cycle; no tracing of a research plot is involved. Final curves retain the “illustrative” label unless actual experimental data are obtained and used with their provenance.

A3 portrait: 297 × 420 mm, one page, 10–12 mm safe margins, white/light paper, dark text and teal/coral accents that remain distinct in grayscale. Main title about 32–36 pt; panel titles 13–15 pt; body at least 10 pt; bibliography at least 8.5 pt. Keep every heading with its caption and each table row on the page. Use italic scientific names and unbroken value/unit pairs.

Provide a self-contained HTML print source and a PDF with embedded fonts, selectable text/vector diagrams and working bibliography links. A3 PDF size should be approximately 841.89 × 1190.55 pt (allow small browser rounding), with exactly one page. PNG preview: 150 dpi for review; optionally export a 300 dpi print raster when requested. No remote fonts or assets should be required after generation.

The initial poster scope used a standalone generator. Will subsequently authorized translucent jellyfish, then the Android build, Chromecast verification and commit/push. The jellyfish bundle update preserves other tank entries; unrelated shared-workspace changes remain outside these commits.

## Review and completion checks

Before final delivery, verify the page count/dimensions with `pdfinfo`; render the PDF to PNG and inspect the entire page plus diagram/table/footer details. Check clipping, overlap, label contrast, small text, italics, embedded fonts and link targets. Confirm every study value against its source/context and every GAME value against the adopted constants. Confirm the contraction curve wraps continuously, separates the three phases, and never labels its chosen timing as experimental data.

The original draft awaited review. Will's 2026-10-03 instruction to update the poster with renderings and make the jellyfish translucent authorizes this completed update.

Related: [three new tanks and runtime evidence](2026-10-02-aquarium-three-more-tanks.md), [clownfish biomechanics poster](2026-09-30-clownfish-biomechanics-poster.md).

## Chromecast follow-up

- [x] Build an Aquarium release APK from the clean checkout with the jellyfish update.
- [x] Install and select the jellyfish tank on Chromecast HD.
- [x] Inspect translucency and pulsing, and capture presented-frame timestamps.
- [x] Record device results and push the focused commits.

The installed APK is built from [25973305](https://github.com/wbniv/WorldFoundry/commit/2597330516d76c148a950c084e1ec427537f07cf), atop the already pushed renderer/FPS integration. APK SHA-256: `de95d99a5220a97687a98ab35f2337cdb75b72e636db6d0eec7e7d486060d3ea`. The 15 s warmup / 12 s idle trace records **29.97 FPS**, 383 intervals, median/p95 **33.367 ms**, on Chromecast HD / Android 14. The short trace is not an opaque-baseline comparison or thermal soak. A separate 6.67 s pulse recording was visually inspected; recording is excluded from the performance trace. All six animals remain visible, with translucent overlapping arms and independent pulsing. The app is left running in Jellyfish.

[Device validation and raw evidence](../reference/jellyfish-biomechanics-poster/chromecast/validation.md) · [pulse video](../reference/jellyfish-biomechanics-poster/chromecast/pulse.mp4). The updated poster's game panel now uses the actual Chromecast capture.
