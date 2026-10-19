# TODO: move entity settings from C++ state into OAS/OAD definitions

Status: **audit complete; conversions pending**. Audited 5 October 2026.
Requested while reviewing the sea-anemone implementation. This records follow-up
work; it does not authorize engine modifications.

The audit covered `wfsource/source/game`, the phone controller, Android settings
routing, engine scripting bindings and aquarium deformation helpers. It found
one implemented level-specific C++ settings system: the **Planted Tank**.
Freshwater and saltwater are two modes of that system, not separate settings owners.
The proposed anemone-specific settings system was withdrawn before implementation.

## Planted Tank — conversion TODO

- [ ] **Convert Planted Tank settings to OAS/OAD.** Currently declared and managed
  in `wfsource/source/game/plant_settings.h` (`planted::State`), with hard-coded
  controls in `plant_ui.cc` and `hal/phonepad/controller.html`. Move field names,
  types, ranges, defaults, choice labels and runtime bindings into authored
  schemas. Use the reusable runtime TV/phone settings bridge rather than a
  second source of field definitions in C++/JavaScript.
- [ ] **Seed:** schema-defined number/text entry, validation and random-seed action.
  Preserve the complete unsigned 32-bit range **0–4294967295** and deterministic
  regeneration. Do not store that entire range in one 16.16 mailbox scalar:
  choose a lossless binding representation, such as split words or a typed value.
- [ ] **Water type:** enum **Freshwater | Saltwater**, including authored default
  and binding. Preserve regeneration when water type changes.
- [ ] **Growth speed:** authored choice/range and labels for **Paused, 0.25×,
  0.5×, 1×, 2×, 4×, 8×**. Preserve existing growth when only speed changes.
- [ ] **Actions and presentation:** schema-driven Regenerate/New random seed,
  draft/apply/cancel behavior and field order; preserve the space left by the
  removed Apply Speed button. Back arrow applies and closes, validation errors
  keep settings open, and connected-phone editing mirrors TV availability/state.
- [ ] **Diagnostic overrides:** map `--plant-seed`, `--plant-age`,
  `--plant-speed`, `--plant-water`, `--plant-sway` and `--plant-texture` to the
  same typed authored configuration where appropriate. Profiling-only overrides
  stay explicitly marked; do not automatically expose every debug field to users.
- [ ] **Keep simulation state distinct:** age, generated shoots/chunks, actor
  IDs, topology slot, generation/cache bookkeeping and generic modal/session
  lifetime are runtime implementation state, not editor settings. Converting
  declarations does not require serializing the whole C++ struct as OAD fields.
- [ ] **Verify the migration:** preserve seed precision, speed-only continuity,
  freshwater/saltwater regeneration, remote grid navigation, phone reconnect,
  stale-session rejection, overlay back behavior and both-device rendering.

Related implementation files: `wfsource/source/game/game.cc`, `game/main.cc`,
`gfx/gl/display.cc`, `hal/android/native_app_entry.cc`,
`engine/stubs/scripting_zforth.cc`, `wflevels/aquarium_tanks/plants_controller.fth`.
The bridge, schema placement and approved engine scope must be discussed before
editing those engine files. Existing behavior remains until the conversion is
implemented and verified.

## Other audited entities

No equivalent implemented C++ settings form/state was found for clownfish,
tiger barbs, betta, blue shrimp, jellyfish, lionfish or Asian arowana in this
checkout. Their mesh/pose calculations and Forth/generator tunables are not
runtime settings forms, so no unsupported migration TODO is invented for them.

Generic level-selector cursor/input state, renderer backend state and
`runtime_profile.hp` profiling counters are shared infrastructure, rather than
entity-owned settings. They are outside this conversion list. Shield/tool code
already consumes generated OAD structures; historical comments saying “options”
do not establish another C++ settings interface.

## Anemone prevention TODO

- [ ] Use the authored `wflevels/aquarium/anemone_settings.oas` control-focus enum,
  its generated OAD and explicit mailbox binding for the new tank controls.
  A compiled authoring proof is saved under the
  [anemone plan assets](2026-10-05-sea-anemone-realism/assets/runtime-settings.json).
  No dedicated `anemone_settings.h` state machine has been added.

The saved prototype proves labels/default/ranges can come from the actual OAD.
The reusable runtime bridge remains unimplemented and requires an approved engine
proposal. See the [anemone plan](2026-10-05-sea-anemone-realism.md) and
[engine discussion](2026-10-05-sea-anemone-realism/engine-integration-proposal.md).
