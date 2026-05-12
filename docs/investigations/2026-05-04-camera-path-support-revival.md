# Camera path support — what the engine has, what was deleted, what's needed

**Date:** 2026-05-04
**Context:** While planning the Q✱bert intro cinematic
([docs/plans/2026-05-04-qbert-intro-camera-sweep.md](../plans/2026-05-04-qbert-intro-camera-sweep.md), planned but not
yet filed under that name — see `~/.claude/plans/elegant-gliding-glacier.md`),
the question came up: instead of approximating a curved sweep with a
chain of `CamShot` keyframes, can we attach the camera to a Blender
**curve / spline** and let the engine traverse it? This investigation
captures what the engine actually supports today, what existed at one
point and was deleted, and what would need to land for a Blender-
authored curved camera path to work.

## TL;DR

- **Engine has runtime path-following infrastructure** —
  `MOBILITY_PATH` is a real mobility class (`actor.cc:108` registers
  `thePathHandler`); `wfsource/source/movement/movepath.cc`
  implements the per-tick traversal; `wfsource/source/anim/channel.cc`
  has a working `LinearChannel::Value()` that lerps between keyframe
  pairs.
- **The original 3DS Max exporter wrote per-axis animation channels**
  (`wfmaxplugins/max2lvl/path.cc` + `channel.cc`, deleted in commit
  `c5761ca` "purge"). It accepted Bezier / TCB / Linear curves at
  authoring time but **only exported the keyframe values, not the
  tangents** — so even with the full original toolchain, the runtime
  rendered piecewise-linear motion through the keys.
- **The current Blender exporter (`wftools/wf_blender/`) has zero
  curve/channel-write code.** No `bpy.types.Curve` handling, no
  per-axis channel emission. So even though the engine could *consume*
  a path today, nothing in the authoring pipeline emits one.
- **A camera-on-path hook is commented out** at `camera.cc:51`:
  `// _path = NEW(PathPoint(origPos, Euler()));` — needs uncommenting
  + connecting through the actor's `Mobility` field to actually drive
  the gameplay camera from a path.
- **Net** — there is no "free" Blender → spline-camera pipeline. The
  chained-CamShot approach (5–6 keyframe shots, `Pan Time In Seconds`
  approximating ease-in-out) gets the same fundamental visual quality
  as a path-based approach would *with the existing channel encoding*
  (piecewise-linear), and ships in a few hours instead of a few days.

## Engine surface — what's still in tree

### Mobility = Path

`wfsource/source/movement/movepath.cc` is the per-tick path traversal
handler. Key behaviours:

- Reads `_movementData->AtEndOfPath` (enum: `Ping-Pong | Stop |
  Jumpback | Delete | Derail | WarpBack`, definitions at
  `wfsource/source/anim/path.hp:47`).
- The `WARPBACK` variant is "jumpback **without** interpolated
  collision box" — the existing comment confirms collision-box
  interpolation between waypoints is part of the model.

`actor.cc:108` registers `thePathHandler` for `MOBILITY_PATH`, so any
actor whose movement block has `Mobility = "Path"` (per the OAS enum
`Anchored | Physics | Path | Camera | Follow`) will be driven by it.

### Channel storage

`wfsource/source/anim/channel.cc` defines two channel-decoding
classes:

- `LinearChannel::Value(time)` — `lerp(keyBelow, keyAbove,
  pct)`. Works fine; at `channel.cc:71`. This is a piecewise-linear
  interpolator over a sorted array of `(time, value)` pairs.
- `ConstantChannel::Value(_, _)` — returns the single stored value
  regardless of time. For static channels.

The on-disk channel format (`_ChannelOnDisk` in `channel.hp`) has only
two compressor types: `LINEAR_COMPRESSION` and `CONSTANT_COMPRESSION`.
**No spline-segment encoding** — there is no place in the format to
store Bezier in/out tangents or TCB tension/continuity/bias values.

### Camera-on-path stub

`wfsource/source/game/camera.cc:51` contains the commented-out line:

```cc
// _path = NEW(PathPoint(origPos, Euler()));
```

…suggesting the camera was at one point set up to consume a `PathPoint`
at construction, but that hook was disabled. Re-enabling it (plus
ensuring the `Camera` actor's OAD block can be set to `Mobility=Path`
and reference the path index) is part of "make camera-on-path work."

### Build status

