# Planted Tank

One sea urchin among eight runtime plant groups. The current urchin has a textured rounded test, 61 primary spines and 40 smaller spines, plus eight pale tube feet. Body and feet share a deterministic 256 × 256 atlas in the permanent asset slot; the plant texture page stays unchanged. Feet use the existing material-opacity capability. Phase 1 has 3,540 animal source triangles, nine animal actors and 38 scene actors.

Build: `bash wflevels/aquarium_plants/build.sh`. Run: `bash wflevels/aquarium_plants/run.sh`. D-pad directions crawl directly on the substrate at 0.0125 world units/second, with normalized diagonals. Tap A changes wide/close view; hold A opens plant settings. The back arrow applies/closes settings, returns from the level to the selector, and exits from the selector. Plant growth speed does not control the animal.

Menu index 5 is **Planted Tank** in `aquarium-menu.manifest`. The existing freshwater/saltwater settings remain available; the urchin realism preview uses saltwater. A suitable freshwater resident or a plant-only freshwater view remains a separate design decision.

Content checks: `pytest -q tests/test_aquarium_plants.py tests/test_urchin_asset.py`. Desktop debug-bridge traces check visual/control correctness only; performance comparisons use matched Chromecast jobs through the coordinator. See [the sea-urchin plan](../../docs/plans/2026-10-05-sea-urchin-realism.md) and [phase comparison](../../docs/plans/2026-10-05-sea-urchin-realism/comparison.md).

The source model and atlas generator live in `wflevels/aquarium_tanks/urchin.py`; runtime plant authoring remains independent. Phases 2–3 will improve contact anchoring and add eight representative basal spine pivots without engine edits. The sea-anemone/generic-deformation work remains set aside.
