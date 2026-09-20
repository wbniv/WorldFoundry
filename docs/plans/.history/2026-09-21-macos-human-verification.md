| Date | Change |
|------|--------|
| [2026-09-21](https://github.com/wbniv/WorldFoundry/commit/1882bb0f) | ci(macos): publish the .app bundle, plus the human-verification runbook |

<!--history-meta v1
1882bb0f	author	Will Norris
1882bb0f	added	81
1882bb0f	deleted	0
1882bb0f	files	1
1882bb0f	body	The macos-desktop-debug artifact list said `engine/wf_game`, which on\nmacOS matches nothing -- the Mach-O lives inside engine/wf_game.app --\nso every artifact zip so far (~200 KB) was logs and PNGs with no app in\nit. Publish the bundle instead; it carries cd.iff/level0.mid in\nContents/Resources so it can be double-clicked.\n\nPhase 4's CI proxy gate is met; its real exit ("an interactive .app\nthat plays snowgoons") needs a human on a Mac for what CI cannot\nexercise: Retina (runner is scale 1.0), input, close paths,\n-fullscreen, and the NSBundle cd.iff double-click path. The runbook is\nthat one ask, with a checklist whose rows map to the two open TODO\nitems.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
-->