`wfsource/source/anim/GNUmakefile` was deleted in commit `e2dcc98`
("cleanup: Batch 7 — PSX/Win artifacts, OpusMake Makefiles, platform
guards"). The `.cc` and `.hp` files in `wfsource/source/anim/` are
still present, so the source survives — but it's no longer in the
active build. Whether `LinearChannel::Value()` is currently compiled
into `wf_game` is uncertain; if it is (via some catch-all directory
scan in `engine/build_game.sh`), great, otherwise the engine work
includes restoring the build wiring.

## What the original 3DS Max exporter did

Files (deleted in commit `c5761ca` "purge"):
- `wfmaxplugins/max2lvl/path.cc` (278 LOC) — `QPath` class, `AddPositionKey()` / `AddRotationKey()`.
- `wfmaxplugins/max2lvl/channel.cc` (176 LOC) — exporter-side `Channel` class with `LINEAR_COMPRESSION` / `CONSTANT_COMPRESSION` selection, key sorting, IFF chunk write.
- `wfmaxplugins/max2lvl/level.cc:231` — "PATH CODE STARTS HERE" — sampled keyframes from each Max scene node's `TMController`.

The key extraction loop (recovered from `git show c5761ca^:wfmaxplugins/max2lvl/level.cc`):

```cc
posControl = thisNode->GetTMController()->GetPositionController();
numPosKeys = posControl->NumKeys();

for (int keyIndex = 0; keyIndex < numPosKeys; keyIndex++) {
    keyTime = posControl->GetKeyTime(keyIndex);
    posInterface->GetKey(keyIndex, (IKey*)thisPosKey);
    switch( posControl->ClassID().PartA() ) {
        case LININTERP_POSITION_CLASS_ID:
            tempPosition = ((ILinPoint3Key*)thisPosKey)->val;
            break;
        case TCBINTERP_POSITION_CLASS_ID:
            tempPosition = ((ITCBPoint3Key*)thisPosKey)->val;
            break;
        case HYBRIDINTERP_POSITION_CLASS_ID:   // Bezier
            tempPosition = ((IBezPoint3Key*)thisPosKey)->val;
            break;
        default:
            AssertMessageBox(0, "Path contains unknown key types");
    }
    tempPath.AddPositionKey(keyTime, tempPosition);
}
```

**Critical observation:** for all three Max curve types — Linear, TCB,
Bezier — the exporter only reads `->val` (the keyframe position
value). It does **not** read TCB t/c/b parameters or Bezier in/out
tangents. So curved Max splines were sampled at the keyframe times
only and exported as a flat `(time, value)` list, which the runtime
then re-interpolated **linearly** between successive keys.

Authoring a smooth curve in Max therefore relied on:
1. The Max user setting many closely-spaced keyframes manually, or
2. Accepting piecewise-linear motion at runtime regardless of what the
   Max viewport showed.

Same fundamental constraint applies to any Blender pipeline that
emits the same Channel format.

## What's needed for Blender → curved camera path

To make a Blender-drawn Bezier curve drive the gameplay camera at
runtime, even if the on-wire representation stays piecewise-linear:

### Authoring side (`wftools/wf_blender/`)

1. **Detect Blender curve objects.** `obj.type == 'CURVE'` and
   `obj.data` is a `bpy.types.Curve` with `splines[i]` containing
   Bezier or NURBS control points.
2. **Sample the curve densely.** For a smooth-looking piecewise-linear
   render at 60 Hz, 1 sample per frame over the camera-traverse
   duration is ample. e.g. for a 4 s sweep, 240 samples. Use
   `curve.evaluate()` or build a temp mesh evaluator.
3. **Emit per-axis Channel chunks** in the level binary. The Channel
   IFF format from `wfmaxplugins/max2lvl/channel.cc` is the reference;
   per-position-axis (X/Y/Z) and per-rotation-axis (EulerA/B/C)
   channels with `LINEAR_COMPRESSION`.
4. **Wire the path index** onto the consuming actor (the camera) by
   setting its OAD block's path reference field. Format details in the
   deleted `level.cc::CreateQObjectFromSceneNode()` and `level.cc:122`
   `QLevel::AddPath()`.
5. **Set the camera's mobility** to `Path` via the OAD `Mobility`
   enum.

The Channel-emission code is genuinely new work in the Rust pipeline
(`wftools/levcomp-rs` / `wftools/iffcomp-rs`) — neither tool currently
knows about path or channel chunks. The deleted C++ Channel code is a
useful reference but doesn't port directly.

### Engine side

1. **Re-enable the camera-on-path hook** at `camera.cc:51`. Verify
   `PathHandler` correctly drives the camera's transform when
   `Mobility = Path`.
2. **Confirm/restore the anim subsystem build.** If
   `wfsource/source/anim/*.cc` files aren't being compiled (because
   the old `GNUmakefile` was removed), add them to `engine/build_game.sh`
   or the equivalent build path.
