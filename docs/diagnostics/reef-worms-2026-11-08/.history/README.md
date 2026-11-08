| Date | Change |
|------|--------|
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b8831c71) | Reef: rebuild the Christmas tree worms (plan W1) |

<!--history-meta v1
b8831c71	author	Will Norris
b8831c71	added	58
b8831c71	deleted	0
b8831c71	files	1
b8831c71	body	The worms were flat "pine tree" cut-outs on white pegs, on a rigid 5 x 3\ngrid floating 9-14 cm in front of the Porites boulder, all pointing up,\ncoloured with borrowed tiles, and retracting toward a point 15 cm below.\n\n- scene.py: worm_mouths() places 15 tube mouths on the boulder surface\n  (shared Porites lobes and relief), camera- and up-facing, >= 0.14 apart,\n  crown axis = normal + 0.7 up; neighbours never share a colour morph.\n- life.py: twin spiral crowns (core + two-sided helical radiole ribbon,\n  4.5 turns, explicit UVs) and static collars + opercula in reef_hard.\n- atlas.py: repack to 16 cells of 256 x 256 (D2); cell 8 holds the eight\n  worm morphs (D1), cell 15 the flat swatches; UV writers updated.\n- worm_rig.py: curves rooted at the tube mouths along the crown axes, so\n  the retract scale collapses each crown into its mouth.\n- Anchor, director and actor origin all come from worm_mouths().\n- Both levels and the menu bundle rebuilt (other tanks taken from HEAD).\n- New tests/test_thai_reef_placement.py; the worm reaction test now reads\n  the mouths instead of the old grid.\n\nCrowns 4,920 triangles (budget 5,000). Review renders in\ndocs/diagnostics/reef-worms-2026-11-08/.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
