| Date | Change |
|------|--------|
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/be2470783) | WF Clocks replaces the minutemachine flavor |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/c2562c13a) | Clocks: every level carries a settings object (D13), and the audit that found none do |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/4d2e8130a) | TODO: Minute Machine physics realism; trig plan: Espressif FPU table verified |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/f8ccaa124) | Minute Machine: fix the hour 9 drawing as 8 on cast1; guard test for card depth |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/9124cceff) | Forth trig words plan; Minute Machine plan records what was built |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/74075aca1) | Minute Machine phase 2: timeline model and pure tests |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/ab7a7e944) | Minute Machine plan approved: D1–D10 accepted; index row and captured deferrals |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/0d6063b86) | Minute Machine plan: a sixty-second chain reaction that drops the minute flap |

<!--history-meta v1
be2470783	author	Will Norris
be2470783	added	2
be2470783	deleted	0
be2470783	files	1
be2470783	body	Decision D2: one app for the clocks. Removed: the minutemachine flavor\n(org.worldfoundry.minutemachine), its source set, MinuteMachineActivity,\nMinuteMachineDreamService, MinuteMachineSettingsProvider,\nscripts/pack-minute-machine-bundle.py, task build-minute-machine-apk and\nthe minutemachine-screensaver-cd.iff ignore line. Its icons, banner and\nstrings live on under src/clocks (copied in the flavor commit);\ngen-screensaver-android-icons.py now writes the `clocks` flavor from the\nsame Minute Machine art. The sixty-second plan gets a superseded note.\nThe old package must still be uninstalled from devices that have it.\n\ntests: the removal is pinned in test_clocks_screensaver_catalog.py, and\ntest_dream_host_vram.py pins the Aquarium's 11 tanks (range 0..10) and\nthe clocks roster from their manifests.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
c2562c13a	author	Will Norris
c2562c13a	added	1
c2562c13a	deleted	1
c2562c13a	files	1
c2562c13a	body	Will: "make sure level has a settings object (same for all clocks---audit)". Audited both\nclocks against the pattern the Planted, Jellyfish, Reef and Sea Stars levels use (an .oas type\nwith live fields, one placed object, property@ in the director, a capabilities asset for the\nphone form, a live-field test). Neither Minute Machine nor Tide Harbour has any of the six.\nscripts/audit-clock-settings.py checks all six per clock; its own test builds a fake tree\nthat passes and removes each piece to see exactly that check flip.\n\nPlan: D13, a Settings objects section (the standard, the audit, a common Clock sheet),\nPhase 2b for Minute Machine's retrofit, LevelSettings becoming a factory by clock id in\nPhase 3, verification steps 12-13, and open question Q9 (what clocks share). The Minute\nMachine plan's D10 is marked superseded for the settings object. TODO item added.\n\nAlso: the tide fit now writes the time-error, longest-gap and error-by-waves-kept numbers the\nposter will print, and the research document's time-zone claim is corrected (the GLOSS\nhandbook verifies Ko Lak's zone; the UHSLC file's own clock is not stated on any page read).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
4d2e8130a	author	Will Norris
4d2e8130a	added	1
4d2e8130a	deleted	0
4d2e8130a	files	1
4d2e8130a	body	Will, 2026-11-21: the marble down the ramp and the dominoes fall too slowly\nto be realistic. A rolling sphere on the same rails would take about 5.5 s\nagainst 10.8 s in the model, so this is a TODO item with the numbers, ranked T4\nbecause realism and the 60 s budget pull against each other.\n\nWill asked to verify the Espressif FPU row. Verified against Espressif's own\ndeveloper article (FPU on ESP32, S3, H4, P4; none on S2, C2, C3, C5, C6, C61,\nH2; every Espressif FPU single-precision only), corrected the row (the first\nversion missed the H4, P4, C5 and C61) and cited the sources.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
f8ccaa124	author	Will Norris
f8ccaa124	added	1
f8ccaa124	deleted	1
f8ccaa124	files	1
f8ccaa124	body	Found by reading the real cast1 screenshot: fallen flap cards were 18 mm\nthick with art 10 mm proud, stacked 10 mm apart, so the art of a card behind\ncame out level with the front card's face and the lower-left bar of an 8 showed\nthrough a 9. Cards are now 8 mm thick with art 4 mm proud, stacked 16 mm apart,\nthe housing back plate moves back to fit, and tests/test_minute_machine_parts.py\nfails if the spacing is not more than a card's thickness plus its art.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
9124cceff	author	Will Norris
9124cceff	added	17
9124cceff	deleted	1
9124cceff	files	1
9124cceff	body	Draft plan for the full trig set in the zForth bridge (cos, tan, asin, acos,\natan, atan2, sincos, sqrt beside sin-rev): exact at the quarter turns, loud\non a domain error, one shared header. Eight decisions wait for Will.\nThe Minute Machine plan gains a section on where the build differs from the\nplan, and its TODO line is updated.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
74075aca1	author	Will Norris
74075aca1	added	3
74075aca1	deleted	3
74075aca1	files	1
74075aca1	body	timeline.py is the one table of times and the pose of every piece as a\nfunction of the second of the day. 13 tests: loop closure at minute, hour\nand midnight, a 2 ms continuity sweep, every contact, the hour cascade,\nthe midnight flutter, and the plan's pose table. Plan corrected where the\nmodel disagreed: comb step 0.46 s for 24 dominoes, card back is the digit\nafter, and the half-way comb moment is 10:08:47.\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
ab7a7e944	author	Will Norris
ab7a7e944	added	2
ab7a7e944	deleted	2
ab7a7e944	files	1
ab7a7e944	body	Will, 2026-11-21: "D1-10: accept recommendations", then "implement /\ndeploy / commit / push". TODO item is now in progress.\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
0d6063b86	author	Will Norris
0d6063b86	added	329
0d6063b86	deleted	0
0d6063b86	files	1
0d6063b86	body	Draft plan for idea 17 of the 3D timepieces brainstorm (homeboard-tv),\nas a World Foundry level and a fourth Dream flavor. Every pose is\ncomputed from the clock; no simulation. Four mockups, one of them\nrunning live from the clock. D1 to D10 wait for Will; the time-of-day\nmailboxes are pre-approved.\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
-->
