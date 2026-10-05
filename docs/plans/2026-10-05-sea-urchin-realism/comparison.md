# Sea-urchin phase comparison

Performance evidence comes exclusively from Chromecast 1. Desktop captures check geometry, contacts and movement correctness; desktop load/FPS is not used. Fixed native library hashes, saltwater seed 713, plant age 150, growth speed 0, existing water sway. Three release repeats and one separately instrumented repeat per phase; each repeat contains 60 seconds each of wide idle, close idle and cardinal crawl. CPU values are reported separately from presented-frame pacing.

| Phase | Animal / scene actors | Animal source triangles | FPS | Δ FPS % | p95 present ms | Actor CPU ms | Render CPU ms | PSS MiB | Δ actor CPU ms | Δ render CPU ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 9 / 38 | 860 | 14.520 | 0.000 | 83.417 | 1.313 | 55.111 | 77.952 | 0.000 | 0.000 |
| 1 | 9 / 38 | 3540 | 13.722 | -5.496 | 83.417 | 1.287 | 58.919 | 70.220 | -0.026 | 3.809 |
| 2 | 9 / 38 | 3540 | 13.639 | -6.065 | 83.417 | 1.303 | 58.936 | 78.207 | -0.010 | 3.825 |
| 3 | 17 / 46 | 3540 | 13.514 | -6.923 | 83.417 | 1.473 | 59.403 | 79.923 | 0.160 | 4.292 |

Source triangle counts can differ from cooked meshes. Presented p95 is frame interval, not CPU time. The coordinator’s reviewed plants trace uses cardinal key events; diagonal, reversal and anchor checks use deterministic host/runtime correctness traces. Chromecast 2 currently requires local setup. CPU repeats are exploratory single runs; do not infer statistical certainty from small deltas.

## Instrumented script and rendering cost

| Phase | Director CPU ms | Δ Director CPU ms | Plant animation CPU ms | Actor mailbox writes/frame | Render actors/frame | Draws/frame | Rendered triangles/frame |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6.971 | 0.000 | 6.784 | 29.000 | 26.000 | 25.000 | 23827.064 |
| 1 | 6.960 | -0.012 | 6.772 | 29.000 | 26.000 | 19.000 | 25159.962 |
| 2 | 7.336 | 0.365 | 6.760 | 53.000 | 26.000 | 19.000 | 25154.234 |
| 3 | 7.559 | 0.588 | 6.739 | 93.000 | 34.000 | 27.000 | 25154.464 |

Director CPU includes its Forth and runtime plant calls. The animation section measures existing runtime plant animation and overlaps Director CPU; do not add it again. These counters cover the whole planted scene, not an isolated animal. Source animal triangles and rendered scene triangles are distinct.

## Phase 0 scenarios

| Scenario | FPS | p95 present ms |
|---|---:|---:|
| wide-idle | 14.681 | 83.417 |
| close-idle | 14.514 | 83.417 |
| crawl-close | 14.363 | 83.417 |

## Phase 1 scenarios

| Scenario | FPS | p95 present ms |
|---|---:|---:|
| wide-idle | 13.813 | 83.417 |
| close-idle | 13.733 | 83.417 |
| crawl-close | 13.605 | 83.417 |

## Phase 2 scenarios

| Scenario | FPS | p95 present ms |
|---|---:|---:|
| wide-idle | 13.717 | 83.417 |
| close-idle | 13.667 | 83.417 |
| crawl-close | 13.511 | 83.417 |

## Phase 3 scenarios

| Scenario | FPS | p95 present ms |
|---|---:|---:|
| wide-idle | 13.583 | 83.417 |
| close-idle | 13.567 | 83.417 |
| crawl-close | 13.399 | 83.417 |
