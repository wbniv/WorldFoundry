| Date | Change |
|------|--------|
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/094f53a6) | Reef plan: R0 device run P0–P3 on cast1; realistic 97-object load abort |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/ed2b171e) | Reef plan: W5 R0 spike results; D9 (where ReefSettings appears) |

<!--history-meta v1
094f53a6	author	Will Norris
094f53a6	added	77
094f53a6	deleted	0
094f53a6	files	1
094f53a6	body	Probes on copies of today's reef levels, three alternating runs each:\nhidden actors cost ~4-8 us/frame, one-shot moves cost nothing after\nentry. Realistic P3 (97 objects) aborts at load 4 of 4; anime P3 loads.\nCause unknown; W5b's realistic kit waits on it. P0 doubles as the\nre-run of original step 10 (22.95 / 21.19 FPS, both above 20).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
ed2b171e	author	Will Norris
ed2b171e	added	248
ed2b171e	deleted	0
ed2b171e	files	1
ed2b171e	body	R0 code reading: moving and hiding pieces from Forth works, colliders\nfollow position but not rotation (one box per module, parked inside the\nroom), Forth's random is already reseeded per level, property@ and the\nTV panel work for a Director-owned catalog, the kit fits the limits, DFRM\nlobes are not worth it. The phone/coordinator settings path is\nPlanted-only today, so D9 asks whether W5a ships TV-panel-only. The\nrotation-latch bug R0 surfaced is fixed (4ca61197, c5b6bc33).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
