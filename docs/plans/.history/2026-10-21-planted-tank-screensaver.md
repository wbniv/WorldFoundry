| Date | Change |
|------|--------|
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/7c218a95) | Planted Tank plan: fold in S1/S2 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/5b330d11) | Screensaver host hides the engine overlay (seed strip, settings, menu) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/c2b0f95d) | Planted Tank plan: record maturity sweep and S3 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/4266a44c) | Plan the Planted Tank screensaver |

<!--history-meta v1
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
