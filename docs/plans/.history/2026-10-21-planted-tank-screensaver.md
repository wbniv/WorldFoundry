| Date | Change |
|------|--------|
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/bab64a7d) | Planted Tank plan: record Phase 2a and 3 as done |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/8671b5c7) | Planted Tank plan: fold in S4 (plants-only variant) and log the Aquarium catalog bug |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/c78fdf31) | Planted Tank plan: plants only, generic seam approved, hold stays a parameter |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/4e8c5333) | Planted Tank plan: drop the cycles parameter |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/7c218a95) | Planted Tank plan: fold in S1/S2 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/5b330d11) | Screensaver host hides the engine overlay (seed strip, settings, menu) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/c2b0f95d) | Planted Tank plan: record maturity sweep and S3 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/4266a44c) | Plan the Planted Tank screensaver |

<!--history-meta v1
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
