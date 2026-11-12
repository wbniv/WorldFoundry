| Date | Change |
|------|--------|
| [2026-11-10](https://github.com/wbniv/WorldFoundry/commit/950fc4a1) | Seahorse six-pair regression: bisect record (a86f420b ~0.6 ms; rest sub-noise) |

<!--history-meta v1
950fc4a1	author	Will Norris
950fc4a1	added	130
950fc4a1	deleted	0
950fc4a1	files	1
950fc4a1	body	Reproduced on cast1: 9f97f5dd 69.30 ms vs HEAD-era 71.27 ms (planted-tank\nsix-pair fixture, E7.1 window, alternating). Bisect: a86f420b (no-palette\nprogram selection + per-triangle palette tracking) is the one commit with\na demonstrated cost, +0.61 ms in a single alternating job (tracking ~0.2,\nprogram switching ~0.4); -0.63 ms when both are disabled at HEAD. Two more\nbisects named 59d554e4 and 9a982a5d; controls refute both (prewarm runs\nzero times; byte-identical libraries differ by 0.38 ms, the noise floor).\nFix options recorded, none implemented (a deliberate optimisation).\nscripts/swap-apk-assets.py swaps assets between APKs and re-signs.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
