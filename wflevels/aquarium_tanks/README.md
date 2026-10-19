# Aquarium tank sources and runtime plants

Shared source toolkit for Betta, Jellyfish, Lionfish and Planted Tank. The current Android bundle uses the eight-tank selector in `wflevels/aquarium-menu.manifest`. Older six-tank preview commands below are retained as development history.

| Tank | Animals | Visual rig | Scene |
|---|---:|---|---|
| Calm Betta | 1 | Body, tail, dorsal and anal fins | Broad leaves, pale sand, red/gold Thai pavilion with an empty open hall; no Buddha figure or statues |
| Jellyfish | 6 | Bell, oral arms, fringe | Dark rounded display; independent drifting routes and pulse phases |
| Lionfish | 2 | One native mesh per fish; selective jaw, skull and curved fin deformation | Sparse low reef rocks, pale sand and open water |
| Planted Tank | 1 sea urchin | Rounded test and radial spines | Seeded freshwater/saltwater growth in eight mesh groups, pale substrate |

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

## Current Android selector

The single Android menu path is `wflevels/aquarium-menu.manifest` → `wflevels/aquarium-menu-cd.iff`. Both APK tasks depend on `build-cd-iff-aquarium-menu`; the flavor asset symlink points to that bundle. The accidental five-tank path was removed. `aquarium-cd.iff` remains the direct/Apple bundle.

Planted Tank is index 5 in the current eight-tank selector, with one sea urchin, eight runtime foliage groups, substrate and tank structure (38 actors total). Its speed is 0.0125 world units/second, 1/20 of the initial crawl speed. It stays on the substrate; desktop B/C controls depth, arrows left/right crawl and short A toggles wide/close views; hold A opens plant settings. Build/run using `wflevels/aquarium_plants/build.sh` and `run.sh`. `run_checks.py plants --video --cost` verifies mesh presence, substrate height, four crawl boundaries, inward recovery and view input release. Current phone/remote settings and lifecycle checks passed on Chromecast; see the runtime section below.

`python3 wflevels/aquarium_tanks/check_menu.py --installed-bundle` checks the packaged tank payloads and the desktop sequence 5 → 2 → 3 → 4 → 0 → 1 → 5. The first aquarium standalone is preserved byte-for-byte during menu reconciliation. Tests: `python3 -m pytest tests/test_aquarium_menu.py tests/test_aquarium_plants.py -q`.

## Runtime planted colonies (2026-10-03)

Planted Tank now generates a fresh seeded ecosystem on selection: 16 founder shoots grow into 384 rooted plants, rendered in eight mesh groups. Freshwater uses broad rosettes, ribbons and fine whorls; saltwater uses seagrass ribbons, paired paddles and forked brown algae. The six-form opaque texture atlas follows individual leaves through growth and gentle root-pinned sway. Native buffers own the graph, rest shapes, UVs and deformation; plants do not receive individual actors.

Short A changes camera; hold A about one second opens plant settings. With Planted Tank highlighted in the selector, Right opens settings before entry. The phone provides the complete interface when connected; otherwise use the remote’s visible grid and numeric keypad. A enters/leaves slider adjustment; Left/Right adjusts while editing. The standard back arrow applies the draft and closes: speed-only edits preserve age, while seed/water edits regenerate. The former Apply speed button position stays empty; explicit Cancel discards edits. Growth speed does not change water sway or urchin movement.

The bottom-left display identifies the actual unsigned 32-bit seed and water type. Normal re-entry chooses a new seed; entering the same seed replays the same layout and growth history within that water type. [Plan, diagrams, captures and performance evidence](../../docs/plans/2026-10-03-aquatic-plant-clumps-and-poster.md).

## Current mature-static texture performance (2026-10-04)

Twenty coordinator-owned Chromecast HD traces used matching current native libraries: three release runs and one separate CPU trace per case. Freshwater textured/shaded: **14.64 / 22.19 FPS**, render CPU **60.39 / 33.02 ms**. Saltwater textured/shaded: **16.52 / 25.43 FPS**, render CPU **53.70 / 29.55 ms**. Actor CPU stays near **1.3 ms**, with 38 level actors in every case. Texture rendering costs 34–35% FPS; these CPU measurements do not measure GPU time.

