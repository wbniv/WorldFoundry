# World Foundry baseline

Reusable empty-scene level with a 200 × 200 floor, 1/10-unit grid, RGB unit axes,
coordinate labels, visible player, unit cube and 10-unit ruler. Source geometry
and actor defaults are generated here; no Snowgoons or adventure level is imported.

The reviewed editable scene is [baseline.blend](baseline.blend). Configuration
is in [baseline.json](baseline.json). Open the Blender file directly to edit
meshes, actor properties or collections. The `AUTHORING_ONLY` camera has no OAD
and is excluded from runtime export.

Prerequisites: Blender with this checkout's `wf_core.so`, Python/Pillow, and
built `iffcomp-rs`, `levcomp-rs`, `textile-rs`, `cdpack-rs`, `oas2oad-rs`,
`wf_attr_edit` catalog and `wftools/prep/prep`. Use the existing repository tool
build instructions. No native engine rebuild is needed for level-only work.

From the repository root:

```sh
task baseline:build
task baseline:verify
task baseline:check
```

Build exports the reviewed Blender file, compiles the level and both OAS
fixtures, attaches two independent property catalogs and creates an isolated
`build/cd.iff`. Logs, receipts and native screenshots are under `build/`.
`baseline:check` starts and closes its own desktop runtime, uses port 7785,
and verifies native movement, release, grounding, collision, camera switching,
quadrant support and reset. It needs a working display and local socket access.
Debug-assisted position/heading setup is explicitly distinguished from the
input-driven movement it tests.

```sh
task baseline:generate
task baseline:export
task baseline:diagnostics
task baseline:settings-gallery
```

Generate creates `build/baseline-generated.blend` and refuses to overwrite it.
It never regenerates `baseline.blend`. To replace a generated file deliberately,
use `generate.py --output <file> --overwrite`; export accepts `--export <file>`
independently. `build.py --blend <file>` builds manual edits without regeneration.

Diagnostic presets use separate generated Blender files. Disabled diagnostic
actors have an explicit `wf_baseline_excluded` flag: viewport hiding alone is
not an export policy. Export temporarily detaches those schemas and restores
them afterward. The sparse default retains no diagnostic actors or textures.
Optional motion/room-transition fixtures remain pending; wedges exercise static triangle-mesh collision; slope traversal acceptance
remains pending.

Native controls: Up/Down moves forward/backward; Left/Right turns; A jumps,
B resets, C changes camera. A Chromecast remote uses Up+OK to reset and
Down+OK to switch camera. The first-person shot is an inspection camera with
no separate player-controller implementation. Camera obstruction behavior is
the existing engine's behavior.

Package with already built native libraries:

```sh
python3 wflevels/baseline/build.py --package-only \
  --runtime android/app/build/outputs/apk/condo/release/worldfoundry-condo-release.apk
```

The first package freezes the input runtime under ignored `build/runtime.apk`.
Later packages refuse a different runtime unless that snapshot is explicitly
reviewed/replaced. Receipts record desktop, tool, level, APK and native-library
hashes; packaged libraries are byte-verified. The output package is
`org.worldfoundry.wf_game.baseline`, with its own development signing key kept
under ignored `build/`. SDK discovery uses `ANDROID_HOME`, `ANDROID_SDK_ROOT`,
then `~/android-sdk-local`. No signing keys or machine paths are portable config.

Chromecast sessions must use the shared coordinator. The coordinator currently
needs baseline app registration before it can accept `APP=baseline`; there is
no direct ADB fallback. Device acceptance remains pending. Add the baseline to
the main `cd.iff` only after matching native/device verification succeeds;
preserve all existing level indices and its boot level.

The five-field default and 118-field gallery come from level-owned OAS/OAD.
[settings-coverage.json](settings-coverage.json) accounts for every declared
descriptor type and presentation code, preserves original metadata, and records
unsupported and excluded cases. Hidden cases are omission tests. Narrow fields
are supplemental catalog examples, not changes to native actor packing.
Source/compiled coverage is distinct from interactive acceptance.
[Saved verification receipts and captures](../../docs/diagnostics/baseline/README.md)
record the tested build hashes.

The catalogs are attached, but the current settings host only opens Planted Tank
objects. Baseline form selection and migration of the remaining plant routing
require the [shared engine integration](docs/generic-settings-integration.md).
See the [baseline plan](../../docs/plans/2026-10-05-world-foundry-baseline.md)
for acceptance and documentation migration gates.
