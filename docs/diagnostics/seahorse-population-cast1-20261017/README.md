# Seahorse population baseline on cast1

17 October 2026. Integration merge `9f97f5dd` is pushed to `2026-new-level`.

Completed cast1 wide-idle baseline: 12 accepted release runs and four accepted
CPU runs. [Results](../../plans/2026-10-16-saltwater-seahorses/comparison.md).
Frozen APK hashes, identical native-library hashes,
authored fixture settings and job IDs are recorded beside this file. Four
populations (None, 1, 2 and 6 pairs) use the same twelve-resident level.
The setting controls visibility and script/evaluator execution. Hiding the
residents does not free their allocated meshes or state; None also hides the
six posts. Process PSS therefore cannot establish memory cost per seahorse.

Three release rounds measure 60 seconds of wide idle per count after 15 seconds
of warm-up, with count order varied between rounds. A separate round enables
`--frame-profile` for main-thread CPU sections; those timings are kept separate
from release presentation statistics. The coordinator owns installation,
launch, measurement, evidence collection and restoration of the six-pair APK
for each complete round. Reservations and other sessions are respected.

Presentation results are rejected if polling loses coverage or the
observed span is below 59 seconds. CPU windows must lie fully inside the
measured device presentation timestamps, excluding startup, warm-up and
older content in the cumulative engine log. Thermal status and raw snapshots
are retained with every run. No hardware GPU timer or skinning implementation
is part of this baseline. Close views and crawling remain separate checks.

Large text artifacts are losslessly gzipped to reduce disk use. The analyzer
reads plain and compressed files; `compressed-evidence.json` records original
sizes and SHA256 hashes. `rejections.json` records the wrong-scene sample and
failed launches, and `selections.json` identifies explicit replacements. The
valid None CPU sample survives its session's later failure. A matching marker
somewhere in a cumulative app log is insufficient scene evidence; the analyzer
scopes the latest load and screenshots are reviewed separately.

The original requests' unused top-level APK default was supplied by the main
checkout's producer. The variant workflow installs only each frozen variant and
the explicit restoration APK; installation receipts identify those exact hashes.
Replacement recipes set the top-level APK explicitly to the six-pair restoration
build. Presentation and CPU results always refer to the variant hashes in
`frozen-builds.json`.

The completed normal-convention worktree and obsolete demo scratch were removed.
The remaining isolated checkout was reduced to report/evidence files while jobs
waited. Inputs were already frozen and uploaded to the coordinator; local APK
build outputs are disposable. Branch commits and committed evidence are retained.

The selected evidence is already retained here. Job directories:

| Folder | Coordinator job | Use |
|---|---|---|
| `round-1` | J‑ad650fa52937 | Four accepted release samples |
| `round-2` | J‑37d37d7bc854 | Three accepted release samples; None rejected |
| `round-3-failed` | J‑4399ea64b1f4 | Failed launch, retained for diagnosis |
| `round-3` | J‑b17ce50c0065 | Four accepted replacement release samples |
| `none-replacement` | J‑03e1af5ca7bf | Accepted replacement for round two's None |
| `cpu-failed` | J‑a85e8414f1d4 | Accepted None CPU sample before later failure |
| `cpu` | J‑5319448dd00e | Three accepted remaining CPU samples |

Re-download any completed session with `task chromecast:evidence JOB=... OUT=...`
to a fresh directory. Job IDs in commands use ASCII `J-`; the JSON job map keeps
the executable bytes. `selections.json` resolves the two replacement paths.

Reproduce the analysis:

```sh
python3 scripts/analyze-seahorse-population.py \
  --evidence docs/diagnostics/seahorse-population-cast1-20261017 \
  --out docs/diagnostics/seahorse-population-cast1-20261017/comparison.json
```
