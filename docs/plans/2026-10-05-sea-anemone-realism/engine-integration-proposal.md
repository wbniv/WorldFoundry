# Sea-anemone engine integration: permission proposal

Status: **under revision for generic deformation; awaiting approval; no engine files edited**. 5 October 2026.
The level implementation request authorizes assets/scripts/tooling. The standing
engine rule requires separate discussion and explicit permission for this scope.

## Why the existing entry points do not fit

Read-only inspection of `fin_deform.h` shows that texture UVs are interpreted as
root-to-tip/across-fin weights and fixed-axis surface displacements. That would
couple the atlas layout to motion and cannot describe this radial crown.
`jelly_deform.h` derives lengths from negative local Z and hard-codes bell/trailing
weights; the anemone has upward tentacles and an attached foot. `lion-pose` has
fish-specific regions/pivots. None provides the required metadata and independent
foot/crown contraction. Reusing their names or altering their semantics would
risk existing levels.

The actual authored asset is **one mesh, 3,420 vertices, 5,756 triangles,
48 tentacles, one 256² atlas**. Geometry and reference pose invariants pass
10 tests. [Rest preview](assets/rest.png), [flow-left](assets/flow-left.png),
[flow-right](assets/flow-right.png), [withdrawal](assets/withdrawn.png).
These are Blender authoring studies, not a running-game demonstration.

## Earlier engine scope — deformation items 1–2 superseded

Will asked to make deformation reusable across actors. Prefer the
[generic deformation proposal](generic-deformation-proposal.md): DFRM metadata,
a shared curve/weighted-transform evaluator and `deform-apply`, replacing ARIG
and `anemone-pose`. The earlier items below are retained as discussion history,
not the current API to implement. Settings remain OAS/OAD-defined with script
state and a reusable bridge. No engine edits are authorized.

## Earlier requested engine scope

1. Add an optional `ARIG` version-1 mesh metadata chunk, alongside the existing
   optional `LRIG` convention. Header: uint32 version/count, followed by each
   exported vertex's region and six fixed-point values: root XYZ, normalized
   root-to-tip coordinate, local length and phase offset. Preserve metadata when
   exporter splits vertices for UV/material seams. Texture UVs remain texture UVs.
   Invalid sizes, regions, values or unsupported versions must fail safely.
2. Add cached rest-vertex deformation to `RenderActor3D` with a new
   `anemone-pose ( phase flow-x flow-y withdrawal actor -- )` Forth entry point.
   Region 0 is the foot/column/disc; region 1 is tentacle tissue. Body shortening
   keeps the foot attached; tentacle roots follow the deformed oral disc. Shared
   flow and subordinate lag bend the tip-weighted curve. Withdrawal is clamped,
   UVs stay unchanged, rest coordinates never accumulate error, and incompatible
   fish/jelly/fin deformation calls cannot claim the same mesh.
3. Define **Control Focus** as an OAS/OAD enum with labels
   **Clownfish | Anemone**, an authored default and a mailbox binding consumed by
   Forth. Keep focus, held-input suppression and action envelopes in level scripts.
   Use a reusable runtime settings bridge to render this declared enum on TV and
   phone, rather than adding a separate anemone settings state machine. Existing
   `SHOW_AS_DROPMENU` entries specify editor widgets; they do not currently provide
   a shipped TV/phone runtime menu. The bridge needs explicit metadata for runtime
   exposure/binding, validation, modal/session lifetime and generic label rendering.
   Proposed cooked `RSET` v1 metadata accompanies the owning model: title, enum
   field names, ranges/defaults/choice labels and explicit mailbox bindings are
   generated from the OAD plus the allowlisted bindings file. A generic
   `settings-register ( actor -- )` binding makes that descriptor available to
   the existing overlay/phone transport. The bridge edits draft values, applies
   validated values to the bound mailboxes and resets registration on level exit.
   Start with integer enums only; the plant uint32 seed migration is a separate
   TODO requiring a lossless typed representation before implementation.
   Do not expose arbitrary actor OAD fields or hard-code anemone labels in C++.
   Clear held input on focus/modal transitions; consume the closing action before
   gameplay resumes. Mirror the value on phones, reject stale sessions and support
   Chromium/WebView 91.
