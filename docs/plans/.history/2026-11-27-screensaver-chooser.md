| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/a66b87250) | todo, plan: screensaver chooser built and merged; APK and devices left |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/1539de805) | plan: one data-driven chooser for every WF screensaver bundle |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/8b8637c7a) | plan: Will decides the screensaver chooser (D4: no Random row) |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/88befddc5) | Plan: Aquarium and Clocks screensaver chooser behind the Dream's settings link |

<!--history-meta v1
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
