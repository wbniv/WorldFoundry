| Date | Change |
|------|--------|
| [2026-09-21](https://github.com/wbniv/WorldFoundry/commit/f88573c2) | docs(macos): human verification runs over Codemagic VNC — nobody has a Mac |
| [2026-09-21](https://github.com/wbniv/WorldFoundry/commit/1882bb0f) | ci(macos): publish the .app bundle, plus the human-verification runbook |

<!--history-meta v1
f88573c2	author	Will Norris
f88573c2	added	27
f88573c2	deleted	2
f88573c2	files	1
f88573c2	body	Reframe the Phase 4 human-verification runbook around the path that\nactually exists: a VNC session on the build runner. Per Codemagic's\nremote-access docs the VM stays connectable for 10 min after the steps\nfinish and a connected session lives until max_build_duration, so raise\nmacos-desktop-debug's limit from 20 to 60 (unattended runs still end at\n~4 min). Rows 2-6 of the checklist close over VNC; Retina cannot (the\nrunner is scale 1.0) and stays parked on real hardware. Index the plan.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
1882bb0f	author	Will Norris
1882bb0f	added	81
1882bb0f	deleted	0
1882bb0f	files	1
1882bb0f	body	The macos-desktop-debug artifact list said `engine/wf_game`, which on\nmacOS matches nothing -- the Mach-O lives inside engine/wf_game.app --\nso every artifact zip so far (~200 KB) was logs and PNGs with no app in\nit. Publish the bundle instead; it carries cd.iff/level0.mid in\nContents/Resources so it can be double-clicked.\n\nPhase 4's CI proxy gate is met; its real exit ("an interactive .app\nthat plays snowgoons") needs a human on a Mac for what CI cannot\nexercise: Retina (runner is scale 1.0), input, close paths,\n-fullscreen, and the NSBundle cd.iff double-click path. The runbook is\nthat one ask, with a checklist whose rows map to the two open TODO\nitems.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
-->
