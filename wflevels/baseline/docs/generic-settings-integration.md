# Shared generic settings integration

6 October 2026. Concrete engine proposal for the
[generic OAS/OAD plan](../../../docs/plans/2026-10-06-runtime-oas-oad-object-editor.md).
Engine changes explicitly authorized by Will on 6 October 2026 under
[AGENTS.md](../../../AGENTS.md). The shared host and plant consumer migration are implemented. Device acceptance
and the subsequent main-CD addition are in progress.

The baseline already exports two independently addressed OAD catalog owners.
Planted Tank already exports Seed, Water type and Growth speed through that
catalog, but game/modal/phone routing is still owned by `planted::State` and
`planted::open`, which specifically selects `PlantedTankSettings`.

Implement one shared property-editor host with these responsibilities:

1. Enumerate live eligible catalog objects in stable actor order, show their
   authored titles, select an owner and call the existing `Form::begin`.
   A single owner opens directly; baseline's two owners use an object picker.
2. Own modal state, hold/release gating, TV form/picker rendering, phone commands,
   apply/cancel and lifecycle cleanup independently of plant simulation state.
   Use the existing draft, generation/revision and session checks. Closing,
   unloading or deleting the owner cancels stale sessions and clears held input.
3. Route the existing held-OK settings gesture to that host whenever eligible
   level objects exist. Preserve each level's short-press gameplay behavior.
   Add an explicit generic Forth open-by-owner entry point if level scripts need
   to choose an owner, rather than adding a baseline-specific syscall.
4. Keep plant regeneration, random seed and speed mapping as consumer callbacks
   registered for its authored owner/action keys. After a successful validated
   commit, seed/water changes regenerate; speed-only changes retain growth.
   Preserve the existing selector preview settings through the shared host.
5. Attach baseline defaults and the full settings-gallery preset to the same
   host. Apply/Cancel edits only that instance. Leave unsupported descriptor
   presentations labelled as gaps until separately implemented and verified.

Expected engine files: `engine/runtime_properties.{hpp,cpp}` (object
enumeration), shared host implementation alongside `engine/runtime_property_form`,
`wfsource/source/game/game.cc` (input/modal/lifecycle routing),
`wfsource/source/game/plant_settings.h` and `plant_ui.cc` (consumer migration),
`wfsource/source/game/runtime_property_ui.{h,cc}` (shared object picker),
`wfsource/source/hal/android/native_app_entry.cc` and
`wfsource/source/hal/phonepad/controller.html` (generic session/owner commands),
`engine/stubs/scripting_zforth.cc` if the explicit open entry point is needed,
and build declarations required for the shared host. Existing diagnostics
must report the shared modal/session rather than plant-owned state.

Verification: host tests for two-instance selection/isolation, invalid values,
Apply/Cancel, stale/deleted owners, opening-input release, phone reconnect and
level teardown. Rebuild desktop and both Android ABIs. Coordinator-owned cast1
and cast2 sessions test baseline forms and movement/release, plus plant seed
precision, seed/water regeneration, speed-only continuity, TV/phone controls,
Home/resume and selector exit. WebView changes retain Chromium 91 support.

After matching baseline verification passes, add its standalone level to the
main `cd.iff` without changing existing indices or the boot level, and verify
launch from the rebuilt bundle. Commit and push the baseline and approved
generic integration separately from unrelated work in this checkout.

## Implemented integration and current verification

`wfprops::Host` now binds each level catalog, enumerates eligible live owners in
actor order, opens a picker for multiple owners and shares the same Form/session
transaction with TV and phone controls. It owns modal pause, opening/closing
input release, Apply/Cancel, owner generation checks and lifecycle cancellation.
Plant simulation registers callbacks for its schema; seed/water changes and
explicit regeneration rebuild plants, while speed-only Apply preserves growth.
The aquarium selector uses the same host with its authored preview catalog.
Baseline retains its small default form and full descriptor gallery preset.

The catalog loader and attachment tool also accept the 48-byte FLAG-only RAM
header used by baseline; the optional SLOT header is no longer assumed.

Validation recorded in `docs/diagnostics/baseline/generic-settings/`:

- Default desktop baseline: all 145 source, geometry and gameplay checks passed,
  against standalone SHA-256
  `4aca056094c048b61f2254aec7cb601c60b32a284958cd963c4b20b511d654e5`.
- The isolated integration passed all eight host, catalog, plant simulation and
  browser checks (`isolated-contracts-final.log`). This copy excludes unrelated
  colour/native-text/diagnostic work in the shared checkout and verifies that
  the integration can compile independently.
- The actual full gallery catalog passed two-owner host validation/commit with
  178 visible rows. Presentation gaps remain as described in the descriptor
  audit; catalog attachment alone does not prove every control's presentation.
- Cast1 default passed movement/release, TV selection, instance isolation,
  invalid-value rejection, Apply readback and phone reconnect before the
  observer disconnected at Home/resume. Cast2 stopped on an unsupported timed
  Android input command. Both are harness failures requiring reruns, not full
  device acceptance.
- Coordinator fixes are committed in the standalone coordinator repository:
  a bounded directional/OK hold helper and explicit observer reconnection.
  Its 147 tests passed. The reviewed v3 release awaits interactive sudo
  installation before final default/gallery and plant sessions on both devices.

Do not add baseline to the main CD until those matching sessions pass. Keep
existing level indices and boot behavior when appending it at index 7.
