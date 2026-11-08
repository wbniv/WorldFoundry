| Date | Change |
|------|--------|
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/2099c8e7) | Reef plan: W1 worms approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b8831c71) | Reef: rebuild the Christmas tree worms (plan W1) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/04a42178) | Plan: reef finish, record the completed cast1 frame-rate gate |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b756367f) | Plan: finish the reef tanks (worms, skins, placement, acceptance) |

<!--history-meta v1
2099c8e7	author	Will Norris
2099c8e7	added	1
2099c8e7	deleted	1
2099c8e7	files	1
2099c8e7	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b8831c71	author	Will Norris
b8831c71	added	9
b8831c71	deleted	9
b8831c71	files	1
b8831c71	body	The worms were flat "pine tree" cut-outs on white pegs, on a rigid 5 x 3\ngrid floating 9-14 cm in front of the Porites boulder, all pointing up,\ncoloured with borrowed tiles, and retracting toward a point 15 cm below.\n\n- scene.py: worm_mouths() places 15 tube mouths on the boulder surface\n  (shared Porites lobes and relief), camera- and up-facing, >= 0.14 apart,\n  crown axis = normal + 0.7 up; neighbours never share a colour morph.\n- life.py: twin spiral crowns (core + two-sided helical radiole ribbon,\n  4.5 turns, explicit UVs) and static collars + opercula in reef_hard.\n- atlas.py: repack to 16 cells of 256 x 256 (D2); cell 8 holds the eight\n  worm morphs (D1), cell 15 the flat swatches; UV writers updated.\n- worm_rig.py: curves rooted at the tube mouths along the crown axes, so\n  the retract scale collapses each crown into its mouth.\n- Anchor, director and actor origin all come from worm_mouths().\n- Both levels and the menu bundle rebuilt (other tanks taken from HEAD).\n- New tests/test_thai_reef_placement.py; the worm reaction test now reads\n  the mouths instead of the old grid.\n\nCrowns 4,920 triangles (budget 5,000). Review renders in\ndocs/diagnostics/reef-worms-2026-11-08/.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
04a42178	author	Will Norris
04a42178	added	2
04a42178	deleted	2
04a42178	files	1
04a42178	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b756367f	author	Will Norris
b756367f	added	306
b756367f	deleted	0
b756367f	files	1
b756367f	body	Compares the 2026-11-02 reef plan's 15 verification steps with today's\nstate and adds W1 (rebuilt Christmas tree worms set into the Porites\nboulder), W2 (creature skins via a 16-cell atlas repack), W3 (placement\nand an anchor single source of truth, with a regression test) and W4 (the\noriginal plan's open steps). Mockups, a texel-coverage audit and the\nmockup generator are in the bundle.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
