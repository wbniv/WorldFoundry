# Fish assets: research, model, texture and swimming

This guide takes an individual fish from a brief to a reviewable World Foundry asset. It covers research, model, texture, palette variants, motion, plans and previews. It does not prescribe a tank or a level. The examples illustrate existing approaches, not a universal fish implementation. For level and runtime details use [Level Building](../level-building.md) and [Troubleshooting](../level-design-troubleshooting.md).

## 1. Establish the subject and research record

1. Confirm the fish, the intended visual style and whether the target is a wild species, a named ornamental strain, or an invented interpretation. Common names can cover many species. Resolve a mismatch before building.
2. Find a clear side photograph and, if possible, front, top, oblique and moving references of the same form. Prefer scientific descriptions, museum collections and primary research for anatomy and measurements; use clearly credited photographs and video for appearance and motion. Do not assume a similar fish has the same proportions or fin movement.
3. Record the source URL, author, title, date, taxon or strain, view, and what it supports. Record reuse license, attribution, license URL, share-alike and modification obligations before copying an image into the project. A photo may be consulted as a reference without assuming that it can be redistributed or turned into a texture. Credit generated and adapted assets accurately; do not label an AI concept, vector sketch or Blender render a photograph or engine capture.
4. Record measurements with their definitions and source. **Standard length** ends at the caudal-fin base; **total length** includes the tail. Distinguish body depth from overall height including fins. Normalize a useful dimension (for example TL = 1) and choose a model scale separately. Mark every estimate, stylization and missing view; never invent specimen measurements from an oblique photo. A labelled vector side/front guide is useful, but an estimated front view is not evidence of measured thickness.
5. For swimming, find evidence for fin use, body stiffness, tail beat, turn and braking. If quantitative data is unavailable, label tuning as a game approximation and compare it with footage. Specify which motions matter at the intended camera distance.

**Record facts separately from decisions.** For example: “the source reports a 15–20 cm total length” and “we model a 17 cm fish” are different statements. Taxonomy and aquarium strain names can be contested; link a source and avoid claiming that a recolored image represents a named strain without evidence.

## 2. Write the plan and establish a visual target

Save a dated plan in `docs/plans/` before building. Include the goal, chosen subject and sources, scope, dimensions and coordinate convention, asset/rig design, texture approach, planned variants, integration boundary, deliverables, acceptance checks and explicit unknowns. Identify sketches as sketches and keep them separate from evidence of the built asset. Include the requested poster if applicable: page size, content, editable source, print PDF, preview, citations and reproduction instructions.

Produce a reference board and side/front/oblique silhouette guide early. A side-on scientific photo helps with silhouette; a single side photo cannot prove width. Compare the actual geometry to the reference before adding visual polish. Capture the actual exported model from the same views at the same scale. A plausible color pattern cannot rescue the wrong fish shape.

### Plan template

Copy and adapt the following rather than treating the example values as facts:

```markdown
# <fish> — asset and motion
Date: <date> · Status: proposed / in progress / verified

## Brief
Subject and identification: <species, strain or stylised interpretation>
Use and scope: <standalone asset, target camera and intended integration>
Out of scope: <decisions not requested>

## References and permissions
| Reference | What it establishes | View / measurements | Author, license, attribution, changes |
|---|---|---|---|
| <link> | <fact or visual reference> | <side/front/video; SL or TL> | <terms, or reference only> |

## Design and dimensions
Coordinate axes, units, rest pose and origin: <...>
Measured dimensions and sources: <...>
Estimated modelling dimensions: <...>
Geometry and fin groups, triangle/material targets: <...>

## Texture and variants
Source, license and required attribution: <...>
UV convention, texture/page sizes, material and color space: <...>
Shared index map / palette table and number of colorways: <...>
Separate pattern families, if explicitly requested: <...>

## Motion and controls
Existing primitives and actor ownership: <...>
Idle, cruise, turn, braking, inputs and recovery: <...>
Fin attachments and deformation weights: <...>

## Deliverables and verification
- [ ] Editable sources, deterministic builds and credits.
- [ ] Side, front and oblique actual-model renders and palette contact sheet.
- [ ] Cooked desktop engine captures; validate UV orientation, fin roots and motion.
- [ ] Relevant tests, performance/device evidence where applicable.
- [ ] <poster and print checks, if requested>

## Evidence and outstanding work
<Paths, commands, versions, results, limitations and remaining checks>
```

## 3. Model the fish

