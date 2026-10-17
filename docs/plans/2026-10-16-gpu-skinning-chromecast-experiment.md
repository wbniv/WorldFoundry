# GPU skinning on Chromecast: measured engine experiment

16 October 2026 · **Experimental engine implementation approved 17 October; worktree only.** Will separately authorized the winding cleanup discussed here on 16 October 2026; Will approved the bounded GPU experiment below on 17 October 2026, in its own worktree. GPU skinning could keep an animated mesh in a resident vertex buffer and send only joint matrices each frame. This experiment will compare that path with CPU skinning of the *same rig and poses*, then decide whether its frame-time benefit pays for new GL and Metal rendering paths and changed face culling. The [mesh deformer versus joint rig investigation](../investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md) motivates the question; its cost figures are estimates, not a GPU-skinning result.

## Existing CPU baseline — 17 October

The [six-pair seahorse comparison](2026-10-16-saltwater-seahorses/comparison.md)
records matched cast1 wide-idle measurements for None, 1, 2 and 6 pairs with the
implemented CPU `DFRM` path. Release medians are 47.14, 51.58, 55.10 and 69.26 ms
per presented frame. Use its CPU sections, upload counters, PSS, frozen hashes
and raw timestamps as the current workload reference. All variants author the
same twelve residents (two actors each); None also hides six posts. This baseline supplies
context for the spike, not the matched CPU-rig (`C`) versus GPU-rig (`G0`/`G1`)
comparison below. Cast1 close-idle/crawl are now complete on `d8d215ae`: None → six pairs
measures 47.19 → 68.52 ms in close idle and 47.33 → 68.57 ms in close crawl,
with three release repeats per count/view and separate CPU profiles. The CPU
increases are 20.67 / 20.82 ms; nested animation contributes 2.68 / 2.73 ms,
already included in update/Director. Whole-frame vertex traffic is about
5.13 → 6.66 MiB/frame, including other deformers. The existing close camera
follows the urchin; the authored crawl fixture measures controller work without
validating remote input delivery. See the comparison's
[close results and graph](2026-10-16-saltwater-seahorses/comparison.md#close-idle-and-close-crawl--completed-17-october).
Three through five pairs are interpolated estimates. Cast2 remains unavailable. GPU skinning has
not been implemented or measured by this baseline.

## Decision and scope

The decision is whether to build a production GPU path for opaque skinned meshes on the Chromecast, retain CPU skinning, or defer skinning entirely. A fish `DFRM` wave and a joint chain can be compared separately for Deformer phase 2; they are different animations, so they cannot isolate the cost of moving skinning to the GPU. The seahorse's approved Phase 1 remains on its planned CPU `DFRM` path. GPU skinning changes, including diagnostic counters, require Will's separate explicit permission under [AGENTS.md](../../AGENTS.md).

Use a disposable branch/worktree and a small rigged fixture, with no asset-format commitment or default-path change. Start with one opaque, single-material mesh with approximately 900 vertices and 35 joints, plus a tiny opaque `DOUBLE_SIDED` fixture for the culling exemption. Then scale copies of the main mesh to find the crossover. An exported 35-joint seahorse may serve as the main fixture if available; otherwise generate a repeatable test mesh and clip. Keep the same mesh topology, weights, clip, pose evaluation, lighting, camera, scene, and update rate across the CPU and GPU variants. Limit the first implementation to four influences per vertex, normalized byte weights, byte joint indices, and linear blend skinning. Record the exact layout and round-trip quantization error.

## Existing paths and design constraints

| Area | Current behavior | Experiment requirement |
|---|---|---|
| Mutable meshes | [`GetWrittableVertexList()`](../../wfsource/source/gfx/rendobj3.hp) permanently excludes the object from the GL static-mesh bake. The per-face renderer streams its deformed positions. | Keep bind-pose vertices and weights immutable; update the pose without asking for writable vertices. Retain a CPU-streamed fallback. |
| GL | [`backend_modern.cc`](../../wfsource/source/gfx/glpipeline/backend_modern.cc) has a resident static VBO, but its current record and draw interface has no skin attributes or joint palette. It uses seven vertex attributes. | Add an explicit skinned-mesh resource and draw path; do not reinterpret an ordinary static bake as a skinned mesh. Query vertex-attribute and vertex-uniform capacity, compile the GLES 3 shader on both devices, and make failure select the CPU path. Preserve GL 3.3 and WebGL 2 compilation if the common backend is changed. |
| Metal | [`backend_metal.mm`](../../wfsource/source/gfx/metal/backend_metal.mm) batches triangles into a new vertex buffer during flush and does not implement the optional static-mesh interface. | Add a resident skinned buffer, a matching MSL vertex function and palette binding, with working macOS/iOS fallback. A GL-only proof is an intermediate result, not completion of a cross-backend feature. |
| Face culling | [`WfFaceIsBackfacing()`](../../wfsource/source/gfx/backface_cull.hp) uses face normals; GL static draws build a fresh survivor index list on the CPU ([`static_mesh.cc`](../../wfsource/source/gfx/glpipeline/static_mesh.cc)). The engine does not enable `GL_CULL_FACE` for world meshes. `DOUBLE_SIDED` faces are exempt. | The rigged path must not cull from bind-pose normals or centres. Establish one front-face convention, audit each mesh eligible for GPU skinning, then test hardware face culling on its *skinned* triangles in both APIs. Keep two-sided faces uncullable. Fall back to CPU skinning for a mesh or transform that fails this contract. Count visible triangles and inspect silhouettes against the CPU reference. |
| Visibility | The room/actor render list remains on the CPU ([`level.cc`](../../wfsource/source/game/level.cc)). Any mesh-bound visibility shortcut must contain every permitted pose. | Keep existing actor visibility semantics. If a tighter mesh bound is used, derive a conservative animated bound from clip extrema and procedural limits; test that tail tips and fins never disappear at view edges. Do not read skinned vertices back from the GPU for culling. |

### Clean up winding at its sources

The [engine-wide normal migration](2026-10-16-blender-normal-convention-engine-wide.md)
defines `(v1-v0) × (v2-v0)` as the shared Blender/engine normal. The exporter
and importer preserve face order directly. Its offline manifest accounts for
528 original model hashes, including `keep` decisions and separate face groups
for two mixed meshes. The built-in cube, scarecrow, matte, test geometry and
DFRM normal calculations are covered by the source review. Exterior surfaces
point outward; an interior room or dome faces the viewer inside it.

**Migration status, 16 October 2026:** Desktop builds, exporter and deformer
checks, binary verification and the Android release build pass. Device rendering
is pending because the shared network is unavailable, and Metal rendering is
pending on an Apple host. The dome's unchanged legacy script fails to compile,
so its black-frame comparison does not prove interior rendering. See the
[evidence record](../diagnostics/blender-normal-convention/README.md). Complete
those validation gaps before treating the migration as release-ready. None of
these checks certifies every pose or mirrored transform for hardware culling.

1. Audit each mesh selected for GPU skinning, including its one-sided and `DOUBLE_SIDED` faces. Check the cooked face order against the engine normal, intended viewing side, degenerate faces, allowed poses and negative-scale transforms. Record intentional interior surfaces and exceptions explicitly.
2. Correct any failure at the generating source, then regenerate that mesh. Verify each face group's intended side before conversion. Material colour, prelit lighting, UVs, two-sided sheets and interior views have existing semantics to preserve. Use the shared Blender-order normal rule for direct geometry and exported meshes.
3. Validate the selected rig in bind pose, maximum bend, interior/exterior views and mirrored transforms. Compare software-cull and hardware-cull results and GL and Metal screenshots. Keep exporter and built-in geometry regression checks as guards for future assets.

Keep the current software cull for ordinary meshes. Replacing it engine-wide would require a separate audit of **every distinct rendered mesh asset** used by shipped levels, plus procedural draw paths and transform variants; deduplicate shared assets rather than inspecting each level instance by hand. The 18-level single-frame sweep is a useful regression check, not that audit. A no-cull GPU variant is useful to measure an upper bound on CPU savings, but it cannot pass the visual or production gate by itself. Preserve material order, palette, fog, alpha-cutout, lighting and context-loss behavior in any path proposed for use beyond the opaque fixture. Translucent skinned meshes stay on the CPU path until sorting has its own design and tests.

## Concrete engine proposal — approved 17 October

This section defines the requested engine edits. It is based on a read-only
source review at `69517e7d`; Will explicitly approved this experimental scope on 17 October 2026: “approved in worktree, ofc”. Work in
an isolated worktree (proposal checkout: `gpu-skinning-proposal`), retain the CPU default, and keep
the experimental changes off the integration branch until separately reviewed.

### 1. Separate the pose from moving vertices

[`DfrmEvaluator::Evaluate`](../../wfsource/source/renderassets/dfrm_deform.cc#L241)
currently does clips, knots, wrap, limits, forward kinematics, vertex placement,
face normals and write-backs in one call. Split it into a common pose stage and
an optional CPU materialization stage. The common stage must still calculate
the wrap centre, tip, clamped status and world-vertical lead-in. It publishes a
complete pose atomically; invalid input retains the previous valid pose and
outputs. CPU `Evaluate` remains the reference wrapper around both stages.

Add an optional GPU-pose hook to `MeshDeformer`, unsupported by default. Only
`DfrmDeformer` opts in. In [`RenderActor3D::Deform`](../../wfsource/source/renderassets/rendacto.cc#L576),
try that hook before requesting writable vertices. Successful GPU posing must
never call `GetWrittableVertexList()` or `GetWritableFaceList()` each frame:
both currently mark an object as deformed, and the latter is also called by
`DfrmDeformer::Bind`. Add const bind-data access and retain the existing CPU
route for the five species deformers. A rejected or unsupported GPU draw must
materialize the **current** pose on the CPU before streaming it, without
advancing the behavior or clip a second time.

**Preserve DFRM's actual math.** In
[`dfrm_deform.cc:394`](../../wfsource/source/renderassets/dfrm_deform.cc#L394),
a transform's weight multiplies its **angle**. Half the head rotation is not
a 50/50 blend of identity and full rotation. The current seahorse authors a
half-weight neck in `seahorse.py`'s `HEAD` table. Build an in-memory palette
entry for each distinct `(transform, angle-weight)` used by the loaded mesh,
plus identity and the curve samples. Each such vertex then has one full-weight
palette binding. For curve vertices, derive the bind point from DFRM's stored
local offsets and rest frame, so the shader reproduces its placement formula
rather than silently substituting differently rounded mesh coordinates.
Audit the loaded chunks to establish the actual palette size; do not infer
it from the nominal 35 tail joints.

The [read-only fixture preflight](2026-10-16-gpu-skinning-chromecast-experiment/preflight.json)
records both body hashes and matches them to the
[reviewed normal-migration exports](../diagnostics/blender-normal-convention/integration-seahorse-source-review.json).
Each body has 868 vertices, 1,027 faces, one opaque lit single-sided material,
no native handles, no degenerate rest faces, **32 faces spanning bindings**,
and **40 proposed palette entries** (identity, 35 samples, head at half/full
angle, two eyes). This is a rest/source preflight, not a posed-winding or GPU
render certificate. Reproduce it from the repository root with:

```sh
python3 docs/plans/2026-10-16-gpu-skinning-chromecast-experiment/audit_fixture.py --revision 69517e7d
```

This adapter changes neither the DFRM file format nor the seahorse's
choreography. The separate four-influence fixture uses conventional linear
blend skinning in both its CPU and GPU references. Its result must not be
reported as a measured replacement for DFRM unless the seahorse adapter also
passes parity.

### 2. Add a small optional renderer seam

Add `RBSkinnedMeshHandle` and optional support/create/live/destroy/draw methods
beside the static-mesh methods in
[`renderer_backend.hp`](../../wfsource/source/gfx/renderer_backend.hp).
Defaults report unsupported, preserving headless and other backend builds.
The draw contract takes a palette snapshot, an immutable material run and a
cull mode. Flush pending streamed or static triangles before an immediate
skinned draw; do not retain a pointer to mutable actor pose data for later use.

The experiment's bind representation is:

- An affine palette of **at most 48 entries**, each three float4 rows (48
  bytes). Both backends and the CPU fixture use the same row layout and
  multiplication convention. An over-capacity mesh selects the CPU path.
- A face-expanded, immutable vertex buffer retaining the existing seven
  attributes plus four byte joint indices and four normalized byte weights
  at locations 7 and 8. No cross-face vertex sharing: material colors and UV
  seams retain their current interpretation. Byte weights sum to 255; CPU
  comparison uses these same decoded weights and separately reports error
  against any original float weights.
- Immutable, contiguous material runs in existing face order. Use triangle-list
  range draws, so there is **no per-frame survivor-index upload**. Culling is
  a draw-state decision, not a CPU-generated index list.
- One backend resource per render object initially, with retained CPU bind
  data for reconstruction. Measure that duplication honestly; a new global
  mesh cache and instancing are outside this experiment. Material, UV/atlas or
  geometry changes invalidate the resource. Keep each instance's pose private.

Insert `RenderSkinned` before `RenderStatic` in
[`glpipeline/rendobj3.cc`](../../wfsource/source/gfx/glpipeline/rendobj3.cc#L51),
which is the shared submission path used by the GL and Metal backends. A GPU
skin is not an E3 static bake: it must not enter `RenderStatic`, its cached
plane-distance cull, its survivor list, or its rest-triangle check mode.
`static_mesh.cc` and its existing culling behavior need no change.

Select modes at startup through a proposed `--gpu-skinning=cpu|gpu-no-cull|gpu`
argument in `game/main.cc`, usable in frozen APK `wf_args.txt` as well as desktop
launches. Default `cpu`; log requested and effective mode and every fallback
reason. The four-weight synthetic fixture gets a test-only entry point, not
a new public skeleton format, Forth API or seventh production deformer kind.

### 3. Implement GL and Metal siblings

| Backend | Required edit | Resource and failure behavior |
|---|---|---|
| GL/GLES/WebGL2, `glpipeline/backend_modern.cc` | Add a dedicated skinned VAO/program, byte index/weight attributes, and a joint-palette uniform upload. Skin bind positions in the vertex shader. Draw immutable material ranges directly. | Check attribute, varying and vertex/fragment uniform capacity and shader linkage. At the 48-entry cap the palette alone is 144 float4 vectors; also budget matrices and lighting. Upload only the **used** entries (48 bytes each) per actor draw. Shader or allocation failure returns unsupported and draws the current CPU pose. Follow `OnSurfaceLost()` generation/liveness rules; never delete an old-context GL name in a new context. |
| Metal, `metal/backend_metal.mm` | Add matching MSL skinning and material pipeline variants, a resident bind `MTLBuffer`, and per-draw palette binding. This bypasses `Flush()`'s fresh vertex-buffer allocation for eligible draws. | A 48-entry palette is 2,304 bytes: use a separate copied `setVertexBytes` binding, within Apple's 4 KB limit. Retain resident resources until queued commands finish. Keep the existing command-buffer completion policy. On a missing encoder, failed pipeline or allocation, report the condition and retain/retry the ordinary path rather than declaring a successful GPU draw. |

Preserve the existing texture, palette, prelit, ambient/directional light,
fog and depth behavior. The first eligible material class is fully opaque
and has no alpha cutout. Seahorse fins stay on their existing CPU fin deformer;
translucent sorting is not part of this change. Continue compiling the common
GL backend for GLES 3.0, desktop GL 3.3 and WebGL2; add no unguarded newer API.

**Flat normals need an explicit solution.** The current DFRM evaluator rotates
normals for rigid faces but recomputes a cross product for faces spanning
different bindings. Blending a rest normal by one vertex's weights would
change that lighting. For the experiment, pass posed eye-space position to a
dedicated skinned fragment shader and derive the geometric face normal from
screen-space derivatives (`dFdx`/`dFdy` in GLSL, `dfdx`/`dfdy` in MSL). Correct
its sign using front-facing state and a backend orientation calibration so a
two-sided back face keeps its **authored winding normal**, not an automatic
face-toward-camera normal. Apply the existing Lambert lighting there; retain
the existing vertex fog calculation using the posed position. Evaluate
derivatives before any nonuniform branch or discard; their behavior is not
defined inside nonuniform control flow by the
[GLSL ES 3.00 specification](https://registry.khronos.org/OpenGL/specs/es/3.0/GLSL_ES_Specification_3.00.pdf).

This avoids a second CPU vertex/face walk and a normal upload, while retaining
flat shading on mixed-binding triangles. It moves lighting work to fragments,
which may cost more GPU time: count that cost in the result. Test against the
current stored-normal lighting, including its fixed-point rounding. Eligible
faces must have geometric normals consistent with their reviewed stored
normals and remain nondegenerate throughout the tested pose envelope. The CPU
evaluator's rule of retaining the previous normal on a degenerate face is not
reproduced by derivatives; such a mesh/pose class fails eligibility. Do not
claim universal DFRM support from seven successful pose presets.

### 4. Change culling only for eligible skin draws

The engine reference remains Blender's `(v1-v0) × (v2-v0)`. Ordinary meshes keep
their software test. Metal currently has a handwritten copy of that test in
`DrawTriangle`; GL uses `WfFaceIsBackfacing`. Neither should receive bind-pose
vertices/normals for a GPU-skinned draw.

- `gpu-no-cull` (`G0`) submits all selected skin faces with hardware culling
  off. This is diagnostic only. Compare it with a fixture-local CPU no-cull
  control (`C0`), rather than misattributing removal of CPU culling to vertex
  skinning. Do not disable culling globally for the rest of the aquarium.
- `gpu` (`G1`) uses back-face hardware culling for audited one-sided material
  runs. For `DOUBLE_SIDED`, use no hardware cull. Keep material-run order.
  Start with `GL_CCW` / `MTLWindingCounterClockwise`, verify their visible side
  with a known triangle under each backend's real projection/viewport, and
  make the derivative-normal sign agree with that calibration.
- GL explicitly sets/restores `GL_CULL_FACE`, back-cull selection and front
  winding around skin draws. Metal explicitly sets `setCullMode` and
  `setFrontFacingWinding`; reset to the ordinary no-hardware-cull policy before
  streamed geometry, matte, text or overlays, including on a new encoder.
- Initially accept only finite rotations with positive uniform scale.
  Mirrored, singular or nonuniform transforms select the CPU fallback.
  Exercise those cases to verify the fallback, not to claim GPU support.
- Preserve the CPU room/render-list and `actor->isVisible()` decisions in
  [`Level::RenderScene`](../../wfsource/source/game/level.cc#L1396), including
  the current-room render scope. This proposal adds **no new frustum test**
  and needs no `level.cc` edit. Never use a rest bounding box as a new skin
  rejection shortcut. Validate tail tips at view edges; leave collision,
  picking and gameplay coordinates on their existing CPU representations.

The native `GetHandle` API can read an arbitrary CPU vertex. Meshes with native
handles stay on CPU for this experiment; silently returning a bind vertex is
unacceptable.
The seahorse's mailbox wrap/tip outputs still come from the common pose stage.

### 5. Instrument and prove this exact change

Append counters/sections in `game/runtime_profile.hp`; preserve all existing
counter indices and log field meanings. Separate common pose, CPU vertex
materialization, CPU face-normal work, software culling, and skin submission
CPU time. Keep nested times out of additive totals. Add skin-specific vertex,
index and palette upload bytes, draw/face submission counts, fallback counts,
GPU/CPU resident bytes and rebuild counts. Sample resident gauges once per
frame; instrument GL and Metal consistently. Hardware-rejected face counts are
**unavailable** unless actually queried: submitted faces are not surviving
faces. Do not label CPU timers as GPU duration. Keep all resource creation and
warm-up uploads separate from steady-state traffic.

Expected implementation file surface (names for new files are provisional):

| Files | Purpose |
|---|---|
| `wfsource/source/renderassets/dfrm_deform.{h,cc}` | Common pose, CPU materialization, exact palette adapter and atomic outputs |
| `wfsource/source/renderassets/mesh_deformer.{h,cc}`, `rendacto.{hp,cc}` | Optional GPU hook, eligibility and current-pose CPU fallback |
| `wfsource/source/gfx/rendobj3.{hp,hpi,cc}` | Const bind access, resource ownership, invalidation and handle eligibility |
| `wfsource/source/gfx/renderer_backend.hp`, new `gfx/skinned_mesh.{hp,cc}`, `gfx/glpipeline/rendobj3.cc` | Optional backend seam, material runs, draw routing and mode selection |
| `wfsource/source/gfx/glpipeline/backend_modern.cc`, `gfx/metal/backend_metal.mm` | Resident resources, GLSL/MSL shaders, cull state and lifecycle |
| `wfsource/source/game/main.cc`, `runtime_profile.hp` | Startup switch and appended measurements |
| `CMakeLists.txt`, `tests/dfrm_strand.cc`, new skinning math/GL/Metal fixtures | Test registration, pose parity, rendering and lifetime tests |
| New fixture/build/analysis scripts, this plan's evidence directory | Reproducible rig, frozen APK variants, coordinator manifests and result tables |

Before device timing, run existing DFRM and deformer-golden tests, then compare
the old CPU evaluator, refactored CPU evaluator and GPU adapter on the actual
female and male chunks. Include half-weight neck, all clips/crossfades, maximum
bends, wrap/grasp/release, world rotation, head/eyes, invalid input, independent
instances and current-pose fallback. Preserve the existing `1e-4` CPU reference
tolerance; report shader position/normal errors, including fixed-point
conversion, instead of promising bit-identical rasterization. Compare images
with identical light/fog and declared edge tolerances; missing faces, holes,
changed silhouettes or broad shading changes fail. Include a mixed-binding
triangle and both sides of the two-sided fixture in each backend.

Lifecycle tests must draw an ordinary streamed/static mesh immediately after
each skin mode to expose cull-state leaks; exercise material invalidation,
Android surface recreation, background/resume and repeated load/unload.
Compile **and render** the sibling on an Apple host. This Linux worktree cannot
establish Metal rendering parity, and an unavailable host/device is a recorded
validation gap, not a passed test.

### 6. Repeat the matched cast1 campaign after parity

Freeze a fresh CPU control and GPU candidate from the same spike revision.
The historical `d8d215ae` timings remain context; do not compare an old APK
against a new engine and call the difference skinning. Use the same meshes,
behavior, twelve allocated residents, six posts, seed 713, saltwater, plant age
150, paused growth, camera and authored crawl fixture. Record requested and
effective mode, frozen APK/asset hashes, and thermal state for every run.

- **Release timing:** `C` versus `G1`, None / 1 / 2 / 6 pairs, close-idle and
  close-crawl, three 60-second repeats after the original 15-second warm-up:
  **48 runs**. Rotate C/G1 order. The None cells are negative controls, and
  None hides posts in both modes. Keep 3 / 4 / 5-pair interpolation outside
  the measured table. Retain the close camera's head clipping and the crawl
  fixture's lack of hardware-input validation in the interpretation.
- **CPU split:** one separate profiled repeat for each mode/count/view:
  **16 runs**. Do not combine instrumented and release presentation results.
  Repeat a profile only to resolve a concrete discrepancy.
- **Diagnostic fixture:** C/C0/G0/G1 at 1 / 4 / 16 rigged actors, matching mesh
  and poses; follow the 30-second warm-up/three-repeat protocol below. This
  isolates four-weight skinning and culling costs. Keep its actor counts
  separate from aquarium pair counts. G0 needs no full population campaign
  unless it is needed to explain a failed G1 result.

Build/freeze locally, then use `task chromecast:*` for each complete session
on `chromecast-test-01`. Save comparison data and coordinator evidence under
`docs/diagnostics/` and link them from this plan. Restore the selector release
through the same coordinator-owned session. No raw ADB or recurring device
permission request is needed. Queue/reservations still apply. Cast2 gets the
same verification when available; no availability or Apple parity is assumed.

Apply the existing acceptance gate below. Record cast1 results even if Metal
or cast2 remains unavailable, explicitly mark those gaps, and retain the CPU
default. Only after tests, update
[`2026-10-16-mesh-deformers-vs-joint-rigs`](../investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md)
with measured savings/costs, culling and lighting findings, memory, fallback
coverage and the crossover. A successful cast1 result alone does not authorize
a production default or merging the experimental engine changes. Clean build
artifacts and the experiment worktree after the reviewed changes are merged;
keep the frozen evidence and final report.

### Approval record

Will supplied the explicit engine permission required by `AGENTS.md` on 17 October 2026.
The approved scope is the bounded **experimental** surface above: DFRM pose split
and exact adapter; optional skin resource/draw seam; GL and Metal shaders,
buffers and local cull state; CPU fallback and profiling; fixtures and matched
cast1 tests. Existing CPU defaults, public asset formats, ordinary-mesh culling
and global visibility policy stay as specified. Implementation and ordinary
coordinator testing are authorized under that approval. Merging
the spike or selecting a production GPU default requires a later decision.

API references for the proposed paths:
[Khronos vertex attribute specification](https://wikis.khronos.org/opengl/Vertex_Specification),
[OpenGL ES reference registry](https://registry.khronos.org/OpenGL-Refpages/),
[Apple palette-byte binding](https://developer.apple.com/documentation/metal/mtlrendercommandencoder/setvertexbytes(_:length:index:)),
[Apple front-face selection](https://developer.apple.com/documentation/metal/mtlrendercommandencoder/setfrontfacing(_:)),
[Metal shading language specification](https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf).

## Experiment sequence

1. **Freeze the reference.** Choose a reproducible scene and rig with rigid and four-weight regions, a turning body, an edge-on pose, and the largest permitted bend. Save mesh/clip hashes, pose samples and a CPU skinning reference. Validate bind pose, joint indices, weight sums, inverse bind transforms and the CPU results before adding a shader.
2. **Validate the rig's winding.** Audit the fixture and any additional meshes proposed for GPU skinning, fix their source if needed, and record intentional inward and two-sided surfaces. Complete the normal migration's pending render checks for the selected fixtures; record unrelated migration validation gaps separately. Ordinary meshes stay on software culling.
3. **Instrument the cost.** For identical frames, count CPU pose time, CPU vertex skin time, face-cull time, render submission time, vertex upload bytes, index upload bytes, palette upload bytes, draw calls, submitted/culled faces, resident GPU/CPU bytes and resource rebuilds. Measure presented intervals separately from thread CPU time; isolate shader/GPU duration only where a supported timer gives a trustworthy result. Existing [`runtime_profile.hp`](../../wfsource/source/game/runtime_profile.hp) counters provide part of this, but do not separate rig-specific uploads or GPU time.
4. **Build three selectable paths.** `C`: CPU skin + streamed draw, the correctness and cost reference. `G0`: immutable GPU bind-pose buffer + joint palette + GPU skinning, with back-face culling disabled as a diagnostic. `G1`: the same GPU path with hardware face culling after the fixture passes the winding audit above, including the `DOUBLE_SIDED` exemption. All three evaluate the same CPU joint matrices and draw the same opaque mesh. Keep ordinary meshes on their current path and use an explicit diagnostic switch so tests can alternate variants without rebuilding assets.
5. **Prove visual and lifecycle parity.** Compare deterministic screenshots and short recordings of bind pose, maximum bend, turn, near/edge-on view, two-sided detail, light and fog changes. Check finite positions/normals, seams, silhouettes, missing faces and back-face bleed. On Android, exercise surface loss/recreation and app resume; on Apple, compile and render the Metal sibling. Measure or explicitly mark unavailable each backend's resident-buffer behavior. A shader that compiles without a real draw is insufficient.
6. **Run paired device profiles.** Freeze one APK per candidate and baseline, then use the shared coordinator on `chromecast-test-01` and `chromecast-test-02`. Respect queue/reservations and save full job evidence under this plan's `evidence/` directory. In a fixed aquarium camera and lighting scene, profile 1, 4 and 16 rigged actors at the same pose rate; add a smaller and larger mesh only if the 900-vertex result does not identify a crossover. Warm for 30 seconds, capture three 60-second repeats per variant and device, and rotate variant order. Record display refresh, thermal state, app/build and asset hashes, and the uninstrumented presentation trace. Use a separate instrumented repeat for the CPU split. Include held and released directional input while the animated actor is visible, especially on cast2.
7. **Decide from a comparison table.** Report per-device and per-population median and run range for p50/p95/p99 presented interval, missed-refresh share, render/pose/skin/cull CPU ms, measured GPU ms if available, bytes uploaded per frame, draw counts and resident memory. Compare `G1` to `C`; use `G0` only to explain culling overhead. Report the fixed cost at one actor and the crossover, not just the best high-population case. Keep the earlier `DFRM` and fish-deformer timings as context with their different animation costs clearly identified.
8. **Update the rig investigation after testing.** Revise [2026-10-16-mesh-deformers-vs-joint-rigs.md](../investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md) with the measured Chromecast results, winding cleanup and culling findings, Metal findings, crossover, and decision. Replace or clearly qualify its GPU cost estimates and link the comparison and raw evidence. State how the findings affect its joint-rig recommendation and Deformer phase 2 timing.

## Acceptance gate

Adopt GPU skinning for an eligible class of meshes only if `G1` has visual and lifecycle parity on both rendering backends, a reliable CPU fallback, the winding cleanup and validation above are complete for that asset class, and it produces a repeatable improvement on the workload that will use it. The proposed performance gate is at least **10% lower median main-thread render-section CPU time** for the skinned workload on both Chromecasts, with no reproducible p95 presented-interval or missed-refresh regression beyond the run-to-run spread, and no GPU-time or memory increase that erases the frame-time gain or exceeds the available memory budget. Treat these thresholds as a decision rule for the experiment, not an expected result. If a timer is unavailable, do not claim a GPU-time result; use the presentation and CPU evidence, and state that GPU saturation remains unmeasured.

If `G0` helps but `G1` does not, investigate culling/index work once before widening scope. If only 16 actors benefit, keep CPU skinning for sparse scenes and record the measured crossover. If a correct culling path, Metal parity, or acceptable GPU cost cannot be achieved within this bounded experiment, stop the spike and retain the CPU path. No rig format, renderer default, or Deformer phase 2 choice follows automatically from a single-device speedup.

## Review package and permission boundary

Before GPU skinning engine edits, request explicit permission for the proposed surface: the `RenderObject3D`/renderer-backend skinned resource seam, GL and Metal shaders and buffer ownership, culling/visibility handling, and profiling counters. Present the fixture winding report, fallback, test matrix and expected file list with that request. The three cited winding paths have separate authorization; this plan alone authorizes no further engine work.

After the experiment, retain the frozen APK hashes, source revision/diff, capabilities, raw traces, screenshots, Apple render evidence and a short comparison in this plan's `evidence/` directory. Make a separate production proposal if the gate passes; the spike itself does not authorize merging its engine changes.

## Implementation log

17 October: isolated worktree `gpu-skinning-proposal`, base `69517e7d`.
The pose-only palette and late CPU materialization pass 320 poses per exported
male/female mesh (640 total), including clips, wrap and the half-angle neck.
Maximum palette position error is 1.1920929e-7 model units; CPU fallback
positions, normals and mailbox outputs are identical to the complete evaluator.
No GPU timing or rendering parity is established by this math check.

The implementation additionally forwards the optional seam through the existing
`CompositingBackend` in `glpipeline/backend_factory.cc`. `static_mesh.cc` gets
only an atlas-generation getter and the skin-memory gauge call; its culling and
static-bake paths retain their behavior. Sample-local bind points map directly
through each ring's affine palette entry, algebraically cancelling the proposed
rest-frame/inverse-rest-frame conversion and preserving the stored offsets.

Coordinator availability checked 17 October: both casts report ready, with
other sessions currently owning them. Cast2 is therefore eligible for queued
verification once the frozen candidate is ready; the earlier unavailable status
is historical. Respect the existing queue rather than taking either session.

The optional diagnostic `cpu-no-cull` supplies C0 for isolating software culling
on DFRM objects only. Ordinary object culling is unchanged in every mode.
GPU eligibility now includes a one-time geometry certificate: rigid faces
remain nondegenerate; mixed faces must use weights of one axial transform and
pass a conservative area lower bound across its entire clamped angle interval.
Other mixed bindings fall back to CPU. Both exported bodies pass this check;
a deliberately collapsing test face is rejected. This preserves the CPU
previous-normal rule without a per-frame CPU face walk. Across the 640 pose
samples, minimum triangle double area is 0.000210811384 and maximum normalized
face-normal component difference is 7.16000795e-6.
