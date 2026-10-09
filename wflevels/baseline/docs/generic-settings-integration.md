# Shared generic settings integration

6 October 2026. Concrete engine proposal for the
[generic OAS/OAD plan](../../../docs/plans/2026-10-06-runtime-oas-oad-object-editor.md).
Engine changes explicitly authorized by Will on 6 October 2026 under
[AGENTS.md](../../../AGENTS.md). The shared host and plant consumer migration are implemented. Baseline device acceptance and the main-CD addition are complete. Plant
device acceptance is also complete on both Chromecasts.

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
- Default and gallery each passed all 20 baseline assertions on both cast1 and
  cast2. This includes real held/released directional input, two-owner TV
  selection, stale sessions, instance isolation, invalid drafts, Apply/Cancel,
  phone reconnect, same-process Home/resume and reset chords.
- Baseline was appended at main CD index 7 after those sessions passed. All 156
  bundle/source/native checks passed. The existing shell and seven entries and
  bodies are byte-identical to the previous bundle; boot remains level 0.
- Plant's full device run passed on both devices with the same frozen APK:
  cast2 passed 29 assertions and cast1 passed 30 (including Down clearance).
  Native text entry, seed precision, regeneration, speed-only continuity,
  reconnect/Cancel, held/released movement, same-process Home/resume and selector
  exit all passed. Cast1's earlier grounded Down setup was corrected in the
  validator; no additional engine change was needed.
- Coordinator fixes live in the standalone coordinator repository. The v4
  reviewed release is installed; baseline acceptance uses that release.

[Final evidence and hashes](../../../docs/diagnostics/baseline/generic-settings/README.md)
record the accepted baseline and plant checks. Gallery catalog
coverage is comprehensive; interactive coverage of every descriptor presentation
remains a separate acceptance requirement.


## Runtime Options implementation (2026-10-09)

The isolated `baseline-runtime-options` branch adds one Runtime Options sheet to
both authored presets, preserving existing sample IDs and values. The existing
RPRP cooker and shared host remain the transport and transaction boundary.
`engine/runtime_options.hpp` synchronizes process values across both owners,
rejects stale snapshots and read-only mutations, and prepares fallible resources
before application. `game/runtime_options.cc` supplies effective readback and
adapters for FPS, fixed/real-time simulation clock, enable-only profilers and
conditional debug streams. TV rows now show category labels, dimmed read-only
controls and focused help; the existing phone form already supports these.

Build with the existing `wflevels/baseline/build.py`. The generated
`runtime-options.json` records field IDs, CLI inventory and capability policies;
the build receipt hashes the source, OAS/OAD, bindings and cooked catalog.
`pytest -q tests/test_runtime_options.py` covers real cooked catalogs and host
transactions, including failure preparation, unchanged Apply, two-owner state,
ordinary sample isolation, numeric bounds, stale globals/sessions and diagnostic
fallback/typing restoration. Production desktop acceptance is reproducible with
`python3 scripts/check-baseline-runtime-desktop.py --out /path/to/evidence`
after a diagnostic desktop build and default level build. It uses the engine's
own X11 window and the read-only diagnostic bridge, then checks applied values
and emitted profiling output. It requires Python Xlib and an X11 session.

Desktop and Android armeabi-v7a builds compiled. The final frozen APK is
`baseline-9e6c852ce3bb8f8c.apk`. Both dedicated Chromecasts passed the existing
20-assertion `baseline-settings` validator in batch `B-2004eb07c1a0`:
cast1 `J-e74c40420a95`, cast2 `J-cc3f36457c7e`. Evidence is retained under the
ignored build directory; actual models expose the runtime controls as editable
and renderer/surface/allocation rows as read-only. That validator exercises
settings transactions, held/released directions, reconnect and Home/resume. It
does not toggle runtime controls, so live device effects remain an acceptance
follow-up. Desktop testing confirms FPS state, fixed delta at 21 Hz, return to
real time, both-owner readback and actual frame/script profile output. X11 front
buffer captures retained the menu image and are not visual FPS evidence. Direct
level-clock advancement measurements and live debug-stream effects also remain
unverified. The conditional debug-stream adapter and accessor compiled in the
debug configuration; current CMake builds disable file-stream output.

The six plant switches are excluded from this sheet. Their parser and plant
consumer are unchanged: conversion to authored settings still requires explicit
permission beyond the previously authorized baseline engine scope. No renderer,
allocator, window or listener reconstruction was added.
