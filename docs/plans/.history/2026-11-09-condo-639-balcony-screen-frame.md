| Date | Change |
|------|--------|
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/418a87be) | Balcony screen frame: Lazada stock panels; solar set no longer six-alike |
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/e7ba0bb8) | Balcony screen frame: solar inserts also go in to harvest power at home |
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/e84c3807) | Balcony screen frame: controller and 50 Ah battery prices; payback range |
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/d1a67569) | Balcony screen frame: battery prices from AliExpress Thailand; revised payback |
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/65ab436c) | Balcony screen frame: payback estimate for the solar option |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/4572a098) | Balcony screen frame: solar value at both the base and the top MEA rate |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/be93d8f3) | Balcony screen frame: value of the solar yield at MEA's 2026 tariff |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/b5561098) | Balcony screen frame: solar charges an off-grid battery; no grid-tie |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/adc50caa) | Balcony screen frame: solar options buyable in Thailand |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/7a50bd79) | Balcony: break the screen frame out as its own plan; archive A and B |

<!--history-meta v1
418a87be	author	Will Norris
418a87be	added	14
418a87be	deleted	12
418a87be	files	1
418a87be	body	Will (2026-11-11): six panels were for aesthetics, so the solar set need\nnot match them. Recommends eight 18 V 50 W panels (600 x 460, Lazada\nflash price 234.52 THB) sideways, two high, in four quarter-width\ninserts: 400 W, about 280-320 W after the ledge's shade. Adds the 18 V\n30 W (390 x 430) and 80 W (960 x 460) sizes, revises the yield value and\npayback (panels 2-3 years; whole kit 4.5-19 years), and redraws the\nstock mockup state.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
e7ba0bb8	author	Will Norris
e7ba0bb8	added	13
e7ba0bb8	deleted	10
e7ba0bb8	files	1
e7ba0bb8	body	Will (2026-11-11): the solar set goes in whenever he would rather harvest\npower than have the view, not only while away. Updates the power use,\npayback reading, power diagram and panel-set state diagram.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
e84c3807	author	Will Norris
e84c3807	added	2
e84c3807	deleted	2
e84c3807	files	1
e84c3807	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
d1a67569	author	Will Norris
d1a67569	added	3
d1a67569	deleted	3
d1a67569	files	1
d1a67569	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
65ab436c	author	Will Norris
65ab436c	added	9
65ab436c	deleted	0
65ab436c	files	1
65ab436c	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
4572a098	author	Will Norris
4572a098	added	1
4572a098	deleted	1
4572a098	files	1
4572a098	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
be93d8f3	author	Will Norris
be93d8f3	added	1
be93d8f3	deleted	1
be93d8f3	files	1
be93d8f3	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
b5561098	author	Will Norris
b5561098	added	4
b5561098	deleted	6
b5561098	files	1
b5561098	body	Will's decision answers open question 3; the grid-tie branch leaves the\npower diagram and moves to out of scope.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
adc50caa	author	Will Norris
adc50caa	added	37
adc50caa	deleted	7
adc50caa	files	1
adc50caa	body	Replace the US custom-maker suggestion with Thai sources (Sunnergy and\nNSTHAI to quote a custom size; NSTHAI stock sizes) and a table of seven\nways to fit: custom laminate, stock 50/60 W panels low in each insert,\nstock 100/150 W in double-width inserts, marine flexible on the inserts,\nand stock panels behind clear inserts, each with an after-shade estimate\nfrom PVGIS's beam share and the ledge's shadow depth. Evaluates the\noverhang idea, recommends custom-or-stock-50 W, adds open question 7\n(latches at any width) and a stock-panel mockup state.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
7a50bd79	author	Will Norris
7a50bd79	added	178
7a50bd79	deleted	0
7a50bd79	files	1
7a50bd79	body	The fixed screen frame (formerly plan C) is the plan going forward, so it\nmoves to docs/plans/2026-11-09-condo-639-balcony-screen-frame.md with its\nmockups and SVG generators: context and measurements, the v1 screens, v2\nweather inserts, solar inserts, open questions renumbered 1-6, and\nhandover verification checks. The balcony shade plan marks plans A (zip\nscreen) and B (bi-fold) archived and points to the new plan; its level\nmodel section is unchanged. The plan-B RFQ TODO item is parked.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
-->
