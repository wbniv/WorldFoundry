# Anamorphic Shards — 3D clock

**Status: implementation and standalone verification in progress.** Add this clock to the shared 3D Clocks pack after its PC and Chromecast checks. On 2026‑11‑23 Will approved the normal new-level settings holder and object-registry changes; other engine changes still require explicit permission.

## Experience

A suspended mobile of opaque fragments occupies real, distinct depths. At the designated viewpoint their projections assemble the **current local time**, illustrated as 10:08 in the concept; at other viewpoints parallax breaks it into scattered fragments. The camera completes a continuous 60-second loop, reaches the precise alignment once per minute and holds for a few seconds. A separate, legible overlay displays the current time throughout. The inset is a visual comparison showing the same fragments from an off-axis view, not a second set arranged differently. Verify whether a simultaneous inset is possible with existing rendering facilities; otherwise present a truthful captured off-axis inset in review and document the limitation before proposing a runtime substitute.

## Construction

Use a canonical alignment camera and a readable digit stencil. Split each digit stroke into individually visible irregular fragments, distribute their anchor points at multiple depths, and compute each fragment’s position by back-projecting its target screen polygon through the alignment camera. Shapes must be genuinely 3D, not a single plane or a view-dependent texture. At alignment the projected fragments form the glyph, with intentional small joints that do not impair readability; off-axis capture must show disassembly from parallax. Provide depth and actor-count bounds and measure performance rather than assuming it.

Time changes must update the displayed digits using the existing wall-clock interface, including leading-zero and 12/24-hour behavior consistent with the pack. Use existing actor visibility/position mechanisms and audit mailbox capacity and material/actor budgets. Verify a minute rollover while the camera is both aligned and off-axis: the illusion and overlay must agree. No fixed 10:08 display is acceptable in the running clock.

Implement the camera path as a time-based loop, with smooth departure and arrival and an explicitly stationary 3–5 second hold at the alignment point. Derive all paths from elapsed time, avoiding cumulative drift and frame-rate-dependent movement. At minute boundaries, sync the cycle to the actual seconds if the existing time service supports it; check behavior after resume, wall-clock correction and time-zone changes. Do not assume elapsed scene time is wall time.

## Work and acceptance

- [ ] Inspect the live clocks package, catalog, shared settings, wall-clock and overlay APIs and baseline toolkit. Preserve current uncommitted work; avoid competing package manifests.
- [ ] Generate a reference-led visual review: alignment and off-axis views of the **same** 3D scene, depth diagram, and camera loop. Label concepts versus actual engine captures.
- [ ] Build the real fragments, time-dependent glyph selection, overlay and smooth camera path using existing asset and scripting facilities. Maintain readable digits and overlay at television distance.
- [ ] Test projection convergence at alignment and meaningful parallax off-axis, all ten digits and transitions, 12/24-hour and leading-zero behavior, minute rollover, camera period and hold, and suspend/resume. Compare actual engine captures with the computed geometry.
- [ ] Integrate into the canonical clock catalog and shared settings contract once its actual implementation and ownership are identified. Preserve stable IDs and other clocks. Build the standalone and the bundle.
- [ ] Profile and visually check the frozen release APK through the shared Chromecast coordinator; capture alignment and off-axis, overlay readability and minute rollover. Report device evidence and unresolved limitations.

If an existing camera, overlay or inset capability is insufficient, prepare a concrete engine-change proposal and obtain explicit permission before editing engine code; continue independent art and scripting work where possible.

## Implementation notes

The level uses a single live camera. No existing simultaneous second-view facility was found during the read-only investigation, so the runtime has no inset. The [aligned PC capture](../diagnostics/anamorphic-shards-2026-11-23/registered-aligned.png) and [off-axis PC capture](../diagnostics/anamorphic-shards-2026-11-23/registered-off-axis.png) show separate views of the same three-dimensional pieces; they are not a live inset. The independent white time display stays readable throughout the move. Camera drift can be turned off in the level settings, holding the alignment.
