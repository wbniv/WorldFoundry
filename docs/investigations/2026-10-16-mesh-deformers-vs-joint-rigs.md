# Mesh deformers or joint rigs?

16 October 2026 · **Investigation, for a decision by Will.** This compares the implemented generic mesh deformer (the [seahorse plan](../plans/2026-10-16-saltwater-seahorses.md), Phase 1) with **joint rigs**: a skeleton of joints, per-vertex skin weights and joint animation clips. No code changes. Numbers marked *est.* are estimates; the rest cite the source or a measurement.

## The question

Until now World Foundry has animated meshes in two ways: five per-species C++ deformers (fish, fin, swim, jelly, lion), and rigid actors posed one by one from Forth. It has no skeleton, no skinning and no parenting ([clownfish plan, M5–M7](../plans/2026-09-30-clownfish-idle-animation.md)). Phase 1 of the seahorse plan added:

- **one generic deformer slot** per actor (`MeshDeformer`), with the five existing kinds moved behind it and golden-tested;
- **`DFRM` v1**, a data-driven deformer with two operators. The *rooted curve* drives the 35-joint tail; *weighted transforms* drive head and eyes. Both play pre-animated clips, and the curve adds runtime contact (gripping a post).

A **joint rig** is the standard alternative in game engines:
- a **tree** of joints with a bind pose;
- each vertex weighted to up to four joints (linear blend skinning);
- clips of joint rotations and translations;
- blending and inverse kinematics (IK);
- **sockets** where other objects attach to a joint.

Which should World Foundry's animated meshes use, now and later?

## Short answer