4. Add lifecycle cleanup on tank/selector transitions, including cached pose and
   phone settings availability. Add optional profiling switches to freeze the
   pose/withdrawal for matched device trials without changing normal defaults.

Candidate files (exact locations can be reduced during integration):

- New `wfsource/source/renderassets/anemone_deform.h`.
- `wfsource/source/renderassets/rendacto.hp` and `.cc`: pose/cache API.
- `wfsource/source/gfx/rendobj3.hp` and `.cc`,
  `wfsource/source/gfx/glpipeline/rendobj3.cc`: optional rig loading/storage,
  including non-modern backend compatibility or explicit guarded behavior.
- `engine/stubs/scripting_zforth.cc`: dedicated pose/settings bindings.
- Authored `wflevels/aquarium/anemone_settings.oas`, compiled OAD and explicit
  `anemone_settings_bindings.json`, extracted by `scripts/build-runtime-settings.py`.
- New generic `wfsource/source/game/runtime_settings.h`/`.cc` for descriptor
  registration, enum drafts/validation and shared TV/phone presentation.
  No `anemone_settings.h` or dedicated anemone UI state machine.
- Existing game/input/overlay lifecycle files that own plant/phone settings:
  `wfsource/source/game/game.cc`, `wfsource/source/gfx/gl/display.cc`,
  `wfsource/source/hal/android/native_app_entry.cc`,
  phonepad overlay/connection owners and `wfsource/source/hal/phonepad/controller.html`.
- `wfsource/source/gfx/metal/backend_metal.mm` only if its existing writable-vertex
  path needs explicit ARIG integration; otherwise retain its existing upload path.
- Exporter tooling `wftools/wf_blender/export_level.py` for the optional chunk;
  level/Forth/assets and tests are already within the authorized non-engine work.

This scope does **not** include a general skeleton system, renderer lighting
rewrite, new transparency implementation, unrelated fish changes or device-service
changes. Existing translucency and writable vertex upload paths will be reused.

## Validation before deployment

Check metadata round trips including seam splits and malformed chunks; finite
pose math, fixed foot/tentacle-root invariants, no drift over repeated cycles,
unchanged UVs and bounded response after a long tick. Exercise focus transitions,
held/released actions, phone reconnect and stale sessions, overlay/selector back
behavior and cast2 directional input. Regression-check existing fin, jelly,
lionfish, plant and menu behavior. Capture actual runtime wide/close-up evidence.
Profile baseline, rest asset, deformation and crawling separately on both
Chromecasts with saved APK hashes and deltas as specified in the parent plan.

## Settings architecture correction · 5 October 2026

Will asked whether settings can use OAS/OAD entries. Yes: `test.oas` already
supports named integer enums and editor dropdowns. A schema entry can own the
labels/default, and a script mailbox can own the runtime value. OAD generation
alone does not create the runtime TV/phone form: the existing plant UI uses
species-specific C++ state and rendering. The proposal above is revised to keep
anemone state in Forth and author settings as data, with any missing UI bridge
reusable. The earlier anemone-specific settings plumbing is withdrawn. This
revision is discussion, not permission to edit OAS schemas or engine code.

## Authoring proof

`wflevels/aquarium/anemone_settings.oas` has been compiled using the existing
OAS compiler, in a temporary copy of the schema directory so no engine schemas
were edited. `scripts/build-runtime-settings.py` reads that binary OAD and an
explicit field/mailbox allowlist. The resulting
[descriptor](assets/runtime-settings.json) takes **Control Focus**, **Clownfish |
Anemone**, range **0–1** and default **0** from the actual compiled OAD, then binds
the live value to mailbox **729**. Asset, Forth and schema-authoring checks now
pass **23 tests**. Existing plant conversion work is recorded separately in the
[runtime settings migration TODOs](../2026-10-05-runtime-settings-oas-oad-migration.md).
