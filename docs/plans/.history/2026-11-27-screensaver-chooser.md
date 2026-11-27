| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/8b8637c7a) | plan: Will decides the screensaver chooser (D4: no Random row) |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/88befddc5) | Plan: Aquarium and Clocks screensaver chooser behind the Dream's settings link |

<!--history-meta v1
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
