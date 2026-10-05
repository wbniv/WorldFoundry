# Approved engine scope: lionfish rig and palette integration

Permission granted: Will replied “implement” to the concrete proposal, then
“go ahead” to the separate debug-bridge fix. The scope remains this rig/palette
integration and the discussed command-initialization/bounds fix. The standing
AGENTS.md engine-permission rule still applies to future engine changes.

The authoring asset is one mesh with 13 dorsal spines, named head/jaw/body/fin
regions, shared surface UVs, three palette definitions and shape-key studies.
It includes shared 256² grayscale/detail maps, Blender previews and a separate
tested Forth suction helper. The asset now runs in the game; these linked images remain Blender
pose studies rather than device captures. [Hover preview](assets/hover.png), [travel](assets/travel.png),
[gulp study](assets/gulp.png), [editable Blender asset](assets/lionfish.blend).

## Why the approved extensions were required

Existing `RenderActor3D::SetFinDeformation` reads the texture UV channel as fin
weights and only deforms one fin-style geometry. `SetFishDeformation` similarly
uses an entire-mesh body wave. Their caches explicitly exclude simultaneous
fin/body deformation. Neither can selectively pose skull, jaw, throat, two
pectoral fins and tail in one actor. `SetAnimationCycle` is empty, so the Blender
shape keys are not a working exported animation path.

The renderer already supports translucent material opacity; retain it. The
shared grayscale texture needs palette remapping (dark/light role colors),
which differs from a uniform tint. The current exporter supports a directly
connected image but cannot serialize Blender's palette ColorRamp as a runtime
material. Therefore a rendered Blender preview does not establish runtime
palette support. No recolored per-fish textures will be substituted.

## Approved engine changes

1. Add an **optional, versioned model rig chunk** carrying per-exported-vertex
   region ID, bend weight and authored root/pivot, independent of texture UVs.
   Validate counts, finite values and region bounds; models without the chunk
   retain their existing behavior. The Blender exporter must map metadata
   through triangulation/UV seam duplication; it is tooling, not engine code.
2. Add a lionfish rest-vertex cache and pose operation covering small skull/jaw
   rotations, throat expansion, mouth protrusion, folded spines and curved fin
   tips. Extend `renderassets/rendacto.hp/.cc`, a new isolated `lionfish_deform.h`,
   and model loading in `gfx/rendobj3.hp/.cc`. Keep immutable rest data and
   independent per-actor pose state; reuse the existing dynamic vertex upload.
3. Add an explicitly flagged **per-instance dark/light palette mapping** for
   the shared texture sample. Carry palette state through the render actor and
   material submission; extend the relevant desktop/GLES/WebGL material paths
   in `gfx/glpipeline/`. Preserve translucency and lighting; unflagged materials
   take the original path. Include a working legacy fallback or state its
   platform limitation for review before changing support policy.
4. Expose one bounded pose/palette operation to the existing zForth adapter in
   `engine/stubs/scripting_zforth.cc`. Publish once per fish, without new
   per-ray actors or a mailbox per vertex. The feeding Director remains the
   single writer for prey movement/capture; suction remains level-script code.

Implementation now uses LRIG v1: uint32 version/count, then region ID plus
16.16 weight and pivot XYZ per exported vertex (20 bytes). Region IDs are
trunk, head, jaw, left/right pectoral, tail, dorsal, anal, pelvic and spines.
`lion-pose` consumes phase, drive, turn, gape, packed dark/light colors and actor
index (syscall 177). Palette materials opt into flag 64. The compositor retains
palette state through sorting. Linux/GLES/WebGL and Metal paths have matching
material mapping; Apple runtime verification is not available on this host.
Palette endpoints are per-vertex GPU attributes so depth-interleaved fins
share batches. The compositor skips replaying unchanged lighting/fog on a
palette-only switch. No physics-engine changes, new rigid bodies, fluid solver
or global animation rewrite were made. Modern desktop/GLES paths are verified;
WebGL and Metal source paths are updated but were not runtime tested here. The
retired legacy fixed-function renderer does not implement this palette shader.

## Review and verification

Test missing/malformed rig chunks, UV-seam metadata mapping, rest-pose recovery,
independent fish poses/palettes and non-lionfish rendering. Compare deterministic
poses in desktop and both Chromecasts. Test flow/capture/miss behavior separately
from fin rendering and preserve generation checks. Profile the new runtime
against the recorded baseline, including script/native/render time where
available, actor/draw counts and uploaded texture memory. Cast2 baseline runs
show mixed 30/60 Hz cadence, so comparisons must include all runs and matched
cadence rather than claim a clean improvement from one median.

Without engine permission, authoring assets and script prototypes can continue,
but the one-actor combined rig and palette-remapped runtime material cannot be
reported implemented. A multipart/tinted approximation would be a different
scope and requires an explicit decision rather than silent substitution.