1. **They are not opposites.** `DFRM`'s rooted curve *is* a joint chain in which every vertex follows exactly one joint. A weighted transform is a one-joint skin group. A joint rig is the general case: branching trees, blended influences at bends, and sockets.
2. **Keep the implemented Phase 1 design.** The seahorse needs a chain, clips and contact, and `DFRM` gives all three with the smallest engine change. One cheap design choice keeps the door open: make the evaluator's per-joint **frames** an explicit intermediate result, separate from vertex placement. A later skinning deformer can then reuse the pose stage instead of rebuilding it.
3. **Joint rigs earn their cost with the first consumer that needs any of:**
    - a branching skeleton (limbs, legs, fingers, the anemone's crown);
    - soft skin that blends two or more joints at a bend;
    - sockets, so one actor can ride on another's joint;
    - importing rigged models (Blender armatures, glTF skins).

   Among today's animals only the parked sea anemone needs one of these: a tree of 48 tentacles on a contracting disc.
4. **Deformer phase 2 should not start before a joint-rig spike.** That phase re-expresses fish, fin, swim, lion and jelly as `DFRM` operators. The same bodies could instead be joint chains driven by procedural wave generators, which is how most engines animate fish. A short spike, measured on Chromecast, should decide which representation D6 uses.
5. **GPU skinning is the one place a rig could be clearly cheaper on the Chromecast.** It keeps vertices in static buffers and drops the per-frame upload. It touches both render backends and the CPU culling path, so it needs its own [measured experiment](../plans/2026-10-16-gpu-skinning-chromecast-experiment.md).

## How each works

```mermaid
flowchart LR
    subgraph D[Mesh deformer: DFRM]
      direction LR
      DC[control block<br/>clips, knots, wrap] --> DO[operators<br/>curve · transform · wave]
      DO --> DF[per-sample frames]
      DF --> DV[vertex positions<br/>CPU, rigid per sample]
      DV --> DS[streamed draw<br/>every frame]
    end
    subgraph R[Joint rig]
      direction LR
      RC[clips + procedural<br/>+ IK targets] --> RP[joint local poses]
      RP --> RM[model-space matrices<br/>down the tree]
      RM --> RK[skinning<br/>≤ 4 joints per vertex]
      RK --> RS1[CPU: streamed draw]
      RK --> RS2[GPU: static buffer<br/>+ joint uniforms]
      RM --> SO[sockets<br/>attached actors]
    end
```

The two pipelines share the middle: both compute a frame per joint (per curve sample) and then move vertices with those frames. They differ in four places:
- what produces the poses (operators versus clips, IK and procedural generators);
- how the frames are connected (chains hanging off one root, versus a tree);
- how many frames each vertex blends (one versus up to four);
- where skinning runs (CPU only, versus CPU or GPU).

## Side by side

| | Mesh deformer (`DFRM`, implemented) | Joint rig |
|---|---|---|
| Structure | Curves (chains) and transform groups, each hanging off the mesh root | A tree: any joint can have children |
| Influences per vertex | 1 (rigid per sample) or a transform weight | Up to 4, blended (linear blend skinning) |
| Procedural motion | **Native.** Operators take a few channels (phase, amplitude, wrap) and compute the pose | Needs pose generators that write joint rotations. Same maths, one more layer |
| Pre-animated clips | Curve angles per frame (3 × int16 per joint) | Joint rotation and translation tracks |
| Blending | Two clips plus an additive knot layer (Phase 1, E2) | Arbitrary layers and masks; standard |
| Contact / IK | The curve's wrap override (grip a post) | IK solvers (two-bone, chain); **Jolt has none**, so we would write them |
| Sockets / parenting | Write-backs only (wrap centre, tail tip) | Built in: any joint's matrix can place another actor |
| Authoring | Blender armature, converted by a **custom** exporter step (swing–twist into flex, lateral, twist) | Blender armature and weights export almost directly |
| Interchange | None outside World Foundry | glTF skins; the [glTF plan](../plans/2026-07-05-gltf-import-export.md) deliberately left skins out (`:115`, `:120`) |
| CPU work per vertex | ≈ 18 flops (one rotate + add), *est.* | ≈ 50 flops (four weighted matrix transforms), *est.* |
| GPU option | No: positions are produced on the CPU | Yes: skin in the vertex shader; vertices stay in static buffers |
| Bytes per vertex | ≈ 16 (sample index, kind, offset) | ≈ 8 (4 joint indices + 4 weights as bytes) |
| Bytes per joint per clip frame | 6 | 8–28 (quantised to full-float rotation + translation) |
| Existing code to reuse | The five deformers' patterns; the E0 slot | **Jolt's skeleton module**: `Skeleton`, `SkeletalAnimation::Sample`, `SkeletonPose::CalculateJointMatrices`. It is already compiled into the engine ([`Jolt.cmake:422-424`](../../engine/vendor/jolt-physics-5.5.0/Jolt/Jolt.cmake)) and so far unused |
| Testability | Pure functions on vertex arrays; bit-exact golden tests | The same, once skinning is a deformer kind |
| Engine scope | Phase 1 as approved (D1) | New chunks (skeleton, skin, clips), pose evaluation, a skinning deformer, Forth words, sockets. GPU skinning adds shaders in both backends |

## How each handles the animals we have

| Animal | With `DFRM` | With a joint rig | Better fit |
|---|---|---|---|
| Seahorse tail | One 35-sample curve, clips, wrap contact | A 35-joint chain, clips, plus an IK or curvature solver for the grip | **`DFRM`**: the contact maths is native |
| Fish body (clownfish, tiger barbs) | A travelling-wave operator over a root-to-tip weight (Deformer phase 2) | A chain of 6–10 spine joints driven by a sine generator; soft skin at each joint | Even. The rig gains import and sockets; the wave operator is cheaper and needs no joints |
| Betta fins | A wave on UV-weighted membrane rows | Many short joint chains (fin rays), or a wave generator per ray | **`DFRM`**: membranes are fields, not bones |
| Jellyfish bell | A radial operator, if one fits | Radial joints around the rim; awkward | Neither is natural; keep the species kind |
| Lionfish | Regions as transforms and waves (`LRIG` converted) | A tree: spine, jaw, pectorals, spines | **Rig**, slightly: it is already a tree with a jaw |
| Sea anemone (parked) | 48 curves rooted on a contracting disc; needs curve roots on a moving parent | A tree: disc joint → 48 tentacle chains | **Rig**: the anemone *is* a tree |
| Urchin spines | Today: 8 rigid actors. As `DFRM`: transform groups | One root, 8 spine joints | Even; either beats 8 actors |
| A walking character (none planned) | Not expressible without inventing a tree | The standard tool | **Rig** |

## What it costs on the Chromecast

**Measured current CPU baseline, 17 October:** the implemented six-pair tank,
cast1 wide idle, three 60-second release repeats per count and one separate
instrumented repeat per count, saltwater, seed 713, plant age 150, growth paused.

| Pairs | Presented frame ms | FPS | Main-thread CPU ms | Process PSS MiB |
|---:|---:|---:|---:|---:|
| 0 | 47.14 | 21.22 | 42.76 | 99.0 |
| 1 | 51.58 | 19.39 | 47.03 | 99.3 |
| 2 | 55.10 | 18.15 | 50.62 | 98.2 |
| 6 | 69.26 | 14.44 | 64.30 | 103.6 |

See the [comparison](../plans/2026-10-16-saltwater-seahorses/comparison.md) and
[raw evidence](../diagnostics/seahorse-population-cast1-20261017/README.md) for
run ranges, p95, CPU windows, counters, frozen hashes and excluded samples.
Six pairs add 22.13 ms per presented frame and 21.54 ms main-thread CPU over
None: +9.24 ms update and +12.30 ms render. Native animation contributes +2.68 ms
inside the update/Director totals; these overlapping sections are not additive.
Whole-frame vertex traffic rises from 5.12 to 6.65 MiB/frame, including plants,
fins and other geometry. Neither those bytes nor the complete render delta
are measured GPU-skinning savings.

All variants allocate the same twelve residents; None also hides the six posts.
PSS varies between repeats and cannot establish per-resident allocation cost.
**Close views completed on cast1:** three release repeats and one separate CPU
profile per population/view, source `d8d215ae`. Close idle measures 47.19 →
68.52 ms from None to six pairs (21.19 → 14.59 FPS); close crawl measures
47.33 → 68.57 ms (21.13 → 14.58 FPS). The corresponding main-thread CPU
increases are 20.67 and 20.82 ms. Their nested animation increases are
2.68 and 2.73 ms, already included in update/Director. Whole-frame vertex traffic
is about 5.13 → 6.66 MiB/frame, including other deformers. These totals are not
measured GPU-skinning savings. The existing close camera follows the urchin and
clips some seahorses; an authored held-right fixture measures crawling work,
without exercising remote input delivery. All 32 close runs passed, with thermal
status 0 and verified selector restoration. See the
[completed comparison and graph](../plans/2026-10-16-saltwater-seahorses/comparison.md#close-idle-and-close-crawl--completed-17-october)
and [raw evidence](../diagnostics/seahorse-close-cast1-20261017/README.md).
The plotted 3–5-pair values interpolate frame time between two and six pairs;
they remain estimates, separate from the four measured populations.

Cast2 was unavailable during that baseline collection. This establishes a
`DFRM` workload reference; the CPU-rig/GPU-rig comparison, crossover, Metal
validation and GPU timing still require the separate experiment. The joint-rig
and Deformer phase 2 recommendations above are unchanged by this baseline.

**Other measured context:**
- Adding the urchin's 2,680 streamed triangles cost **+3.8 ms render CPU** on Chromecast 1, and its 8 extra actors cost +0.59 ms of Director time ([urchin comparison](../plans/2026-10-05-sea-urchin-realism/comparison.md)).
- Plant drawing dominates the frame ([dense planted tank plan](../plans/2026-10-03-aquarium-dense-planted-tank.md)).
- Meshes that don't change are drawn from static buffers since 2026‑10‑08. Any CPU deformer takes its actor off that path, because it hands out writable vertices.

**Estimated, for one 900-vertex seahorse:**
- Rigid curve placement is ≈ 16,000 flops; four-joint skinning is ≈ 45,000. This arithmetic estimate alone cannot establish whether a CPU rig and `DFRM` cost the same. Both currently require streamed geometry; a matched rig experiment must measure pose evaluation, vertex placement, upload and drawing before choosing one on cost.
- **GPU skinning would remove the upload.** Both Chromecasts report a **Mali-G31 with OpenGL ES 3.2** (device logs in `docs/diagnostics/`). The modern vertex shader uses 7 attributes ([`backend_modern.cc:68-74`](../../wfsource/source/gfx/glpipeline/backend_modern.cc)), and GLES 3 guarantees at least 16, so joint indices and weights fit. Thirty-five joints as 3 × vec4 each is 105 uniform vectors, under the guaranteed 256.

**GPU skinning also has three real obstacles:**
1. Back-face culling runs on the CPU from rest-pose normals, and the static path also bakes plane distances. Skinned faces move, so those decisions go wrong. See the next section.
2. The Metal backend ([`backend_metal.mm`](../../wfsource/source/gfx/metal/backend_metal.mm)) needs the same shader change for macOS and iOS.
3. Visibility culling needs conservative bounds, because the CPU never sees the skinned positions.

## GPU skinning experiment: preliminary device evidence, 17 October

The approved experiment is implemented in its own `gpu-skinning-proposal`
worktree. It adapts the existing DFRM poses to a resident vertex buffer and
joint palette, with matching GL/GLES and Metal shaders. It does not introduce
a general skeletal authoring format or change the default CPU path.

The first matched cast1 release round passed at all four counts:

| Pairs | Idle CPU FPS | Idle GPU FPS | Crawl CPU FPS | Crawl GPU FPS |
|---:|---:|---:|---:|---:|
| None | 20.14 | 20.10 | 20.12 | 20.15 |
| 1 | 18.69 | 19.34 | 18.56 | 19.34 |
| 2 | 17.30 | 18.72 | 17.27 | 18.74 |
| 6 | 13.74 | 16.78 | 13.64 | 16.69 |

These are **single measured runs**, not final medians. The second GPU idle
round measured 16.73 FPS at six pairs. None has essentially no first-round
change; benefit grows with visible body count. Fresh CPU and GPU APKs share
the same native code and authored fixture settings. The earlier population
baseline above is context, not the matched CPU comparison.

Cast2 is now available. Its controlled 1/4/16-body study has three release
repeats per path. Median FPS is 59.92/59.94/56.79 on the ordinary CPU path and
59.89/59.91/59.92 on GPU skinning with hardware culling. At sixteen bodies,
p95 presented interval falls from 33.37 to 16.68 ms; median process PSS rises
from 67.34 to 73.89 MiB. These body-only scenes exclude fins, plants and
behaviour AI. The small cases reach the display limit; CPU cost and the
crossover still require the separate profiles.

The first cast2 G1 profile verifies zero steady vertex/index upload,
zero rebuilds and zero CPU fallbacks at all three populations. Sixteen bodies
upload 30 KiB of palettes per frame and use 3.95 MiB of resident GPU skin
buffers; median render-section CPU time is 1.24 ms across eleven contained
five-second windows. These are instrumented measurements, separate from
the release FPS above. They use the original profiling scope and are retained
as historical measurements, not a matched CPU-cost conclusion.

The initial CPU profiles are invalid for that comparison: their final queued
body upload occurred after the profiler closed, and per-face thread clocks
heavily perturbed ordinary CPU culling (about 56.8 release FPS became 19.5
instrumented FPS at sixteen bodies). Corrected profiles are being repeated
with an explicit final-batch flush and coarse CPU scopes. Isolated cull time
is unavailable; C/C0 records its net effect. The paired release FPS above is
unaffected by those profiling-only defects. Release and corrected profiling
cohorts have separate native hashes and must remain separate.

GL image comparisons pass on the actual six-pair and sixteen-body scenes.
Metal's real offscreen draw fixture also passes, including four influences,
normals, fog, culling, resource recreation and upload accounting; it is not an
Apple aquarium performance result. Both casts passed release GPU Home/resume
with surface destruction/recreation and a reused EGL context. Separate
diagnostic builds verified fresh held/released movement in all four
directions on both casts, before a later unrelated native-IME/keypad assertion
failed. The complete UI validators did not pass.

Startup reliability remains open: two cast1 GPU sessions failed during case
startup, the latest immediately after the coordinator's launch-time
Back input. No native crash record was captured; the cause is not established.
Those attempts are excluded from timing and retained as failure evidence.
Three-round release summaries, CPU profiles, measured uploads/resident memory
and the full controlled population study are still pending. No GPU timer
result or adoption decision is claimed. See the
[experiment plan and evidence](../plans/2026-10-16-gpu-skinning-chromecast-experiment.md#first-crawl-round-and-lifecycle-checks).

## Back-face culling, and why moving vertices collides with it

**17 October validation status.** The Blender normal migration passes local
builds, exporter/converter tests, DFRM engine parity and the desktop GL guards.
Its Android release APK contains the migrated assets. Cast1 aquarium captures
and the population baseline now provide rendering evidence for that workload.
Cast2 and Metal experiment rendering evidence are now available as described
above; the legacy dome script failure remains open. The
[GPU skinning experiment](../plans/2026-10-16-gpu-skinning-chromecast-experiment.md)
has preliminary measurements; the complete performance gate remains pending.

**How culling works today.**
- **Where:** The default CPU path does not enable `GL_CULL_FACE`; the GPU experiment enables it only for eligible skinned draws. The engine now derives face normals from Blender's `(v1−v0)×(v2−v0)` order; checked-in meshes, the built-in cube and the matte have been migrated with their intended visible sides reviewed ([normal-convention migration](../plans/2026-10-16-blender-normal-convention-engine-wide.md)). The migration does not make hardware culling safe for all existing draws: two-sided and inside-viewed surfaces still need their material and draw behavior checked. Since 2026‑09‑21 every ordinary CPU triangle passes a **software** test, written once ([`backface_cull.hp`](../../wfsource/source/gfx/backface_cull.hp)):
  - rotate the face's stored normal into eye space;
  - move the triangle's centroid into eye space;
  - the face is back-facing when their dot product is > 0.

  A `DOUBLE_SIDED` material is exempt.
- **Where the normal comes from:** each face's normal is computed **once, when the mesh loads**, from the rest positions ([`rendobj3.cc:286`](../../wfsource/source/gfx/rendobj3.cc)). Every poly renderer then passes that stored normal to `DrawTriangle`, e.g. [`rendftl.cc:74-81`](../../wfsource/source/gfx/glpipeline/rendftl.cc). The same normal also drives the flat lighting.
- **The static path goes further.** For each material group of a baked mesh, it tests every face and writes the survivors' triangle numbers into an index list, which is uploaded for that draw ([`static_mesh.cc:773-809`](../../wfsource/source/gfx/glpipeline/static_mesh.cc)). Its fast form doesn't even read positions. It uses each face's plane distance, *normal · centroid*, which is **baked once** when the mesh is baked (`:557`).

**Why GPU skinning collides with this.** With GPU skinning the vertices move only inside the vertex shader. The CPU still holds the rest pose, so every culling decision is made for a shape that isn't on screen:
1. **Holes.** A face that was back-facing at rest but has turned toward the camera is culled. Example: the inside of a seahorse tail ring that has coiled 180°.
2. **Wasted faces.** A face that turned away is still drawn. The depth test hides it on a closed mesh, but it costs fill.
3. **Silhouette flicker.** Faces near edge-on flip between the two, frame to frame.
4. **Wrong lighting.** The vertex's packed normal (`a_normal`) is a rest normal unless the shader rotates it by the joint matrix too.

Three more parts of the static path assume fixed geometry:
- **translucent runs** are never baked; they stream through a sorted queue, which needs CPU positions;
- the bake's **check mode** compares recorded against baked triangles;
- **visibility culling** uses rest bounds.

A skinned mesh must be exempt from the first two and needs conservative bounds for the third.

**Ways out, simplest first:**
1. **Don't cull skinned meshes.** Mark their groups cull-exempt and draw the whole static index buffer. That removes the per-draw index upload too. The cost is rasterising back faces, about 2× the fragments of a closed mesh. For a 16 cm seahorse on a TV that is likely small, but it should be measured on the Mali-G31.
2. **Hardware culling only for skinned draws.** Blender-order winding is now the engine-wide reference, but this still requires reviewed outward-facing skin meshes and two-sided exemptions. The cull state has to join the backend's batch key, and Metal needs `setCullMode` too.
3. **Conservative CPU culling per joint.** Cull a joint's faces only when they face away in every pose the joint can reach. This is complex and fragile. Not recommended.

**The CPU deformers have the same problem today.** The five existing deformers move vertices but never update face normals. Their cull and lighting therefore use rest normals against deformed centroids. For a fish's small sideways sway the error is small, but a coiled seahorse tail would show holes. Two consequences:
- **`DFRM` (Phase 1):** it now rotates each deformed face's rest normal by its ring's frame every frame. Rigid per-ring binding makes that exact, at one 3 × 3 multiply per face. This was added to the plan and sent to the Phase 1 agent on 2026‑10‑16.
- **The five existing kinds:** fixing them changes their output, which would break the bit-exact golden fixtures of the E0 move. So it's a separate follow-up, with deliberately re-recorded fixtures.

A joint rig on the CPU would need the same per-face normal update. On the GPU it needs the shader-side normal rotation and one of the three options above.

## What building joint rigs would take

- **Asset chunks:** a skeleton (names, parents, inverse bind matrices), a skin (≤ 4 joint indices and weights per vertex, as bytes) and clips (quantised rotation and translation tracks). The exporter writes them from Blender armatures, beside `LRIG` and `DFRM`. glTF skins can follow through the glTF tooling.
- **Pose:** Jolt's `SkeletalAnimation::Sample` and `SkeletonPose::CalculateJointMatrices` (already compiled in), plus blending and two simple IK solvers of our own.
- **Skinning:** first as a **sixth `MeshDeformer` kind** in the E0 slot (CPU, streamed). GPU skinning is a later, measured step.
- **Sockets:** a joint matrix published to mailboxes, which the Director uses to place an attached actor. This is the pattern `DFRM` already uses for the wrap centre and tail tip. A dedicated "attached" mobility would come later, if needed.
- **Forth:** words to play and blend clips, override a joint, set an IK target and read a socket.
- **Permission:** all of this is engine work, outside D1.

The generic-deformation proposal says not to build "a full skeletal/morph system before demonstrating the need" ([proposal `:65`](../plans/2026-10-05-sea-anemone-realism/generic-deformation-proposal.md)). This document is that test. The need is **not** demonstrated for the aquarium animals; it **is** for the anemone and for any future character.

## Recommendation

1. **Phase 1: no change of direction.** Ask the in-flight agent to keep the evaluator's per-joint frames as an explicit array between "pose" and "place vertices". That costs nothing now and lets a skinning deformer reuse the pose stage later.
2. **Complete the approved GPU experiment before choosing the Deformer phase 2 renderer.** The current DFRM adapter tests resident buffers, palette upload, posed normals and culling across GL/GLES and Metal on both casts. It does not measure sampling a general Jolt skeleton or authoring a weighted Blender armature. If D6 needs those features, prepare a separate bounded skeletal spike against `fish-deform`; the current measurements alone do not choose between DFRM waves and joint chains.
3. **Make joint rigs a first-class feature when the first consumer needs a tree, soft skin, sockets or glTF import.** The sea anemone's revival is the likeliest trigger. At that point the E0 slot, the clip format and the curve's contact maths all carry over.

## Sources in this repository

- Phase 1 design, E0–E6: [seahorse plan](../plans/2026-10-16-saltwater-seahorses.md)
- Existing deformers: [`rendacto.cc:186-300`, `:675-692`](../../wfsource/source/renderassets/rendacto.cc); state in [`rendacto.hp:142-148`](../../wfsource/source/renderassets/rendacto.hp)
- The legacy vertex-animation system and why it does not apply: [`anim.cc:146-163`](../../wfsource/source/anim/anim.cc), [`animmang.cc`](../../wfsource/source/anim/animmang.cc)
- Jolt skeleton API: [`SkeletalAnimation.h:72`](../../engine/vendor/jolt-physics-5.5.0/Jolt/Skeleton/SkeletalAnimation.h), [`SkeletonPose.h:47-57`](../../engine/vendor/jolt-physics-5.5.0/Jolt/Skeleton/SkeletonPose.h), [`Skeleton.h:47-48`](../../engine/vendor/jolt-physics-5.5.0/Jolt/Skeleton/Skeleton.h)
- Generic-deformation proposal: [`generic-deformation-proposal.md`](../plans/2026-10-05-sea-anemone-realism/generic-deformation-proposal.md)
