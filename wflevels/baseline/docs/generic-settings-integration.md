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

Will explicitly authorized the plant CLI removal. All six parser interfaces are
removed; stale invocations fail with an explicit migration message. The plant
consumer reads the cooked `PlantedTankSettings` catalog on entry, retaining seed,
water, speed, bounded initial age, textures and sway. Random entry remains the
default; deterministic fixtures explicitly disable it. Age and random-entry
policy are authored read-only fields. Speed and render flags apply live without
resetting growth; seed/water changes regenerate at age zero. A separate geometry
revision refreshes cached meshes when texture/sway changes without resetting the
simulation. The existing renderer API and generic host are reused.

The profile, sea-urchin and atlas recipes cook per-fixture catalogs, preserve
other owners/assets and native-library identities, and record hashes. The
256-pixel atlas control exactly matches the production standalone level; the
permanent page uses production dimensions rather than an obsolete 256 assumption.
38 matched profile APKs and eight 256/128 comparison APKs packaged successfully.
Twenty focused cooked-catalog/Runtime Options tests and three plant sanitizer/
phone-browser tests passed. Coverage includes seed zero/UINT32_MAX, both water
types, age bounds, random entry, live flags/speed, regeneration, Apply/Cancel,
read-only forgery rejection and stale CLI errors. The initial broader aquarium run found a stale 46-actor assertion: two goby
meshes and three grazing rocks increased the exported inventory to 51. Runtime
visibility mailboxes select residents and rocks by water type without removing
their actor indices. The test now checks all exported names/indices against the
actor map and requires exactly eight plant groups. All five aquarium tests pass.

Desktop and Android armeabi-v7a builds compiled with the conversion. Coordinator
profile `J-fbe79303e2b0` on cast1 logged the exact RPRP-selected seed 713,
saltwater, age 150, speed 0, textures/sway enabled. Captures show the mature
saltwater tank and movement under held/released directional input. Evidence is
under `build/evidence/plant-cast1-saltwater`; previous sessions in the appended
log are historical, not results of this run. Cast2 completed contrasting profiles
`J-b6c0a943a456` (freshwater, textures/sway disabled), `J-1bf1cb367058`
(UINT32_MAX seed, saltwater, textures enabled/sway disabled), and
`J-49b5d1752636` (seed 713, saltwater, textures/sway enabled). All logged the
intended RPRP-selected values; captures show the corresponding resident and
textured/untextured plants, and traces include held/released directional input.
The first cast2 saltwater attempt exited before measurement; the same frozen APK
passed on retry. No assertion follows the selected-values log in successful runs.
The existing device plant-settings validator assumes exactly three fields and
has not been updated for the expanded catalog, so these profiles do not claim
that validator's live settings coverage. No renderer, allocator, window or
listener reconstruction was added.

Runtime Options acceptance follow-up (2026-10-09): the existing diagnostic
accessor now reports the actual `LevelClock` time/delta on the game thread,
without permitting mutation. Seventeen diagnostic transport tests passed. The
production desktop UI check measures fixed-clock advancement at 21 Hz and
real-time restoration independently of property values; both passed. Desktop
and Android builds passed. Refreshed diagnostic APK
`baseline-151186bac852a28d.apk` passed all 20 existing baseline checks on cast2
(`J-befe34cb3fdf`), including actual clock readback. This remains general
settings validation, not completed live Runtime Options device acceptance.

Coordinator commit `762032a` prepares a fixed `baseline-runtime-options`
validator on the installed-service revision. It exercises TV Back-to-Apply,
phone Apply/Cancel, two-owner readback, 20/37 Hz actual-clock advancement,
real-time restoration and emitted profiler output, with FPS on/off captures for
visual review. Focused validator/transport tests (51) and validator/service
integration tests (61) passed. The frozen release and hash review are
`/tmp/chromecast-runtime-options-release` and
`/tmp/chromecast-runtime-options-review.json`. Preflight passes; deployment
changes only registration, dispatch and the new validator. Live acceptance
awaits the reviewed administrator upgrade; no direct-control fallback is used.
