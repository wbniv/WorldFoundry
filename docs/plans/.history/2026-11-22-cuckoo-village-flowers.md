| Date | Change |
|------|--------|
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/a377e5243) | Move the flowers' level-of-detail follow-up to its own plan; TODO item |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/cfd8ed997) | Flowers: the village profiled on cast1 (30 fps both ways) and the generated report |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/996161a1c) | Flowers: report --trim, and the profiling method as tested on cast1 |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/d3888eaf3) | Flowers plan: the measured level size, and the village has no phone capabilities asset |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/1baac8b47) | Flowers: the lean geranium box keeps all four edelweiss tufts |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/17f524009) | Flowers: edelweiss spread across the geranium boxes; render times; plan index row; LOD wording |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/e0dde64b8) | Flowers: no ivy geraniums, more edelweiss on geranium boxes; LOD follow-up in the plan; rename landing recorded |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/bbb012df4) | Flowers: a real geranium (round umbels on tall stems, big round leaves, ivy trailing stems) |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/cfd09533b) | Flowers: one box in three is a geranium box; plan, renders and render times updated |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/acbfbc867) | Flowers plan: a Detailed flowers setting, profiling Off then On then Off on cast1, and a generated report |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/1a2df75c7) | Flowers plan: per-piece triangles per material, and what one flower costs |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/0cd9d6ddc) | Cuckoo Village window boxes: plan and prototype for trailing petunias and edelweiss |

