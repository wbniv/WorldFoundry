# Marble Madness: Practice in real 3D

An independent standalone WorldFoundry conversion of the **Practice collision surface**, with a playable timed race. Built directly from the arcade terrain sampler, without the old WF course geometry or Blender conversion scripts. The other five courses are not implemented.

## Play

From this checkout:

```sh
task run-marble-3d
```

Arrow keys apply camera-relative acceleration. Countersteer to brake; momentum and downhill acceleration matter. Space restarts the 60-second race. Cross between the checkered flags to finish. Falling returns to the start while the timer continues. Escape exits.

The checked-in `marble-madness-3d-standalone.iff` needs this branch's built `engine/wf_game`. It is independent of the shipped level selector and `cd.iff`.

## Rebuild and verify

```sh
task build
task tools-build
python3 wflevels/marble-madness-3d/build.py
python3 wflevels/marble-madness-3d/verify_geometry.py
```

The level compiler needs built Rust `iffcomp`, `levcomp`, and `textile` under `wftools/*-rs/target/release/`. `build.py --tools-root /path/to/another/checkout` can reuse existing tool binaries. The verified local build used `--tools-root /home/will/WorldFoundry-wbniv`. No Blender, npm, or ROM is required to rebuild from the checked-in sample data.

`verify_runtime.py --output-dir /tmp/mm3d-evidence` runs an input-only complete race, then forced fall, restart, timeout and deadline/goal precedence checks. It also checks the **presented X window**, before and after a one-shot screenshot, for the reported whole-content flicker. Run it on a private, otherwise empty X display; it needs Pillow. For example, with Xvfb already running on `:97`:

```sh
DISPLAY=:97 python3 wflevels/marble-madness-3d/verify_runtime.py --output-dir /tmp/mm3d-evidence
```

Use a new output directory for each run. The presentation check requires both pre- and post-capture samples. See the [plan and captured evidence](../../docs/plans/2026-09-21-marble-madness-true-3d-reimplementation.md).

## What the data actually means

The earlier research's `0x1DEC0` table is an **object-spawn rectangle dispatch table**, not a terrain descriptor table. Its supposed three heights include object coordinates and script arguments. It cannot be used to reconstruct a course. That correction is based on the arcade consumer routine `0x12DFA`, documented by [Marble Love](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/packages/engine/src/script-rect-dispatch-12dfa.ts).

The actual level pointer table is `0x2BE00`; Practice's header is `0x2BEE2`. `extract.py` interprets the consumer at `0x1CABA`: the packed collision map in playfield RAM selects terrain codes, row bases supply elevations, direct records provide four samples, and encoded/indirect records select slope or void samples. It resolves the protected ROM bank and runtime indirect table. The split-triangle interpolation at `0x1CC62` establishes the diagonal and corner order.

The original local ROM was unavailable. The extraction used the [Internet Archive preservation entry](https://archive.org/details/arcade_marble), with the Marble Madness set 1 and Atari System 1 BIOS archives. **ROM archives and the decoded program image are not included here.** `practice.json` records the archive SHA-256 and capture frame. With your ROM directory containing `marble.zip` and `atarisy1.zip`, extraction can be repeated with MAME:

```sh
python3 wflevels/marble-madness-3d/extract.py --rom-dir /path/to/roms --output /tmp/practice.json
```

The capture boots a fresh Practice game, records 251 live terrain queries, and saves the collision state at frame 600. Those live queries mostly exercise the starting area; they are not 251 distinct course locations. A separate check compared all 16 outputs of 2,675 legal neighborhoods across the course against Marble Love's instruction-level implementation, with zero mismatches; an additional check covered all 1,823 retained cells. The committed interpolation fixtures exercise 20 solid sample points and 12 void sample points from that independent implementation.

Source research: [level header](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/docs/level-header-format.md), [terrain sampler](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/packages/engine/src/sub-1caba-tile-redraw.ts), [height interpolation](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/packages/engine/src/sprite-project-1cc62.ts). The adapted decoding semantics are attributed under [the upstream MIT license](THIRD_PARTY_LICENSE.txt).

## Geometry, camera and physics

- 1,823 nonempty native cells produce 3,502 top triangles. A native cell is eight arcade XY units and one WF unit. Native XY are swapped into WF XY; native spawn `(136,136)` becomes WF `(0,0)`.
- Heights use `(native_height - 16384) * sqrt(2/3) / 8`. This matches the arcade's 2:1 ground-grid projection at a 30-degree camera elevation in the orthographic limit. The actual WF camera uses perspective (60-degree vertical FOV), at a fixed `(20,20,16.32993)` offset from the marble. Authored CamShot FOV is currently ignored by the engine.
- The cell diagonal and heights are retained. A triangle with a zero/void corner is omitted; no surface bridges the pits. Native height discontinuities remain discontinuities. Exposed edges receive authored vertical skirts down to Z=-9. Topology contains 4,818 triangles including these skirts.
- The renderer and Jolt consume the same mesh. The marble uses the existing `MarbleHandler` and a Jolt `CharacterVirtual` sphere of radius 0.48: momentum, surface-projected gravity and collision against actual triangles. This is not an angular rigid-body simulation, and the marble mesh does not visually rotate.
- zForth owns the race. Actor 3 is the marble. Global mailboxes 2–7 hold the deadline/state/respawn/restart edge; 70/71/73 hold score/time/falls. Reserved mailboxes 1770/1771 opt into the Linux debug-build HUD. State values: 0 disabled/uninitialized, 1 racing, 2 finished, 3 timeout. Finish markers use the recovered object-script positions `(72,64)` and `(72,68)` in native cells; the standalone finish trigger crosses WF Y=55 between them.

## Fidelity limits

Practice's static collision heights and split-triangle surface are the verified part. This is **not a pixel- or behavior-exact arcade port**. Textures, skirt depth/colors, flags, lighting and HUD are newly authored. Collision samples have the arcade's finite cell resolution; they do not recover decorative overhangs or the original tile artwork. Frame-600 dynamic terrain is frozen. Physics constants, timer/score behavior and fall recovery are standalone choices, not a port of the 68000 movement/race routines. There is no trackball integration, sound, tutorial animation, multiplayer, or arcade transition sequence. Beginner, Intermediate, Aerial, Silly and Ultimate have not been attempted.

The only shared-engine changes are an opt-in race HUD and a screenshot-presentation fix: every offscreen frame must be blitted before swapping, even when no screenshot is being written. Both are separate from course physics.
