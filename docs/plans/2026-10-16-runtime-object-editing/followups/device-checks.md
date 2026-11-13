# Device follow-ups, 13 November 2026

Will selected **device checks and proposals only**. No engine source edits or
shared coordinator deployment are authorized by this document.

## Baseline runtime options

The actor-based diagnostic baseline APK is frozen at
`build-docker/runtime-editing-android/baseline-diagnostic-followups.apk`, SHA-256
`6c2453387655802b7206c6487512f017a3ffce5e877d88da19f908011621b783`.
It contains the diagnostic marker, current native libraries, and the rebuilt
catalog-free baseline bundle. The runtime build and packaging logs are under
`build-docker/runtime-editing-android/`.

The deployed `baseline-runtime-options` validator still expects the removed
`Settings` schema and field id 1 in FieldTypes. The proposed patch beside this
file changes the expected schema to RuntimeDiagnostics and resolves int-number
by key. It is a proposal only: it has not been applied to the shared service.
The broader baseline-settings validator also assumes the old synthetic text
rows and numeric IDs; its acceptance needs an OAD-aware rewrite, retaining the
bounded-text cases as explicitly deferred rather than pretending they passed.

Cast1 job J‑8c0da2aee2ea reached RuntimeDiagnostics with the expected initial
FPS/fixed-clock/rate values, then failed the stale schema assertion before edits.
It does not satisfy runtime-options acceptance. See the
[assertion summary](../../../diagnostics/runtime-editing-followups-2026-11-13/baseline-summary.json).

After Will unlocked the Pixel, the baseline rendered correctly. Owned touch jobs
J‑9544c851c1d3 and J‑c324a8bad601 both rejected the score with
`app-content-changed` before injecting any edge. Pixel picker/forms remain open.
See the [frame-context proposal](pixel-frame-context.md); no guard was changed.

## Planted default timing: PASS

Production Release job J‑cbc06d527a67 on cast1 measured **315.116 seconds**
between tank starts at 1× and hold 120. The nominal cycle is the authored
195-second maturity bound plus 120 seconds hold: 315 seconds, tolerance ±5.
All 17 process samples were stable; cleanup restored the session. No video.

The initial debug attempts do not count as acceptance: one timed out without
samples, and the sampled debug run repeatedly exceeded the growth clock's
0.2-second frame cutoff. The Release run above is the acceptance result.

## Planted soak: memory acceptance remains open

Release job J‑c21e98845289 on cast2 recorded 63 tank starts (at least 62 reloads)
in one PID, with no fatal marker in collected logs. All 73 process samples were
stable. A 914.8-second sampling gap left only two samples in the final ten
minutes, so the strict below-4096 KiB memory-spread criterion cannot be accepted.
An earlier rolling window reached 5764 KiB. Do not weaken the threshold.

Readback verified speed 3, hold 120, and original Seahorse Grid selection restored.
The session succeeded, health was ready, cleanup restored and survivors were empty.
[Curated verdict and samples](../../../diagnostics/runtime-editing-followups-2026-11-13/README.md).
A repeat needs continuous host sampling. Any required engine fix remains a
proposal requiring explicit permission.
