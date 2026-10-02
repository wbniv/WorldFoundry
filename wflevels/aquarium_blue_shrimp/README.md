# Blue Shrimp — Aquarium level 2

An independent planted aquarium with 24 articulated blue shrimp: one player and
23 residents. Pale sand, rocks, branching wood, plants and moss replace the reef
dressing. Residents graze, crawl along separate authored lanes, and make short
water-column excursions with different periods and phases. Five shared meshes
form each shrimp: body/eyes, segmented abdomen/tail, near legs, far legs and
antennae. The Director poses the player every frame and residents in three groups.

This directory does not import or modify the existing aquarium. Its generators,
scripts, asset files and standalone outputs are independent of the other agent's
fish replacement. `Taskfile.yml`, the engine, app assets and `aquarium-cd.iff` are
untouched. Menu/app integration is a separate coordinated step after both levels
are ready.

## Build and play

From the repository root:

```sh
bash wflevels/aquarium_blue_shrimp/build.sh
bash wflevels/aquarium_blue_shrimp/run.sh
```

The existing Blender exporter add-on and built Rust level tools must be installed.
The output is `wflevels/aquarium_blue_shrimp-standalone.iff`. No app bundle is
rebuilt. `SHRIMP_COUNT=1..24` includes the player; the normal build defaults to 24.

Keyboard/gamepad: arrows move across/up/down the tank, B/2 moves toward the glass,
C/3 away, and A/1 makes a backward tail-flick escape. Motion eases in and out.
Released in open water, the shrimp gently sinks to the substrate. The close-up
camera activates near the foreground grazing patch and returns to the wide view
when the player leaves it. The player is slightly larger than the residents.

`SHRIMP_PROFILE=touch` selects the two-button profile: A switches between vertical
and depth movement; B tail-flicks. Both profiles currently generate the same
standalone output path, so build the desired profile explicitly. This does not
change the first aquarium or its profile.

## Check and capture

```sh
python3 -m pytest tests/test_aquarium_blue_shrimp.py -q
python3 wflevels/aquarium_blue_shrimp/run_checks.py --video
```

The runtime check uses its own debug port, 17913, sticky injected input, a fixed
20 Hz simulation clock, and an engine process that it shuts down afterward.
It captures the actual tank, grazing close-up and tail flick, checks directional
movement and limits, and records a seven-second clip. Screenshots, the log and
results live in `docs/plans/2026-10-02-aquarium-levels-blue-shrimp/engine/`.
Use `--out /tmp/shrimp-checks` to keep evidence elsewhere.

The decorative residents have no physics bodies. Their separate lanes provide
spacing without an expensive all-pairs flocking scan. Rocks are physical; plants
and moss are visual. The player uses an invisible collision hull above its visual
feet so Jolt's predictive ground contact does not apply walking friction to it.
It can settle on the sand or authored rock-top patches after swimming above them.

## Remaining integration checks

Desktop content checks: **8 passed**. The engine checks passed movement, all six
directional limits and leaving each wall, both cameras, colony/leg motion, input
isolation and backward tail flick. The one-shrimp and touch variants loaded cleanly.

The measured desktop debug/ASan estimate is **79.7 ms/frame** after reducing each
shrimp from 1,388 to 596 triangles (previously 137.4 ms/frame). This needs release
measurement and further tuning before shipping. The motion clip is encoded from
fixed simulation steps at 20 fps; it does not demonstrate real-time frame pacing.

- [ ] Add this standalone level to the app's menu bundle after the first level's
  replacement and final display name are settled.
- [ ] Verify Android/Chromecast performance and remote navigation in that combined
  bundle, without competing with the other agent's device work.
- [ ] Verify the touch profile on a physical phone.

The current level uses opaque geometry and fog for water, consistent with the
renderer. The animation is stylized; no feeding, breeding or biological model is
implemented.
