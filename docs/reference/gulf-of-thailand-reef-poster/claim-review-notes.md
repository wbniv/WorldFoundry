# Poster claim review notes — 2026-11-02

Review is incomplete and does not approve the poster. Source assignments and printed wording need independent checks against the full sources before the final gate is opened. A source link and a status flag establish traceability, not verification by themselves.

## Issues to resolve

- **Fish swap, 2026‑11‑09.** Will swapped the humbug *Dascyllus aruanus* (no citable Gulf record) for *D. reticulatus* and parked the poster ("park poster"). `claims.py` and the species label in `reef_art.py` name *D. reticulatus*, but the drawings still show the humbug's three bands: `humbug-illustration-v3.png`, `reef_art.humbug()` and `render.humbug_drawing()` must be redrawn to the grey body, black bar behind the head onto the dorsal and pelvic fins, fainter rear bar and dark scale margins ([FishBase](https://www.fishbase.se/summary/Dascyllus-reticulatus.html), [Reef Life Survey](https://reeflifesurvey.com/species/dascyllus-reticulatus/)) before the poster prints. Internal keys stay `humbug`.

- `R` is explained as another region or related species, but the feather-duster food and withdrawal claims cite general genus accounts. Broaden the legend to cover general/broader-taxon accounts and describe the evidence scope on the claim, or supply narrower evidence. In particular, avoid making a genus account imply a directly observed Gulf individual.
- The printed heading `Defence` is applied indiscriminately to observations of hiding, sediment-associated mucus, inhibition of bacterial adhesion in a lab, and predicted toxins. Those observations do not all establish an observed defensive function in the species. Use neutral, precise headings for those rows or establish the specific defensive function from the cited studies.
- The Goniopora diet row describes food offered in captivity. Confirm from the full Ding et al. experiment that the named foods were consumed before implying consumption through the heading `Eats`; otherwise describe the experimental feeding treatment neutrally.
- The fish-toxin claim attributes boxfish toxin generally to the Maldives guide; confirm the guide addresses the species or explicitly qualify the claim to boxfishes generally.
- Confirm the fluted clam shadow-and-touch claim specifically applies to *Tridacna squamosa*, rather than another giant-clam species in the review.
- The printed map labels itself schematic and not to scale. Its Gulf coastline is hand drawn, whereas the highlighted Bangkok outline comes from the attributed ADM1 dataset. The projection scales longitude and latitude independently, so it should be described as a simplified/transformed administrative outline over a schematic coastline, not as a survey-accurate map.
- All `T` statements are authored planned-tank effects, not observations. Keep their status and future/planned framing clear; the printed tank heading supplies that context.

## Full automated suite

Ran `tests/test_poster_gulf_of_thailand_reef.py` in the network-disabled `wf-coordinator-python-test:local` container with the worktree mounted read-only: 12 passed, 8 skipped, 3 failed, 12 errors. The errors and failures reflect the intentionally closed visual/claim-review gate and missing final layout approval/export; browser/Poppler-dependent tests skipped because those tools are absent from the test container. This is not a clean final-test pass and visual approval remains Will's decision.

## Corrections and rechecks

- The R key now includes broader-taxon accounts. The feather-duster rows explicitly identify their genus-account scope.
- Shelter, sediment, response and laboratory findings use neutral row labels where the cited observation does not itself demonstrate defensive function.
- Ding et al., section 2.2.2, reported observing microalgae and yeast in the body cavities of captive *Goniopora columna*; the revised row states that observation and no longer implies the liquid prepared feed was directly observed there. https://pmc.ncbi.nlm.nih.gov/articles/PMC8614412/
- The Maldives guide explicitly attributes skin toxin to *Ostracion cubicus*, and the giant-clam anti-predator review explicitly includes *T. squamosa* among species sensitive to both shadow and tactile stimuli. https://www.fao.org/4/ad471e/ad471e60.pdf ; https://link.springer.com/content/pdf/10.1007/s00227-014-2545-0.pdf
- The Bangkok outline now uses a locally equirectangular longitude correction at 13.75°N and a single uniform fit scale for both axes. Geographic placement is retained, with schematic coastline disclaimer unchanged. This preserves local shape approximately; the overall coastline remains an illustration, not GIS survey data.
- After these changes, the containerized targeted suite passed 11 tests (24 deselected). The final-review gate remains closed and remaining claims still require an independent full-source audit.
