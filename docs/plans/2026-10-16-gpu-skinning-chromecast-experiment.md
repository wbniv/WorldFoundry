# GPU skinning on Chromecast: measured engine experiment

16 October 2026 · **Plan for review.** Will separately authorized the winding cleanup discussed here on 16 October 2026; GPU skinning engine work still needs its own explicit permission. GPU skinning could keep an animated mesh in a resident vertex buffer and send only joint matrices each frame. This experiment will compare that path with CPU skinning of the *same rig and poses*, then decide whether its frame-time benefit pays for new GL and Metal rendering paths and changed face culling. The [mesh deformer versus joint rig investigation](../investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md) motivates the question; its cost figures are estimates, not a GPU-skinning result.

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

## Experiment sequence

1. **Freeze the reference.** Choose a reproducible scene and rig with rigid and four-weight regions, a turning body, an edge-on pose, and the largest permitted bend. Save mesh/clip hashes, pose samples and a CPU skinning reference. Validate bind pose, joint indices, weight sums, inverse bind transforms and the CPU results before adding a shader.
2. **Validate the rig's winding.** Audit the fixture and any additional meshes proposed for GPU skinning, fix their source if needed, and record intentional inward and two-sided surfaces. Complete the normal migration's pending render checks. Ordinary meshes stay on software culling.
3. **Instrument the cost.** For identical frames, count CPU pose time, CPU vertex skin time, face-cull time, render submission time, vertex upload bytes, index upload bytes, palette upload bytes, draw calls, submitted/culled faces, resident GPU/CPU bytes and resource rebuilds. Measure presented intervals separately from thread CPU time; isolate shader/GPU duration only where a supported timer gives a trustworthy result. Existing [`runtime_profile.hp`](../../wfsource/source/game/runtime_profile.hp) counters provide part of this, but do not separate rig-specific uploads or GPU time.
4. **Build three selectable paths.** `C`: CPU skin + streamed draw, the correctness and cost reference. `G0`: immutable GPU bind-pose buffer + joint palette + GPU skinning, with back-face culling disabled as a diagnostic. `G1`: the same GPU path with hardware face culling after the fixture passes the winding audit above, including the `DOUBLE_SIDED` exemption. All three evaluate the same CPU joint matrices and draw the same opaque mesh. Keep ordinary meshes on their current path and use an explicit diagnostic switch so tests can alternate variants without rebuilding assets.
5. **Prove visual and lifecycle parity.** Compare deterministic screenshots and short recordings of bind pose, maximum bend, turn, near/edge-on view, two-sided detail, light and fog changes. Check finite positions/normals, seams, silhouettes, missing faces and back-face bleed. On Android, exercise surface loss/recreation and app resume; on Apple, compile and render the Metal sibling. Measure or explicitly mark unavailable each backend's resident-buffer behavior. A shader that compiles without a real draw is insufficient.
6. **Run paired device profiles.** Freeze one APK per candidate and baseline, then use the shared coordinator on `chromecast-test-01` and `chromecast-test-02`. Respect queue/reservations and save full job evidence under this plan's `evidence/` directory. In a fixed aquarium camera and lighting scene, profile 1, 4 and 16 rigged actors at the same pose rate; add a smaller and larger mesh only if the 900-vertex result does not identify a crossover. Warm for 30 seconds, capture three 60-second repeats per variant and device, and rotate variant order. Record display refresh, thermal state, app/build and asset hashes, and the uninstrumented presentation trace. Use a separate instrumented repeat for the CPU split. Include held and released directional input while the animated actor is visible, especially on cast2.
7. **Decide from a comparison table.** Report per-device and per-population median and run range for p50/p95/p99 presented interval, missed-refresh share, render/pose/skin/cull CPU ms, measured GPU ms if available, bytes uploaded per frame, draw counts and resident memory. Compare `G1` to `C`; use `G0` only to explain culling overhead. Report the fixed cost at one actor and the crossover, not just the best high-population case. Keep the earlier `DFRM` and fish-deformer timings as context with their different animation costs clearly identified.
8. **Update the rig investigation after testing.** Revise [2026-10-16-mesh-deformers-vs-joint-rigs.md](../investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md) with the measured Chromecast results, winding cleanup and culling findings, Metal findings, crossover, and decision. Replace or clearly qualify its GPU cost estimates and link the comparison and raw evidence. State how the findings affect its joint-rig recommendation and Deformer phase 2 timing.

## Acceptance gate

Adopt GPU skinning for an eligible class of meshes only if `G1` has visual and lifecycle parity on both rendering backends, a reliable CPU fallback, the winding cleanup and validation above are complete for that asset class, and it produces a repeatable improvement on the workload that will use it. The proposed performance gate is at least **10% lower median render-thread CPU time** for the skinned workload on both Chromecasts, with no reproducible p95 presented-interval or missed-refresh regression beyond the run-to-run spread, and no GPU-time or memory increase that erases the frame-time gain or exceeds the available memory budget. Treat these thresholds as a decision rule for the experiment, not an expected result. If a timer is unavailable, do not claim a GPU-time result; use the presentation and CPU evidence, and state that GPU saturation remains unmeasured.

If `G0` helps but `G1` does not, investigate culling/index work once before widening scope. If only 16 actors benefit, keep CPU skinning for sparse scenes and record the measured crossover. If a correct culling path, Metal parity, or acceptable GPU cost cannot be achieved within this bounded experiment, stop the spike and retain the CPU path. No rig format, renderer default, or Deformer phase 2 choice follows automatically from a single-device speedup.

## Review package and permission boundary

Before GPU skinning engine edits, request explicit permission for the proposed surface: the `RenderObject3D`/renderer-backend skinned resource seam, GL and Metal shaders and buffer ownership, culling/visibility handling, and profiling counters. Present the fixture winding report, fallback, test matrix and expected file list with that request. The three cited winding paths have separate authorization; this plan alone authorizes no further engine work.

After the experiment, retain the frozen APK hashes, source revision/diff, capabilities, raw traces, screenshots, Apple render evidence and a short comparison in this plan's `evidence/` directory. Make a separate production proposal if the gate passes; the spike itself does not authorize merging its engine changes.
