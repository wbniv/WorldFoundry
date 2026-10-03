# Planted Tank

One sea urchin crawling at 0.0125 world units/second among 384 plants (64 broad plants, 128 tall stems and 192 foreground tufts), grouped into eight static foliage meshes with 66,048 triangles. No fish, other animals or ornamental decorations. The original plants-only request was updated by Will to include the urchin.

Build: `bash wflevels/aquarium_plants/build.sh`. Run: `bash wflevels/aquarium_plants/run.sh`. Left/right crawls; desktop B/C changes depth. A changes whole-tank/close-up view, with release between presses. Vertical input cannot lift the urchin. The touch profile uses A mode/B view change; physical touch verification remains pending.

Menu index 5, named **Planted Tank**, in `aquarium-menu.manifest`. Engine checks: `python3 wflevels/aquarium_tanks/run_checks.py plants --video --cost`. Content and packaging checks: `python3 -m pytest tests/test_aquarium_plants.py tests/test_aquarium_menu.py -q`.

The dense tank uses curved closed leaves and connected swept stems. Plant groups have no scripts, physics or mailbox allocation. `PLANTED_TANK_DETAIL=density` builds the same population with simple folded leaves for comparison; `PLANTED_TANK_DETAIL=baseline` reproduces the archived sparse layout. The normal build defaults to `detailed`. Its standalone wrapper reserves 24 MB for one room slot, avoiding the old 6 MB room limit and unnecessary streaming-slot allocations.
