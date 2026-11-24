# Tulpenkade

Dutch Cuckoo Village is a standalone World Foundry clock. This worktree's branch is
`feat/dutch-cuckoo-village`, targeting `2026-new-level`. The plan contains the visual
references, animation timetable and desktop captures. [Plan and PC views](../../docs/plans/2026-11-24-dutch-cuckoo-village.md)

From the repository root, build and run the interactive desktop level with

```sh
bash wflevels/dutch_cuckoo_village/build.sh
engine/wf_game -Lwflevels/dutch_cuckoo_village-standalone.iff -width=1280 -height=720 --no-fps
```

Journey follows a closed spline above the quay and inland streets. Still holds an elevated
view across the tulip beds. Hold OK for one second to choose the camera or toggle window
lights. Both modes use local time. On even hours the loaded barge travels east, and on odd
hours it returns west. Sound and general camera collision detection are tracked in [TODO](../../TODO.md).

To reproduce the captures and clock checks, run

```sh
python3 wflevels/dutch_cuckoo_village/capture.py build-docker/tulpenkade 10:00:10 10:01:52 18:00:08
python3 wflevels/dutch_cuckoo_village/capture.py --still build-docker/tulpenkade 10:08:00
pytest -q tests/test_dutch_cuckoo_village.py
```

The build samples every camera leg against the Blender town mesh. It checks eye clearance
and rays through the desktop near plane. The VM check exercises clock jumps, both crossing
directions, the three solos, the cheese scale, rain, windows and camera settings.

The town geometry and painted material atlas are original procedural assets in `town.py`
and `materials.py`. The hand, balcony and cuckoo movements share the original village's
clock equations. The generator writes atlas UVs in cooked-image row order. To render the
Blender reference on a configured host, set `TULPENKADE_REVIEW` to an absolute PNG path
when running the build with `WF_LEVEL_BUILD_HOST=1`.
