| Date | Change |
|------|--------|
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/068281ff) | Reef: creature skins in their own atlas cells (plan W2) |

<!--history-meta v1
068281ff	author	Will Norris
068281ff	added	57
068281ff	deleted	0
068281ff	files	1
068281ff	body	Will reported actors with no textures. Small creatures borrowed sponge,\nsand and rock tiles at ~87 texels per unit, or one flat texel, so they\nrendered as flat colour (crab and shrimp 86 % of area under 3 texels,\nnudibranch 62 % flat black).\n\n- reef/uvmap.py: one pure-Python UV function for every face; generate.py,\n  the texel audit and the review renders all use it.\n- atlas.py cells 9-14: duster radioles and tube, crab, shrimp, nudibranch,\n  hermit shell and legs, crusts; cell 15 humbug sheen and fan/star\n  gradients. Anime saturates and posterises them.\n- Builders use semantic skin keys; zoanthid heads and discs map one\n  flower-head motif each (partition keeps explicit UVs).\n- Colours from sourced references (docs/reference/thai-reef-skin-colours.md).\n- New tests/test_thai_reef_skins.py; texcov --check passes.\n- Both levels and the menu bundle rebuilt (other tanks from HEAD).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
