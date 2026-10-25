| Date | Change |
|------|--------|
| [2026-10-22](https://github.com/wbniv/WorldFoundry/commit/749e3bbf) | docs: refresh planted tank verification status |
| [2026-10-22](https://github.com/wbniv/WorldFoundry/commit/80f43e98) | Use generic Settings catalogs for screensaver controls |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/91990750) | Planted Tank plan: Phase 4b now lists the coordinator registration entries |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/848fd337) | Planted Tank plan: record Phase 5 device verification (blocked on coordinator registration) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/b2064b67) | Planted Tank plan: APK settings come from the OAD (settings-class objects, all fields) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/45d2dc5b) | Planted Tank plan: record the final icon art (plants-only capture) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/a305858d) | Planted Tank plan: record desktop cycle results (steps 4 and 5) and Phase 4a done |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/3153e8cd) | Planted Tank plan: repair two Approach rows overwritten by status edits |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/81969d57) | Planted Tank plan: record Phase 2b done; coordinator registration and two-ABI build needed |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/bdce4dd0) | Planted Tank: builder links the flavor asset; plan records Phase 1 done |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/52a74afe) | Planted Tank plan: record Phase 2c as done, with step 13 output |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/bab64a7d) | Planted Tank plan: record Phase 2a and 3 as done |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/8671b5c7) | Planted Tank plan: fold in S4 (plants-only variant) and log the Aquarium catalog bug |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/c78fdf31) | Planted Tank plan: plants only, generic seam approved, hold stays a parameter |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/4e8c5333) | Planted Tank plan: drop the cycles parameter |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/7c218a95) | Planted Tank plan: fold in S1/S2 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/5b330d11) | Screensaver host hides the engine overlay (seed strip, settings, menu) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/c2b0f95d) | Planted Tank plan: record maturity sweep and S3 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/4266a44c) | Plan the Planted Tank screensaver |

<!--history-meta v1
749e3bbf	author	Will Norris
749e3bbf	added	20
749e3bbf	deleted	20
749e3bbf	files	1
80f43e98	author	Will Norris
80f43e98	added	9
80f43e98	deleted	9
80f43e98	files	1
91990750	author	Will Norris
91990750	added	1
91990750	deleted	1
91990750	files	1
91990750	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
848fd337	author	Will Norris
848fd337	added	53
848fd337	deleted	0
848fd337	files	1
848fd337	body	Steps 6, 10 (pixel test), 12 and 14 (actor map) recorded with raw output.\nThe two-ABI build passes; the coordinator rejects org.worldfoundry.plantedtank\n("APK package is not registered"), so steps 7-9, 11 and the device halves of\n10 and 14 are NOT RUN. Aquarium and Seahorse Grid still start on cast2.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
b2064b67	author	Will Norris
b2064b67	added	1
b2064b67	deleted	1
b2064b67	files	1
b2064b67	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
45d2dc5b	author	Will Norris
45d2dc5b	added	2
45d2dc5b	deleted	2
45d2dc5b	files	1
45d2dc5b	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
a305858d	author	Will Norris
a305858d	added	29
a305858d	deleted	1
a305858d	files	1
a305858d	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
3153e8cd	author	Will Norris
3153e8cd	added	5
3153e8cd	deleted	5
3153e8cd	files	1
3153e8cd	body	My row matching hit the Approach table instead of the phase table: rows 3\nand 4 (Grown, Keep onscreen 2 minutes) are restored and the status lines go\non the phase table rows they belong to. Adds Phase 4b (coordinator registration).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
81969d57	author	Will Norris
81969d57	added	4
81969d57	deleted	3
81969d57	files	1
81969d57	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
bdce4dd0	author	Will Norris
bdce4dd0	added	2
bdce4dd0	deleted	2
bdce4dd0	files	1
bdce4dd0	body	The planted bundle link is created like the Aquarium and Seahorse links\n(assets/ is made if missing). Plan: Phase 1 done; verification step 3 compares\ngenerator output, since the committed aquarium_plants.lev is already stale.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
52a74afe	author	Will Norris
52a74afe	added	16
52a74afe	deleted	1
52a74afe	files	1
52a74afe	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
bab64a7d	author	Will Norris
bab64a7d	added	3
bab64a7d	deleted	3
bab64a7d	files	1
bab64a7d	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
8671b5c7	author	Will Norris
8671b5c7	added	11
8671b5c7	deleted	3
8671b5c7	files	1
8671b5c7	body	S4: use a generator flag; the screensaver variant has no settings catalog\n(Aquarium's Planted choice is always freshwater).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
c78fdf31	author	Will Norris
c78fdf31	added	44
c78fdf31	deleted	37
c78fdf31	files	1
c78fdf31	body	Will's decisions: no urchin, goby or seahorses (drops the seahorses parameter\nand the actor-30 dependency); the generic launch-override table replaces host\nstaging; hold remains a parameter. Adds Spike S4 and Phase 2c. Mockups updated.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
4e8c5333	author	Will Norris
4e8c5333	added	6
4e8c5333	deleted	9
4e8c5333	files	1
4e8c5333	body	The loop runs until the TV wakes; nothing needs a tank count. Tests count tanks\nfrom the log. Removes the host counter, the end-after-hold flag and the Settled\nstate.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
7c218a95	author	Will Norris
7c218a95	added	23
7c218a95	deleted	16
7c218a95	files	1
7c218a95	body	v1 needs no engine edit: the host stages the first tank before HALStart and\nlater tanks from the pump while planted::state() is inactive. Hold gets a new\nlevel-data field, cycles are counted by the host. Also corrects the\ntroubleshooting doc: a level's mailboxes 6000+ do not survive a reload.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
5b330d11	author	Will Norris
5b330d11	added	3
5b330d11	deleted	3
5b330d11	files	1
5b330d11	body	The planted tank's seed strip is drawn only while levelmenu::Drawer() is set.\ndream_host.cc owns WFAndroidPumpEvents(), so it clears the drawer each frame.\nHonouring gHudEnabled in the drawer was rejected: TV builds already set it to 0\nand would lose their level selector. No engine edit. Guard test added.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
c2b0f95d	author	Will Norris
c2b0f95d	added	19
c2b0f95d	deleted	7
c2b0f95d	files	1
c2b0f95d	body	Maturity bound is 195 s (measured 103-193 s over 200 seeds). The seed strip\nis engine-drawn, so hiding it needs a generic engine edit; framing is a\ncamera text substitution (y -12 to -8.25). Mockups updated to match.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
4266a44c	author	Will Norris
4266a44c	added	192
4266a44c	deleted	0
4266a44c	files	1
4266a44c	body	Third Dream flavor: a planted tank grows at 1x, stays 2 minutes, then the\nlevel ends and reloads as a new seeded tank. Parameters via am start extras\nand the settings provider; WF badge on icon and banner. Plan, mockups and\nTODO entry only; no code.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
-->
