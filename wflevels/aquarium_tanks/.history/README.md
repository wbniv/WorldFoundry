| Date | Change |
|------|--------|
| [2026-10-05](https://github.com/wbniv/WorldFoundry/commit/1feaf974) | Implement single-mesh lionfish rig and suction feeding |
| [2026-10-04](https://github.com/wbniv/WorldFoundry/commit/8d165c7c) | Record plant atlas resolution profiles and retain 256 default |
| [2026-10-04](https://github.com/wbniv/WorldFoundry/commit/e45a7ac1) | Reconcile plant docs with implemented runtime and final texture measurements |
| [2026-10-04](https://github.com/wbniv/WorldFoundry/commit/0aa37847) | Add seeded growing plant tank, settings and leaf textures |
| [2026-10-02](https://github.com/wbniv/WorldFoundry/commit/9cef6dde) | Integrate aquarium tanks, feeding, and flowing betta fins |

<!--history-meta v1
1feaf974	author	Will Norris
1feaf974	added	51
1feaf974	deleted	1
1feaf974	files	1
1feaf974	body	Add selective native fin/jaw deformation, shared 256px texture maps and stable\nper-fish palettes. Preserve translucent batching across palette changes and\nintegrate transient suction, swept mouth capture and intraoral transport.\n\nInclude rebuilt Aquarium assets, the updated A3 poster, documented engine\napproval and permission rule, and baseline/final profiles on both Chromecasts.\nFix the separately approved debug-bridge command initialization and bounds.\n\nValidation: 57 tests passed; native feeding checks and all eight selector,\nBack-to-menu and Home/resume checks passed on both Chromecasts. Final normal\nAPK restored and verified on both devices. Cast1 retains about 30 FPS; cast2\nruns about 40 FPS versus 60 in the controlled baseline, as reported.
8d165c7c	author	Will Norris
8d165c7c	added	15
8d165c7c	deleted	0
8d165c7c	files	1
e45a7ac1	author	Will Norris
e45a7ac1	added	12
e45a7ac1	deleted	6
e45a7ac1	files	1
0aa37847	author	Will Norris
0aa37847	added	8
0aa37847	deleted	0
0aa37847	files	1
9cef6dde	author	Will Norris
9cef6dde	added	38
9cef6dde	deleted	0
9cef6dde	files	1
9cef6dde	body	Package the seven-tank selector with tiger-barb schooling, the new tank assets, lionfish goldfish feeding, and the optimized opaque betta fin rig. Preserve the Asian Arowana tank.\n\nMake short Back return from a selected level to its selector; Back on the selector exits. Update pairing help and retain verified desktop/device captures, profiling comparisons, and the runtime-mesh A3 betta poster.\n\nValidation: 172 aquarium, renderer, feeding, and menu regression tests passed; one skipped. The texture RGBA test passed. Desktop and Chromecast selection/Back/resume checks and fin-motion captures passed; installed release hashes were verified.
-->
