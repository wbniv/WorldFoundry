| Date | Change |
|------|--------|
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/ece919b33) | Close Planted Tank screensaver: PSS-spread gate dropped by Will |
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/d4f67e2f1) | Planted soak: phase-binned analysis and phase-locked repeat, still over 4 MiB |
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/ea9977734) | Planted soak: continuous-sampling repeat on cast2 fails the 4 MiB PSS gate |
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/943d8799c) | Record runtime editing device follow-ups and scoped proposals |
| [2026-10-25](https://github.com/wbniv/WorldFoundry/commit/996c93509) | docs: Planted Tank device results on cast1 (install, overrides, saltwater save, natural Dream) |
| [2026-10-22](https://github.com/wbniv/WorldFoundry/commit/749e3bbfa) | docs: refresh planted tank verification status |
| [2026-10-22](https://github.com/wbniv/WorldFoundry/commit/80f43e987) | Use generic Settings catalogs for screensaver controls |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/919907508) | Planted Tank plan: Phase 4b now lists the coordinator registration entries |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/848fd3370) | Planted Tank plan: record Phase 5 device verification (blocked on coordinator registration) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/b2064b674) | Planted Tank plan: APK settings come from the OAD (settings-class objects, all fields) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/45d2dc5bc) | Planted Tank plan: record the final icon art (plants-only capture) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/a305858d5) | Planted Tank plan: record desktop cycle results (steps 4 and 5) and Phase 4a done |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/3153e8cd2) | Planted Tank plan: repair two Approach rows overwritten by status edits |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/81969d57d) | Planted Tank plan: record Phase 2b done; coordinator registration and two-ABI build needed |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/bdce4dd02) | Planted Tank: builder links the flavor asset; plan records Phase 1 done |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/52a74afea) | Planted Tank plan: record Phase 2c as done, with step 13 output |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/bab64a7db) | Planted Tank plan: record Phase 2a and 3 as done |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/8671b5c77) | Planted Tank plan: fold in S4 (plants-only variant) and log the Aquarium catalog bug |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/c78fdf31c) | Planted Tank plan: plants only, generic seam approved, hold stays a parameter |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/4e8c5333a) | Planted Tank plan: drop the cycles parameter |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/7c218a955) | Planted Tank plan: fold in S1/S2 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/5b330d114) | Screensaver host hides the engine overlay (seed strip, settings, menu) |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/c2b0f95d7) | Planted Tank plan: record maturity sweep and S3 spike results |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/4266a44c3) | Plan the Planted Tank screensaver |

<!--history-meta v1
ece919b33	author	Will Norris
ece919b33	added	2
ece919b33	deleted	0
ece919b33	files	1
ece919b33	body	Steps 8 and 10 pass; step 9's same-PID and no-crash conditions pass in both\ncast2 soaks. Will, 2026-11-13: the PSS-spread condition isn't important;\nmemory is covered by resource tracking (allocations freed) instead.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
d4f67e2f1	author	Will Norris
d4f67e2f1	added	19
d4f67e2f1	deleted	0
d4f67e2f1	files	1
d4f67e2f1	body	Binning J-bf9150654784 by phase (device clock: tank markers and the GC\nline dumpsys meminfo forces) puts the 11.8 MiB spread in the hold,\nwhere GL mtrack dips 10 MiB. The phase-locked repeat J-dadba4fb4900\n(one sample per tank at 20 s, sd 0.84 s) on cast2: 50 reloads, PID\n1221, no crash; final-ten-minute spread 6,784 KiB (limit < 4,096).\nGL mtrack is flat; one -4,552 KiB Code PSS step makes up most of it.\ncast2 settings and selection restored and read back.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
ea9977734	author	Will Norris
ea9977734	added	29
ea9977734	deleted	0
ea9977734	files	1
ea9977734	body	The 914.8 s gap in J-c21e98845289 was the host laptop suspending\n(09:30-09:45 +0700) under a sampler timed with time.monotonic().\nThe repeat holds a systemd-inhibit sleep:idle lock, times on the wall\nclock and aborts on gaps over 60 s. J-bf9150654784: 50 reloads, PID\n30527 throughout, no crash; final-ten-minute PSS spread 11,848 KiB\n(34 samples, largest gap 20.6 s), mostly GL mtrack. Limit unchanged.\ncast2 settings and Seahorse Grid selection restored and read back.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
943d8799c	author	Will Norris
943d8799c	added	16
943d8799c	deleted	0
943d8799c	files	1
996c93509	author	Will Norris
996c93509	added	24
996c93509	deleted	2
996c93509	files	1
996c93509	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01PkFSbo6jcue9Gfyb6U9HVs
749e3bbfa	author	Will Norris
749e3bbfa	added	20
749e3bbfa	deleted	20
749e3bbfa	files	1
80f43e987	author	Will Norris
80f43e987	added	9
80f43e987	deleted	9
80f43e987	files	1
919907508	author	Will Norris
919907508	added	1
919907508	deleted	1
919907508	files	1
919907508	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
848fd3370	author	Will Norris
848fd3370	added	53
848fd3370	deleted	0
848fd3370	files	1
848fd3370	body	Steps 6, 10 (pixel test), 12 and 14 (actor map) recorded with raw output.\nThe two-ABI build passes; the coordinator rejects org.worldfoundry.plantedtank\n("APK package is not registered"), so steps 7-9, 11 and the device halves of\n10 and 14 are NOT RUN. Aquarium and Seahorse Grid still start on cast2.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
b2064b674	author	Will Norris
b2064b674	added	1
b2064b674	deleted	1
b2064b674	files	1
b2064b674	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
45d2dc5bc	author	Will Norris
45d2dc5bc	added	2
45d2dc5bc	deleted	2
45d2dc5bc	files	1
45d2dc5bc	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
a305858d5	author	Will Norris
a305858d5	added	29
a305858d5	deleted	1
a305858d5	files	1
a305858d5	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
3153e8cd2	author	Will Norris
3153e8cd2	added	5
3153e8cd2	deleted	5
3153e8cd2	files	1
3153e8cd2	body	My row matching hit the Approach table instead of the phase table: rows 3\nand 4 (Grown, Keep onscreen 2 minutes) are restored and the status lines go\non the phase table rows they belong to. Adds Phase 4b (coordinator registration).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
81969d57d	author	Will Norris
81969d57d	added	4
81969d57d	deleted	3
81969d57d	files	1
81969d57d	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
bdce4dd02	author	Will Norris
bdce4dd02	added	2
bdce4dd02	deleted	2
bdce4dd02	files	1
bdce4dd02	body	The planted bundle link is created like the Aquarium and Seahorse links\n(assets/ is made if missing). Plan: Phase 1 done; verification step 3 compares\ngenerator output, since the committed aquarium_plants.lev is already stale.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
52a74afea	author	Will Norris
52a74afea	added	16
52a74afea	deleted	1
52a74afea	files	1
52a74afea	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
bab64a7db	author	Will Norris
bab64a7db	added	3
bab64a7db	deleted	3
bab64a7db	files	1
bab64a7db	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
8671b5c77	author	Will Norris
8671b5c77	added	11
8671b5c77	deleted	3
8671b5c77	files	1
8671b5c77	body	S4: use a generator flag; the screensaver variant has no settings catalog\n(Aquarium's Planted choice is always freshwater).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
c78fdf31c	author	Will Norris
c78fdf31c	added	44
c78fdf31c	deleted	37
c78fdf31c	files	1
c78fdf31c	body	Will's decisions: no urchin, goby or seahorses (drops the seahorses parameter\nand the actor-30 dependency); the generic launch-override table replaces host\nstaging; hold remains a parameter. Adds Spike S4 and Phase 2c. Mockups updated.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
4e8c5333a	author	Will Norris
4e8c5333a	added	6
4e8c5333a	deleted	9
4e8c5333a	files	1
4e8c5333a	body	The loop runs until the TV wakes; nothing needs a tank count. Tests count tanks\nfrom the log. Removes the host counter, the end-after-hold flag and the Settled\nstate.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
7c218a955	author	Will Norris
7c218a955	added	23
7c218a955	deleted	16
7c218a955	files	1
7c218a955	body	v1 needs no engine edit: the host stages the first tank before HALStart and\nlater tanks from the pump while planted::state() is inactive. Hold gets a new\nlevel-data field, cycles are counted by the host. Also corrects the\ntroubleshooting doc: a level's mailboxes 6000+ do not survive a reload.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
5b330d114	author	Will Norris
5b330d114	added	3
5b330d114	deleted	3
5b330d114	files	1
5b330d114	body	The planted tank's seed strip is drawn only while levelmenu::Drawer() is set.\ndream_host.cc owns WFAndroidPumpEvents(), so it clears the drawer each frame.\nHonouring gHudEnabled in the drawer was rejected: TV builds already set it to 0\nand would lose their level selector. No engine edit. Guard test added.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
c2b0f95d7	author	Will Norris
c2b0f95d7	added	19
c2b0f95d7	deleted	7
c2b0f95d7	files	1
c2b0f95d7	body	Maturity bound is 195 s (measured 103-193 s over 200 seeds). The seed strip\nis engine-drawn, so hiding it needs a generic engine edit; framing is a\ncamera text substitution (y -12 to -8.25). Mockups updated to match.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
4266a44c3	author	Will Norris
4266a44c3	added	192
4266a44c3	deleted	0
4266a44c3	files	1
4266a44c3	body	Third Dream flavor: a planted tank grows at 1x, stays 2 minutes, then the\nlevel ends and reloads as a new seeded tank. Parameters via am start extras\nand the settings provider; WF badge on icon and banner. Plan, mockups and\nTODO entry only; no code.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
-->
