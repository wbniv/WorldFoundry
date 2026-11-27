| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/351be3175) | Classify Seahorse Grid as shipped by its screensaver app |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/cb251fec8) | Unreachable levels review: reframe as tests, experiments and two real levels (Will) |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/22e3d6e66) | Unreachable levels: one-page review of the 22 with screenshots and suggested verdicts |

<!--history-meta v1
351be3175	author	Will Norris
351be3175	added	3
351be3175	deleted	3
351be3175	files	1
cb251fec8	author	Will Norris
cb251fec8	added	69
cb251fec8	deleted	294
cb251fec8	files	1
cb251fec8	body	Will: "most of the things aren't real levels, they're just tests". Each of the 22\nis now classed as a fixture, an experiment or a real level. The fixtures and\nexperiments are judged only on whether they are still useful tests and whether\nthey still rebuild; "keep + upgrade" is offered only for the two real levels,\nmoon_site01 and seahorse_grid. The six rebuild snags link to the separate fix.\nPer-level sections are folded into one table and a screenshot grid.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
22e3d6e66	author	Will Norris
22e3d6e66	added	297
22e3d6e66	deleted	0
22e3d6e66	files	1
22e3d6e66	body	docs/diagnostics/2026-11-27-unreachable-levels/: for each level, what it is, its\nfirst and last commits, what references it (marking the references that would\nbreak if it were deleted), a scratch build test, a frame captured headless in\nwf-linux-test, its size and a suggested verdict, then a Decide checklist for\nWill. Linked from the [T5] TODO item, which stays T5.\n\nThe review found that seahorse_grid ships (the Seahorse Grid screensaver), that\nthe web build preloads moon_site01, marble-madness and pilot_demo, and that seven\nDirector scripts no longer compile.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
-->
