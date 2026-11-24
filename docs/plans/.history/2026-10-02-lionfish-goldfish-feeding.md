| Date | Change |
|------|--------|
| [2026-11-01](https://github.com/wbniv/WorldFoundry/commit/7a68013ff) | Lionfish: the Director releases a goldfish 45-60 s after the tank empties |
| [2026-10-02](https://github.com/wbniv/WorldFoundry/commit/9cef6dded) | Integrate aquarium tanks, feeding, and flowing betta fins |

<!--history-meta v1
7a68013ff	author	Will Norris
7a68013ff	added	2
7a68013ff	deleted	0
7a68013ff	files	1
7a68013ff	body	gf-tick now runs a Director-owned countdown (gf-auto-tick) while gf-count\nis 0: each countdown draws a fresh 45-60 s from a 15-bit LCG seeded at\ngf-setup, counts DELTA_TIME clamped to 0.2 s per tick, and calls\ngf-release-one at the deadline (retrying 2 s later, unlogged, when no\nspawn point is clear). A live or reserved goldfish holds it at 0; a\nmanual A+DOWN release pre-empts it. Mailboxes 980-982 are asserted\ndisjoint from every other consumer; LIONFISH_AUTO_GOLDFISH=0 opts out.\n\nHost Forth tests cover the seven cases; regenerated lionfish outputs and\nthe selector bundle (host route, byte-identical to the container on\nunchanged inputs).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqSWpcGmU9ZTVy7HDyx
9cef6dded	author	Will Norris
9cef6dded	added	193
9cef6dded	deleted	0
9cef6dded	files	1
9cef6dded	body	Package the seven-tank selector with tiger-barb schooling, the new tank assets, lionfish goldfish feeding, and the optimized opaque betta fin rig. Preserve the Asian Arowana tank.\n\nMake short Back return from a selected level to its selector; Back on the selector exits. Update pairing help and retain verified desktop/device captures, profiling comparisons, and the runtime-mesh A3 betta poster.\n\nValidation: 172 aquarium, renderer, feeding, and menu regression tests passed; one skipped. The texture RGBA test passed. Desktop and Chromecast selection/Back/resume checks and fin-motion captures passed; installed release hashes were verified.
-->
