# Sea-urchin phase comparison

Performance evidence comes exclusively from Chromecast 1. Desktop captures check geometry, contacts and movement correctness; desktop load/FPS is not used. Fixed native library hashes, saltwater seed 713, plant age 150, growth speed 0, existing water sway. Three release repeats and one separately instrumented repeat per phase; each repeat contains 60 seconds each of wide idle, close idle and cardinal crawl. CPU values are reported separately from presented-frame pacing.

| Phase | Animal / scene actors | Animal source triangles | FPS | p95 present ms | Actor CPU ms | Render CPU ms | PSS MiB | Δ actor CPU ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 9 / 38 | 860 | 14.520 | 83.417 | 1.313 | 55.111 | 77.952 | 0.000 |

Source triangle counts can differ from cooked meshes. Presented p95 is frame interval, not CPU time. The coordinator’s reviewed plants trace uses cardinal key events; diagonal, reversal and anchor checks use deterministic host/runtime correctness traces. Chromecast 2 currently requires local setup. CPU repeats are exploratory single runs; do not infer statistical certainty from small deltas.

## Phase 0 scenarios

| Scenario | FPS | p95 present ms |
|---|---:|---:|
| wide-idle | 14.681 | 83.417 |
| close-idle | 14.514 | 83.417 |
| crawl-close | 14.363 | 83.417 |
