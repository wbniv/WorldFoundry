# Four new Aquarium tanks

Independent Betta, Jellyfish, Lionfish and Planted Tank levels. The original aquarium and Blue Shrimp sources, current app bundle, Android assets, Taskfile and engine are left to their existing work.

| Tank | Animals | Visual rig | Scene |
|---|---:|---|---|
| Calm Betta | 1 | Body, tail, dorsal and anal fins | Broad leaves, pale sand, red/gold Thai pavilion with an empty open hall; no Buddha figure or statues |
| Jellyfish | 6 | Bell, oral arms, fringe | Dark rounded display; independent drifting routes and pulse phases |
| Lionfish | 2 | Body/spines, tail and two fan fins | Sparse low reef rocks, pale sand and open water |
| Planted Tank | 1 sea urchin | Rounded test and radial spines | Three static foliage groups, pale substrate |

Build with `bash wflevels/aquarium_betta/build.sh`, `bash wflevels/aquarium_jellyfish/build.sh` and `bash wflevels/aquarium_lionfish/build.sh`. Each owns its exported files and standalone IFF. The new local toolkit provides procedural meshes, Blender scaffolding and a zForth controller/pose library without importing either existing aquarium generator. `TANK_COUNT=1` makes a single-animal build; `TANK_PROFILE=touch` selects the touch mode/action mapping. Rebuild without either variable to restore the default keyboard/population artifact.

Run with the matching `bash wflevels/aquarium_<kind>/run.sh`. Arrows move horizontally and vertically; B/2 moves toward the glass and C/3 away; A/1 makes a forward swim burst or stronger upward jelly pulse, with cooldown. The touch profile uses A to switch vertical/depth mode and B for the action. Physical touch/remote device verification remains pending. Neutral buoyancy and smoothed velocities keep idle movement restrained. There are wide/close cameras with hysteresis, and controls can move away from all six boundaries. Complete animated silhouettes determine conservative limits for turning.

Jellies use opaque geometry. Bell-only nonuniform scaling changes bell shape while independently posed oral arms lag/sway; this is not a translucent fluid or soft-body simulation. Fish use compact articulated rigs rather than the other agent's experimental one-mesh vertex-animation path. Decorative pieces are anchored platform actors with no individual physics bodies; the player has a small invisible neutral hull.

Content checks: `python3 -m pytest tests/test_aquarium_new_tanks.py -q`.

Real engine checks/captures: `python3 wflevels/aquarium_tanks/run_checks.py betta --video --cost`, substituting `jellyfish` or `lionfish`. They use separate debug ports 17921–17923 and verify scripts, animation, camera selection, six directional endpoints plus inward recovery, input isolation and action/cooldown. The cost option is a two-point desktop debug wall-time estimate with vsync disabled, not a release/device frame distribution. Run timing checks sequentially. Clips encode fixed 20 Hz simulation frames and do not measure rendering FPS.

## Isolated menu preview

`bash wflevels/aquarium_tanks/run_menu.sh` snapshots the current six standalone levels and launches the existing SMB-style selector in this directory's ignored `preview/` folder. It never writes `aquarium-cd.iff`, shared Taskfile or Android assets. The first menu label is deliberately “Original Aquarium” while its contents are being changed. The snapshot records source hashes; a concurrent file change causes a retry rather than packaging a partial build. This preview is for desktop review, not an installed app update.

`python3 wflevels/aquarium_tanks/check_menu.py` validates six menu entries, exact snapshotted payload hashes and the real engine's 5 → 2 → 3 → 4 → 0 → 1 → 5 selection/return sequence. The menu check uses debug port 17924. Desktop arrows choose, Space opens and Backspace returns, using the existing menu's input-release and session-memory behavior.

App packaging, the final first-tank label, release performance, Android/Chromecast and Apple menu verification remain coordinated follow-up work. The other agent is using the shared device for first-tank profiling. Evidence and current status: [implementation plan](../../docs/plans/2026-10-02-aquarium-three-more-tanks.md).

Desktop results: all three runtime checks pass; 11 content tests and three focused SMB menu regressions pass. The isolated six-tank menu passes all seven selections and six returns. Current debug estimates: Betta 11.0 ms/frame, Jellyfish 26.1 ms/frame, Lionfish 9.0 ms/frame. These do not establish release/device performance; Jellyfish needs tuning and target-device measurement.

## Installed six-tank Android selector

The single Android menu path is `wflevels/aquarium-menu.manifest` → `wflevels/aquarium-menu-cd.iff`. Both APK tasks depend on `build-cd-iff-aquarium-menu`; the flavor asset symlink points to that bundle. The accidental five-tank path was removed. `aquarium-cd.iff` remains the direct/Apple bundle.

Planted Tank is index 5, with one sea urchin, three static foliage groups, substrate and the tank structure. Its speed is 0.0125 world units/second, 1/20 of the initial crawl speed. It stays on the substrate; desktop B/C controls depth, arrows left/right crawl and A toggles wide/close views. Build/run using `wflevels/aquarium_plants/build.sh` and `run.sh`. `run_checks.py plants --video --cost` verifies mesh presence, substrate height, four crawl boundaries, inward recovery and view input release. The touch profile uses A for mode and B for view changes; physical touch is pending.

`python3 wflevels/aquarium_tanks/check_menu.py --installed-bundle` checks exact six-tank packaged payloads and the desktop sequence 5 → 2 → 3 → 4 → 0 → 1 → 5. The first aquarium standalone is preserved byte-for-byte during menu reconciliation. Tests: `python3 -m pytest tests/test_aquarium_menu.py tests/test_aquarium_plants.py -q`.
