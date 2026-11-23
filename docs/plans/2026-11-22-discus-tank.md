# Discus tank

The twelfth Aquarium entry adds ten brown discus (*Symphysodon aequifasciatus*): a player and nine residents using the existing schooling controller. The tank reuses the freshwater shell and sand, and has a screensaver variant with an automatic player. Existing menu indices remain unchanged.

The fish geometry and photographic texture are in `wflevels/discus_asset`; see its README for source attribution and licensing. The tank generator and movement live in `wflevels/aquarium`, and `wflevels/aquarium_discus/build.sh` rebuilds the level. The default level settings provide the framerate toggle. The design sketch is [here](2026-11-22-discus-tank/discus-tank.png).

Verification must cover the cooked level in the engine, directional input and release, schooling, the chooser and screensaver, and performance on a Chromecast. `tests/test_aquarium_discus.py` checks the roster, bounds, assets, scripts and screensaver wiring; desktop captures can be made with `docs/diagnostics/aquarium-discus-2026-11-22/capture.py`. Device verification is still pending.