<!--history-meta v1
a377e5243	author	Will Norris
a377e5243	added	3
a377e5243	deleted	104
a377e5243	files	1
a377e5243	body	Will, 2026-11-22: "move LOD follow-up to its own plan; add to TODO". The section moves unchanged apart from\nreferences to the parent plan; the flowers plan keeps a pointer.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
cfd8ed997	author	Will Norris
cfd8ed997	added	22
cfd8ed997	deleted	1
cfd8ed997	files	1
cfd8ed997	body	Will: "30 fps is fine. if i want more, we'll just analyze things in more detail later". Three profile jobs of the village on\nthe installed window-box build: the field On 29.96 fps, Off 29.97 and 29.97, a median frame of 33.37 ms in all three\n(the Chromecast HD presents the village at 30 fps), so scripts/flowers-profile-report.py with --trim 85 and --fps-floor\n29.5 says PASS. What it cannot show is a cost under one refresh, and each set is one run with a 45 s window; the plan says\nso and records every verification step, including step 7 (the level grew 0.756 MB against 0.75).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
996161a1c	author	Will Norris
996161a1c	added	54
996161a1c	deleted	57
996161a1c	files	1
996161a1c	body	A scripted run's key presses must fit inside its duration, so the menu, the level load and the settings form are inside\nthe measured window. The report script gains --trim N: it drops the first N seconds of every run and recomputes fps,\nthe percentiles and the missed-refresh share from the per-frame present times (a missed refresh is an interval over 1.5\nrefresh periods, matching the profile job). The plan's method now says so: each run sets Detailed flowers from the TV\nform by key script (tested on cast1: seven rows, default On, Left turns it Off), runs 305 s, and the report trims the\nfirst 80 s, leaving one 225 s lap. The village has no phone capabilities asset, so screensaver-setting-set does not reach it.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
d3888eaf3	author	Will Norris
d3888eaf3	added	48
d3888eaf3	deleted	48
d3888eaf3	files	1
d3888eaf3	body	The built level is 5,738,496 bytes against 4,982,784: +755,712, of which the flowers mesh is 582,072 bytes (34 bytes a\ntriangle) and the blocks mesh 183,544. The first estimate (+0.60 MB, from the candles' 28 bytes a triangle) was a quarter\nlow. The village has no phone capabilities asset, so the persistent screensaver-setting-set route does not reach the new field.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
1baac8b47	author	Will Norris
1baac8b47	added	9
1baac8b47	deleted	9
1baac8b47	files	1
1baac8b47	body	Will, 2026-11-22: "4 edelweiss in geranium lean box". Lean geranium boxes now have 4 tufts of 1 head (355 triangles,\nwas 277; petunia lean 332), 8,839 lean triangles in all (+6.4 % on the level); the lean per-box test limit is 360.\nPlan numbers, the lean picture and the lean geranium render time are regenerated.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
17f524009	author	Will Norris
17f524009	added	13
17f524009	deleted	11
17f524009	files	1
17f524009	body	Will, 2026-11-22: "maybe edelweiss more distributed across the box?" A geranium box now alternates its five\nupright geraniums and four edelweiss tufts across the whole width (pitch 0.13 m), counts unchanged (683, petunia 649).\nThe plan's follow-up now says today's Journey camera rarely gives a close look and that a closer camera is expected,\nso Phase 0 defers instead of stopping and a closer test lap joins the profiling (54 laps, about 3.6 hours). Render\ntimes regenerated (CPU seconds 1,315 after against 1,309 before). docs/plans/README.md gains the plan's row.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
e0dde64b8	author	Will Norris
e0dde64b8	added	130
e0dde64b8	deleted	27
e0dde64b8	files	1
e0dde64b8	body	Will, 2026-11-22: "i don't like the ivy geraniums; get rid of them", "add more edelweiss in the geranium boxes\ninstead", "add a followup to the plan: LOD model replacement with lots of profiling". A geranium box is now 5\nupright geraniums and 4 edelweiss tufts (683 triangles, petunia box 649), 17,180 in all (+18.2 % on the level);\n12 tests. The plan gains the follow-up: the camera is never nearer than 7.1 m to a cottage (median nearest 12.2 m),\nfour LOD arrangements, about 3 hours of cast1 profiling and a four-rule decision. TODO records the Clocks package\nrename as READY on the unpushed branch clocks-package-rename with the agreed landing order.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
bbb012df4	author	Will Norris
bbb012df4	added	25
bbb012df4	deleted	25
bbb012df4	files	1
bbb012df4	body	Will, 2026-11-22: "that's not what geraniums look like". The first geranium was a few big separate stars. Now an\nupright geranium is a thick stem with four round leaves and a dense dome of seven five-triangle florets, and the\nivy geranium trails with pointed leaves and two loose heads. A geranium box is 697 triangles (petunia box 649),\n17,306 in all (+18.4 % on the level), still inside the 700 a box budget. Eleven tests. Plan renders, tables,\nand render times (CPU seconds: after 1,344 against before 1,309) regenerated.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
cfd09533b	author	Will Norris
cfd09533b	added	57
cfd09533b	deleted	44
cfd09533b	files	1
cfd09533b	body	Will, 2026-11-22: "make 1/3 of the flowerboxes germaniums and edelweiss, so need a new model for germanium after all".\nflowers.py gains an upright geranium and a trailing ivy geranium (floret of 14 triangles) and box_kind(): boxes 0, 3,\n6 ... are geranium boxes (9 of 26, 680 triangles each), the rest petunia boxes (649). Ten flat materials, eight\ndouble-sided; 17,153 triangles in all. The builder counts its pieces so the plan's tables come from the code. Ten\ntests. The plan has the geranium renders, a two-kind lean comparison, per-piece budgets, and render times as CPU\nseconds (the wall times were taken under a machine load of 18 to 31 and are not comparable).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
acbfbc867	author	Will Norris
acbfbc867	added	93
acbfbc867	deleted	27
acbfbc867	files	1
acbfbc867	body	Will, 2026-11-22: "add profiling before and after (just stick the flowers on an actual settings toggle) and\ngenerate report comparing difference after implementation". The plan now keeps today's blocks as a second actor\nshown when the new field is Off, so one APK is measured both ways; it specifies the profile runs (3 x 225 s per\nstate, whole camera laps, Off/On/Off to catch drift), the gate, and flowers-profile-report.py with the sections\nthe report will contain. Verification steps rewritten to match. No code changed.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
1a2df75c7	author	Will Norris
1a2df75c7	added	28
1a2df75c7	deleted	13
1a2df75c7	files	1
1a2df75c7	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
0cd9d6ddc	author	Will Norris
0cd9d6ddc	added	154
0cd9d6ddc	deleted	0
0cd9d6ddc	files	1
0cd9d6ddc	body	Will, 2026-11-22: "model the flowers with more polygons", "i don't like geraniums", "Petunias and Edelweiss".\nflowers.py builds a box of flowers as flat-coloured triangles (649 a box against about 164 today, 16,874 for the 26\nboxes, nine materials, seven double-sided), with a lean fallback of 332 a box; eight tests hold the budget, the\nbounds and the geometry. flowers_prototype.py renders the cottage before and after in Cycles. The plan has the\nrenders, the budgets, the materials, the render times and a cast1 frame-time gate. The level build is untouched.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
-->