Choose a reference-led silhouette and dimensions before choosing a polygon count. Document axes, origin, physical units and any project scale conversion. Aquarium fish commonly face +X with +Z up, but follow the chosen asset pipeline. Build a true three-dimensional body; inspect head-on thickness, both flanks, the gill cover, mouth, tail base and all paired fins. The [arowana example](../../wflevels/aquarium_tanks/arowana.py) uses separate anatomical groups; the [goby example](../../wflevels/aquarium_tanks/goby.py) uses a body and fins with a shared span. These are examples, not templates to stretch into another species.

Decide the motion architecture before merging parts. Independent pectoral strokes need distinct deformation weights or separately pivoted geometry. Roots must follow body deformation and the complete root transform during yaw, pitch, bank and turning. A separate mesh at a fixed world coordinate is not a rig. Avoid tiny or degenerate triangles, overlapping opposite faces that cause artifacts, inconsistent winding, unintended holes and unstable pivots. Inspect rest, maximum bend and turns from both sides. See [mesh normals and culling](../level-design-troubleshooting.md#mesh-face-normals--backface-culling).

Maintain editable source, reproducible generation/export commands and actual triangle, vertex, material and actor counts. A polygon target is a starting budget, not a guarantee of performance. Profile representative populations and views before making claims about cost.

For a school, measure the full intended fish count with deformation enabled. Each animated instance can consume its own mesh and room memory even when the source asset is shared; test the cooked level for allocation failures. If a tank-only simplified mesh is needed, retain the high-detail source and texture, inspect silhouette and UVs in the cooked view, and record the actual geometry budget and device results. Do not trade away required fin motion without making that limitation visible.

## 4. Texture, UVs and palette variants

Choose a source that resolves at the fish's actual on-screen size. If adapting a photograph, align the head, eye, gill cover and fins to the mesh, remove or mask background, and check both flanks. A photographed pectoral fin baked into the flank will remain visible when a separate fin moves. Build separate UV islands and texture detail where needed instead of projecting the same flank photograph onto every fin. Check seams, mirrored features, padding and close views. Texture resolution alone does not improve an unsuitable pattern or mesh.

For the documented World Foundry textured Blender path, UV V is authored from the **top** of the atlas, while the Blender preview requires a preview-only vertical flip. Validate distinctive colors at the top and bottom in the **cooked engine**, not merely in Blender. Choose texture size, textile page size and host VRAM slot dimensions together; see [Textured Blender assets](../level-building.md#textured-blender-assets-atlas-and-runtime-checks) and [the texture troubleshooting entry](../level-design-troubleshooting.md#textured-asset-looks-correct-in-blender-but-colors-change-in-world-foundry). Check the final host configuration as well as desktop. Avoid assuming a larger source image fits in the old page or that a desktop slot override is present on Android.

For **palette-only** colorways, create one indexed master or equivalent immutable region/index map and a deterministic palette manifest. Export the engine-required formats from it. Every variant must keep dimensions, UVs, geometry, pattern and alpha identical; only index-to-color mappings change. Verify pixel indices byte-for-byte and compare generated RGB/TGA pixels against the intended palette. Inspect every variant at matched lighting, framing and scale. A global hue shift can change eyes and fin accents as well as skin; check the result against references rather than naming it as a real strain. If the user requests spots, stripes or other different patterns, make **separate pattern families**, each with its own master and palette-only variants; do not describe changing pattern as a palette change.

Record the source image and transformation, attribution and license alongside each family. Share-alike obligations can apply to adapted textures; retain source and identify which outputs are derivatives. Use descriptive colorway names and distinguish artistic variants from documented species and strains.

## 5. Build the swimming rig

Start by inspecting existing fish assets and scripts; reuse available actor composition, mailboxes and deformers where suitable. Engine investigation is read-only. **World Foundry engine edits require discussion and explicit permission**, even when a level, asset or plan is authorized. If an existing primitive cannot achieve a required behavior, document the limitation and propose the specific engine change before editing it.

- Define rest pose, local head/tail axis, common deformation span, units and actor/mesh ownership. Keep span coordinates consistent with any exported scale.
- Define behavior as states and transitions appropriate to the fish: idle, acceleration, cruise, steering/turn, brake and recovery as needed. Inputs should request motion; set speed, frequency, amplitude and turn response from evidence or mark them as tuning assumptions. Clear held input on relevant lifecycle transitions. Avoid frame-rate-dependent integration; bound large time steps.
- Implement the head/body/tail motion and independently driven fins with suitable root attachment. `swim-deform` is an existing primitive with a body wave and an optional fin wave. In the [goby asset](../../wflevels/aquarium_tanks/goby.py), fin UV V encodes root-to-tip distance for that fin wave; ordinary photographic UVs do **not** automatically supply valid fin weights. Use appropriate authored data or another supported rig mechanism. A whole-mesh wave with fin amplitude zero is not an independent-fin rig.
- Verify coordinate transforms, pivots and left/right pairing while steering and pitching, not only at rest. Check that the fins follow their bent roots and never remain world-fixed. A painted fin in the photo is not independently animated geometry.
- Test input press, hold, release and opposite-direction transitions, acceleration/braking, turns and limits. Check trajectories, frame-rate variation, clipping and animation continuity, and distinguish in-place fin animation from actual steering and translation. Record assertions and actual captures; visible pixel changes alone prove neither plausible locomotion nor correct attachment.

The [discus prototype](../../wflevels/discus_asset/README.md) demonstrates an existing body-wave call and palette generation, but explicitly does **not** establish independent fins or steering. Do not copy its status as if those features were done.

## 6. Preview, export and verify

Keep a small review scene and label every image by provenance: **concept**, **source/Blender render**, **cooked desktop engine**, or **device capture**. Make a contact sheet at consistent camera, size, light and pose; identify the selected texture and pattern family. Capture front, side, oblique, close and normal-distance views of the exported model, plus representative motion poses and a playable clip. Show maximum bends and fin roots. A static contact sheet cannot verify motion. Record camera, build/commit or local revision, asset hash, commands, configuration, and date so results can be reproduced.

Use the standard Blender exporter, level compiler and texture cook for an engine review, then run the actual engine and inspect the result. The [Cuckoo Village asset example](../../wflevels/cuckoo_village_assets/README.md) documents an end-to-end textured review scene and runtime slot configuration. Headless Blender must use `--python-exit-code 1` so script errors fail the build. Test the cooked result with the intended rendering options; record logs and failures. Compare material/UV output and shape with the source reference and check motion in the fish region rather than relying on an FPS overlay or unrelated changes.

Before installing a new level on a device, run its cooked standalone level in the desktop engine and inspect startup, rendering and representative movement, including press, hold and release. Run the assembled app's menu and screensaver paths on desktop where supported, and record the commands and results. Unit tests, a successful build and a Blender preview do not replace this run. If the desktop check fails or cannot be run, leave device installation pending and report the blocker.

When applicable, freeze the APK before using the shared Chromecast coordinator. Follow the repository's device instructions, queue and reservations; capture and profile the owned session and record its job and evidence. No raw-device fallback is allowed. Record desktop evidence and device evidence separately; a desktop capture is not a device performance result. If there is no runnable device integration, report it as unverified.

When a profiling run includes menu navigation or loading, the overall FPS includes those screens. Capture the selected tank and calculate frame intervals for a documented steady-state segment after it has loaded; report duration, FPS and a frame-time percentile, not just an overall average. Keep the APK hash and compare variants under the same workload. A fixed-timestep video encoded at a chosen frame rate demonstrates motion, not real-time performance. Device installation, launcher verification, gameplay and the screensaver are separate outcomes; report each one actually checked.

### Preview and evidence template

```markdown
## <fish> review — <date>
Asset revision / hash: <...> · Build: <command, host, renderer>
Subject / reference: <link> · Model / texture licenses: <link or path>
Scale / orientation / texture page and slots: <...>

| View | Artifact | Provenance | What to inspect | Result / limitation |
|---|---|---|---|---|
| Side, front, oblique | <links> | Blender / desktop engine / device | silhouette, thickness, seams | <...> |
| Matched palettes | <link> | <...> | same geometry, pattern, alpha | <...> |
| Swim and turn | <clip and frames> | <...> | fin roots, head/tail, press/hold/release | <...> |
| Runtime profile | <receipt> | <device, build> | frame time, memory, duration | <...> |

Known issues: <...>
Tests and commands: <...>
Not yet verified: <...>
```

Do not mark the asset complete merely because it exports, the preview looks good, or one motion frame changes. Close each acceptance item with evidence or leave it explicitly open.

## 7. Finish the Aquarium integration

When the fish is being made for a new Aquarium level, completing the level includes adding it to the combined app and its screensaver. Do this after the level and its movement are ready; a standalone review scene alone does not finish the tank.

1. Build the playable standalone level and append it to `wflevels/aquarium-menu.manifest`, preserving existing indices. Add its build task and any species roster entry. Follow the [chooser and screensaver guide](combine-levels-chooser-and-screensaver-launch.md) for the package wiring.
2. Provide and register a screensaver driver if the player needs automatic movement, then rebuild the menu and screensaver bundles and the Aquarium APK. The manifest, menu bundle, screensaver bundle and packaged `levels.manifest` must agree on the level and its position.
3. Verify the new choice launches from the app menu and through the screensaver, including its movement and relevant controls. Freeze the APK and use the shared coordinator for device installs and tests; record the build and evidence. Include the rebuilt committed outputs with the source changes. Report any build or device verification that remains open.