3. **Test runtime channel decoding** against a synthetic level with a
   known-good path — `mm_practice` and `qbert_practice` don't
   currently use any path-mobility actors, so this hasn't been
   exercised in the modern build.

### Optional — true smooth splines

If piecewise-linear-with-many-samples isn't visually smooth enough at
the eye's distance from the camera, the engine + format would need:

- A new `BEZIER_COMPRESSION` channel type with in/out tangents per
  key.
- A new `BezierChannel::Value()` evaluator (~30 LOC of Hermite
  interpolation).
- The Blender exporter would emit fewer keyframes (one per Bezier
  control point) plus tangents, instead of dense-sampled linear keys.

This is genuinely more work but produces a *truly* smooth curve at any
zoom level. The dense-linear approach is good enough for cinematic
moves where the camera doesn't dwell on any single curve point long
enough for the segmenting to read.

## Effort estimate

Rough sizing for "Blender curve drives camera in WF" with the dense-
linear approach:

| Component | Effort | Notes |
|---|---|---|
| Blender curve sampler in `wf_blender/` | 0.5 day | `curve.evaluate()` + bake to (time, x/y/z, rotA/B/C) keys. |
| Channel chunk writer in `levcomp-rs` (Rust) | 1 day | Port the deleted `channel.cc` save logic; both `LINEAR_COMPRESSION` and `CONSTANT_COMPRESSION` paths. |
| Path chunk writer (assembly of channels into a path) | 0.5 day | `PathBasePosition`, `PathBaseRotation`, channel iter loop. |
| Camera-on-path engine plumbing | 0.5 day | Uncomment + wire `camera.cc:51`; verify `PathHandler` drives the camera transform; confirm anim build. |
| Verification level (synthetic curve, watch the camera traverse it) | 0.5 day | New tiny test level; bridge dump of camera position over time. |
| **Total** | **~3 days** | Plus ~1 day of slop for unknowns in the levcomp pipeline. |

For comparison, the chained-CamShot intro that ships with the Q✱bert
work is **~1 evening** (5 keyframe shots, 30 lines of Forth, no
exporter or engine work).

## Recommendation

Ship the chained-CamShot intro now (it's not throwaway — even with
full path support, you'd still want CamShots for static framing
shots). Treat path-camera support as a separate, bounded ~3-day
deliverable that benefits *every* future level, not just Q✱bert.

Pick it up if either of these triggers:
- The chained-CamShot intro looks too "stair-stepped" once tuned and
  tweaking pan times can't smooth it out.
- A second cinematic scene is planned (Coily reveal, level-clear
  swoop, etc.) — at that point the per-cinematic content cost of
  chained CamShots overtakes the one-time engineering cost of path
  support.

## Reference points

- Engine: `wfsource/source/anim/channel.cc:71` `LinearChannel::Value`
- Engine: `wfsource/source/anim/path.hp:47` `AtEndOfPathOptions` enum
- Engine: `wfsource/source/movement/movepath.cc` (per-tick traversal)
- Engine: `wfsource/source/game/actor.cc:108`
  (`{MOBILITY_PATH, &thePathHandler}` registration)
- Engine: `wfsource/source/game/camera.cc:51` (commented-out
  `PathPoint` hook)
- Deleted exporter: `git show c5761ca^:wfmaxplugins/max2lvl/path.cc`
  (278 LOC)
- Deleted exporter: `git show c5761ca^:wfmaxplugins/max2lvl/channel.cc`
  (176 LOC)
- Deleted exporter: `git show c5761ca^:wfmaxplugins/max2lvl/level.cc`
  (specifically lines 231–340: "PATH CODE STARTS HERE" key extraction)
- Build artifact missing: `wfsource/source/anim/GNUmakefile` (deleted
  in `e2dcc98`)
- Worked example of chained-CamShot approach (sister approach to
  paths): `wflevels/qbert_practice/blender_create_qbert.py`
  (intro state machine in `DIRECTOR_SCRIPT`).
