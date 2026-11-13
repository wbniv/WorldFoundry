# Runtime-editing follow-ups, 13 November 2026

Scope selected by Will: **device checks and proposals only**. No engine source
was changed and no shared coordinator validator or touch guard was deployed.
The proposals are under
[`docs/plans/2026-10-16-runtime-object-editing/followups/`](../../plans/2026-10-16-runtime-object-editing/followups/engine-scope.md).

## Default timing: PASS

The production Release Planted APK completed one uninterrupted 1× cycle with a
120-second hold on cast1 in J‑cbc06d527a67. Tank-start markers are
09:01:09.859 and 09:06:24.975: **315.116 seconds**, within five seconds of the
195 + 120 = 315 second target. All 17 process samples were stable and cleanup
restored the session. Screen recording was disabled.

See [verdict](release-timing/verdict.json), [tank markers](release-timing/markers.json)
and [Release APK identity](release-apk.json). The earlier debug run
J‑66f1f1195221 repeatedly exceeded the growth clock's 0.2-second frame cutoff;
it was ended and is not production timing acceptance.

## Baseline runtime options: blocked by validator expectations

The current diagnostic baseline APK is
`build-docker/runtime-editing-android/baseline-diagnostic-followups.apk`, SHA-256
`6c2453387655802b7206c6487512f017a3ffce5e877d88da19f908011621b783`.
Cast1 job J‑8c0da2aee2ea reached the actual RuntimeDiagnostics TV form with the
expected FPS, fixed-clock and rate values. It then failed
`tv_opens_runtime_settings`: the deployed validator expects the retired Settings
schema. It stopped before exercising edits or actual clock-rate transitions.
Therefore this is not a full baseline-runtime-options PASS.

See the curated [assertion summary](baseline-summary.json).
The proposed validator patch updates the schema expectation and resolves the
FieldTypes int-number field by key rather than the retired synthetic ID 1.
It has not been deployed. The broader baseline-settings validator also needs
an OAD-aware update; its old bounded-string cases remain explicitly deferred.

## Pixel: render verified; touch acceptance remains open

After Will unlocked the phone, the diagnostic baseline launched and rendered
correctly. [Initial screen](pixel-initial.png). Owned touch job J‑9544c851c1d3
was rejected before injecting any edge with `app-content-changed` when the score
used the whole display rectangle. Retry J‑c324a8bad601, using inferred insets,
was also rejected. Display dimensions and rotation matched; the strict active
accessibility-root rectangle did not. No guard was relaxed or bypassed.

The current coordinator does not return that measured rectangle with its frame,
and its rejection drops the observed-rectangle detail. The frame-context proposal
adds that read-only information while retaining exact focus/geometry checks.
Pixel picker/forms acceptance remains open. See the [attempt summary](pixel-summary.json).

## Release soak: reload/process checks pass; memory gate remains open

Cast2 job J‑c21e98845289 recorded 63 tank starts (at least 62 reloads) at 8×,
hold five seconds, in PID 17159. All 73 PID samples were stable, no fatal/crash
marker was found in the collected logs, and session cleanup completed with no
survivors. Screen recording was disabled.

A 914.8-second gap in host sampling left only two samples in the final ten
minutes. Their 2,466 KiB spread cannot establish the strict below-4,096 KiB memory
gate; an earlier rolling window reached 5,764 KiB. **The soak is not accepted.**
Retain the threshold and repeat with continuous sampling; diagnose a repeat
spread failure before proposing engine changes. Marker collection also has a
gap, so the observed reload count is a lower bound.

Readback confirms Growth speed=3, Hold seconds=120, and the original Seahorse
Grid selection restored. See [verdict](release-soak/verdict.json),
[samples](release-soak/sample-values.json), [markers](release-soak/markers.json),
and [restoration](release-soak/restoration.json).