The normal APK was restored and its installed hash verified. [Full tables, charts, evidence and reproduction](../../docs/plans/2026-10-03-aquatic-plant-clumps-and-poster.md#completed-current-build-texture-comparison). Implementation: `0aa37847`; benchmark: `d7e70afb`. Active growth/sway comparisons, seed-cost spread, speed-change pacing and same-process repeated-entry memory/latency remain pending. Use the shared coordinator for device work; archived direct-device procedures are reference text.

## Plant atlas resolution decision (2026-10-04)

Keep the production atlas at **256 × 256**, with six 72 × 112 leaf interiors and four-texel gutters. The larger source artwork is an authoring reference; it is not deployed. The 128 and 512 variants remain comparison artifacts.

| Trial | Appearance | Measured cost / benefit | Decision |
|---|---|---|---|
| 128 versus 256 | Softer veins and tissue grain in close-up | Saves 96 KiB of packed page data; no useful FPS/render CPU gain | Keep 256, confirmed by Will |
| 512 versus 256 | Finer close-up grain; subtle whole-tank difference | About +4 MiB PSS; saltwater −4.7% stationary-view FPS; worse close-up p95 pacing | Profile complete; production remains 256 |

The 512 profile completed 16 corrected coordinator traces with identical native libraries and geometry. Actual wide/close stationary views were audited, relabelled where entry input reversed the order, and analysed after one second of settling; crawl was excluded from every case. Close-up p95 rises to about 117 ms, versus 83 ms freshwater / 67 ms saltwater at 256. Freshwater average FPS is essentially unchanged. These stationary aggregates are separate from the preceding three-segment texture-toggle and 128 protocols.

The 512 variants use original artwork repacked into 144 × 224 interiors, plus `--vram-slot-width=512 --vram-slot-height=512 --vram-height=1024`. The last flag satisfies the legacy strict UV height bound. Configured CPU pixel-buffer capacity increases by 8.75 MiB; each uploaded transient GPU slot increases by 768 KiB, with lazy allocation. PSS snapshots do not isolate GPU residency. Normal 256 APK restoration and installed-hash verification passed after both completed comparisons.

[Resolution tables, paired captures, camera audit and reproduction](../../docs/plans/2026-10-03-aquatic-plant-clumps-and-poster.md#completed-512-atlas-qualitycost-comparison). Renderer submission/UV optimization and broader growth/sway/lifetime profiling remain separate work.

## Lionfish realism (5 October 2026)

The current lionfish uses one 4,068-triangle mesh per animal, shared 256² body
and fin maps, stable per-fish palette remapping and 0.55 translucent membranes.
Named region/weight/pivot attributes export separately from texture UVs to LRIG
v1. `lion-pose` publishes phase, drive, turn, gape, dark/light packed colors and
actor index once per fish. The approved native implementation caches rest
vertices and keeps instances independent. Future fish IDs use `palette_for`;
no recolored texture files are needed. `LIONFISH_REALISM=0` retains the historical
multipart geometry for asset comparisons; use the archived baseline engine/APK
for a true performance baseline.

Build only this level, then repack the existing selector without regenerating
other tanks:

```sh
bash wflevels/aquarium_lionfish/build.sh
wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell-menu.fth \
  --manifest wflevels/aquarium-menu.manifest -o wflevels/aquarium-menu-cd.iff
cd android
./gradlew assembleAquariumRelease
```

The standalone `run.sh` and Aquarium `wf_args.txt` both configure 512² texture
slots/permanent page in a 2048 × 1024 pixel buffer. Those are packed pages;
each source lionfish map is still 256². Other tank payloads remain unchanged.
The local exporter is imported from this checkout; install its matching
`wf_core` extension before Blender export. The Rust `iffcomp`, `levcomp`,
`textile` and `cdpack` tools must be built.

Verify actual feeding with `python3 scripts/check-lionfish-feeding.py` (desktop
GUI required). It checks release limits, proximity, complete gulp, slot reuse,
delayed notice, natural resident pursuit/capture and escape from actual approach.
Focused tests live in `tests/test_lionfish_{feeding,rig,suction,realism_asset}.py`.
The Director owns every prey write; scratch 1300–1347 is transient flow work.
A reservation never immobilizes prey. Swept aperture entry starts engulfment;
intraoral transport, rather than a timer, completes consumption.

Prepare measurement APKs with `scripts/profile-lionfish-realism.py prepare`
(`--help` lists the exact baseline-checkout/APK and signing options), submit its
recipe with `task chromecast:submit DEVICE=all RECIPE=/absolute/path/recipe.json`,
and fetch evidence with `task chromecast:evidence BATCH=... OUT=...`. Fixed
three-prey measurement variants disable resident auto-capture; the normal APK
retains it and is restored by the service. Presentation samples use three runs,
while separate CPU variants add existing `--frame-profile` instrumentation.
The summary script reads only the final complete CPU window so old app sessions
in appended logs cannot contaminate the result.

[Implementation, device evidence, deltas and A3 poster](../../docs/plans/2026-10-05-lionfish-realism.md).
