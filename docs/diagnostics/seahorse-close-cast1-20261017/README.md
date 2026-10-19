# Cast1 close-view population baselines

17 October 2026. Source: `d8d215ae`, in the isolated
`seahorse-close-baselines` worktree. No engine source changes.

## Protocol

None, 1, 2 and 6 pairs, saltwater, seed 713, plant age 150, growth paused,
textures/sway/greeting on and random entry off. Three independent 60-second
release repeats per count and close view, each after 15 seconds warmup. Count
order rotates between rounds. One separate frame-profile repeat per case
provides CPU sections and rendering counters. Four single-sample wide controls
use the same newly built binary; the earlier wide baseline remains a separate
three-repeat campaign. This build includes the subsequently merged object
picker; the old and new native hashes differ. Do not pool their runs or
attribute any difference to one source change.

The deployed coordinator accepts `idle` and `school` traces. Its legacy
`plants` sequence exists in implementation code but is absent from its accepted
request schema, so these jobs use supported `idle` profiles and direct-launch
benchmark assets. `build-seahorse-close-variants.py` fixes the existing camera
selection to the existing urchin-following close camera. It is not a new
seahorse camera: some residents extend above its top edge. The crawl fixture
ORs the right bit into the existing
Forth held-input reader, preserving the normal easing, movement and floor
controller. This measures the crawling workload, not physical input delivery.
A host VM test compares all six position/velocity components with held-right
input over 75 simulated seconds. Close idle remains stationary.

The packager requires unique, complete, NUL-terminated Player and Director
scripts matching the tracked `.lev` source. It refuses changed anchors,
ambiguous scripts, overlapping slots or growth beyond the original slot. It
pads the shorter replacements to their original size, verifies every byte
outside those slots, cooks settings using the existing property tool and
builds a single-level CD with the existing shell. It never converts mesh
indices, normals, materials, UVs or deformers. Every non-signature APK entry
other than `assets/cd.iff` and `assets/wf_args.txt` must equal the base APK.
Native-library and per-script hashes are recorded in `variants.json`. The
analyzer also checks each installed APK hash against that receipt, and requires
successful coordinator cleanup with the exact selector restoration hash.

The selector six-pair release APK is restored by the coordinator after each
complete session. `jobs.json` maps evidence subdirectories to immutable jobs;
recipes record the submitted local inputs. Frozen APKs remain available until
all missing or rejected samples have been repeated. Temporary build outputs
are removed after the results have been committed and merged.

## Validation and reproduction

`local-validation.json` records the offline Android release build and focused
fixture tests. `variants.json` includes all generated fixtures; wide CPU
fixtures were built but are not submitted by this protocol. `restore.json`
identifies the normal selector APK used for cleanup.

```sh
python3 scripts/build-seahorse-close-variants.py \
  --base-apk android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk \
  --out engine/objs_game/.tmp/seahorse-close/fixtures
PYTHONPATH=scripts pytest -q tests/test_seahorse_close_fixtures.py
python3 scripts/analyze-seahorse-close.py \
  --evidence docs/diagnostics/seahorse-close-cast1-20261017 \
  --out docs/diagnostics/seahorse-close-cast1-20261017/comparison.json
```

For a new campaign regenerate recipe paths and hashes, freeze the restoration
APK first, and submit with `task chromecast:submit DEVICE=chromecast-test-01
RECIPE=<path> ASYNC=1`. Follow using `task chromecast:watch JOB=<job>` and download
with `task chromecast:evidence JOB=<job> OUT=<new-directory>`. The coordinator
owns installation, launch, measurement, restoration and foreground cleanup.
No personal reservation or direct device control is needed.

## Completed results and retained evidence

All 24 close-view release runs, eight separate CPU runs and four fresh wide
controls passed. All 36 per-run captures were visually inspected; post-run
thermal status is 0 throughout. Every session verified installed fixture hashes,
restored the exact selector APK and completed cleanup. No replacements or
rejected samples were needed. `verification.json` records the final checks;
`comparison.json` retains every run's presentation statistics and selected CPU
windows. Reanalysis after compression produces byte-identical results.

[Comparison, graph and interpolated 3–5-pair estimates](../../plans/2026-10-16-saltwater-seahorses/comparison.md#close-idle-and-close-crawl--completed-17-october).
The three estimated populations were not tested on the device.

Large text/JSON artifacts are losslessly gzipped. `compressed-evidence.json`
records original and compressed sizes and SHA-256 values; every archive was
round-trip verified. The analyzer reads plain files or `.gz` transparently.
To limit repository/disk growth, the four fresh wide screenshots and the eight
first-round close screenshots are retained. Other repeat/CPU captures and
redundant session screenshots are omitted locally after review; `captures.json`
records all 45 original PNG hashes, review status, retention and source job.
Download any omitted original again with the evidence Task into a new directory.
All timing, CPU, memory, thermal, install and cleanup evidence is retained.

| Batch | Coordinator job |
|---|---|
| wide-idle/control | J‑14efcc267fac |
| close-idle/round-1 | J‑903371c0b823 |
| close-idle/round-2 | J‑bc147de4ef52 |
| close-idle/round-3 | J‑93485aa9a488 |
| close-idle/cpu | J‑efb995f7194f |
| close-crawl/round-1 | J‑0468bcad2555 |
| close-crawl/round-2 | J‑7eebf0150519 |
| close-crawl/round-3 | J‑ff0141cec596 |
| close-crawl/cpu | J‑9c9e21b49a6b |
