| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/4b0f203ba) | plan: chooser steps 5 and 6 pass on Cast1 |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/69875b7a1) | plan: chooser step 6 partial on Cast1: notice and drawn clock pass; shipped reinstall refused |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/ce5f3ea8b) | plan: chooser step 5 partial: Cast1's Dream plays the saved clock |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/9146728df) | plan: chooser step 8 deferred; why the coordinator cannot drive Settings on the Pixel |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/a32e41531) | plan: chooser step 8: phone screensaver plays only while charging; no Random row; no uiautomator dump |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/fb84f198a) | plan: screensaver chooser Verification 9 and 10 pass on Cast1 |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/a66b87250) | todo, plan: screensaver chooser built and merged; APK and devices left |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/1539de805) | plan: one data-driven chooser for every WF screensaver bundle |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/8b8637c7a) | plan: Will decides the screensaver chooser (D4: no Random row) |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/88befddc5) | Plan: Aquarium and Clocks screensaver chooser behind the Dream's settings link |

<!--history-meta v1
4b0f203ba	author	Will Norris
4b0f203ba	added	26
4b0f203ba	deleted	0
4b0f203ba	files	1
4b0f203ba	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqP8zNDXFEqEEztS56o
69875b7a1	author	Will Norris
69875b7a1	added	20
69875b7a1	deleted	0
69875b7a1	files	1
69875b7a1	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqP8zNDXFEqEEztS56o
ce5f3ea8b	author	Will Norris
ce5f3ea8b	added	12
ce5f3ea8b	deleted	0
ce5f3ea8b	files	1
ce5f3ea8b	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqP8zNDXFEqEEztS56o
9146728df	author	Will Norris
9146728df	added	1
9146728df	deleted	0
9146728df	files	1
9146728df	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqP8zNDXFEqEEztS56o
a32e41531	author	Will Norris
a32e41531	added	5
a32e41531	deleted	0
a32e41531	files	1
a32e41531	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqP8zNDXFEqEEztS56o
fb84f198a	author	Will Norris
fb84f198a	added	27
fb84f198a	deleted	0
fb84f198a	files	1
fb84f198a	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqP8zNDXFEqEEztS56o
a66b87250	author	Will Norris
a66b87250	added	2
a66b87250	deleted	0
a66b87250	files	1
a66b87250	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQzN1oGqYJXjCkzVJ1
1539de805	author	Will Norris
1539de805	added	21
1539de805	deleted	0
1539de805	files	1
1539de805	body	Will: reuse the same chooser code for the Aquarium, WF Clocks and every\nfuture World Foundry screensaver bundle. The plan now says everything per-app\nis data (roster, provider authority, level setting id), a bundle with more\nthan one level declares it, adding it is a README how-to, and a source guard\nkeeps bundle names out of the chooser.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQzN1oGqYJXjCkzVJ1
8b8637c7a	author	Will Norris
8b8637c7a	added	10
8b8637c7a	deleted	1
8b8637c7a	files	1
8b8637c7a	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQzN1oGqYJXjCkzVJ1
88befddc5	author	Will Norris
88befddc5	added	190
88befddc5	deleted	0
88befddc5	files	1
88befddc5	body	A design plan, no code. Each app gets a plain Android list (no engine\nchange) declared through settingsActivity in a new res/xml/dream_chooser.xml,\nso Homeboard's Open <app> settings and a phone's screensaver picker open it.\nIt reads and writes the saved choice through the app's own shell-or-own-uid\nsettings provider, so the provider stays the only writer and the coordinator\nsees no change. Ten decisions for Will (D1-D10) with recommendations; seven\nself-contained mockups (TV states, phone, Thai, long names and 2.0x text)\nwith PNGs checked by Homeboard's plan-mockup-check. TODO item updated to link\nthe plan and say it waits on those decisions; plan index row added.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQzN1oGqYJXjCkzVJ1
-->
