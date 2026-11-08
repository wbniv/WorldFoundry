| Date | Change |
|------|--------|
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/5030e6cd) | Reef plan: W2 approved, W3 started |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/144f06af) | Reef: nudibranch mantle skin and matching height-field shape |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/7e42d059) | Reef: rebuild the nudibranch model; W2 skins approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b46fc80d) | Reef skins review: labelled before/after table |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/068281ff) | Reef: creature skins in their own atlas cells (plan W2) |

<!--history-meta v1
5030e6cd	author	Will Norris
5030e6cd	added	2
5030e6cd	deleted	2
5030e6cd	files	1
5030e6cd	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
144f06af	author	Will Norris
144f06af	added	18
144f06af	deleted	4
144f06af	files	1
144f06af	body	Will: "Nudibranch still not approved. don't you have any textures for\nit?" The skin was three flat stripes, mostly seen edge-on. Atlas cell 12\nnow paints a mottled black mantle with wavy, shaded blue-grey ridges,\ndome-shaded yellow tubercles, grey inter-ridge tubercles and transverse\nmargin ridges. The mantle is a low height field whose ridges rise where\nthe skin paints them, with a 3D tubercle on every painted one (one shared\nlayout in atlas.py). Review renders are matte, like the engine.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
7e42d059	author	Will Norris
7e42d059	added	11
7e42d059	deleted	2
7e42d059	files	1
7e42d059	body	Will approved every W2 skin except the nudibranch, which had barely\nchanged: its old tiles already approximated the colours and the model was\nthe problem (a tall blob with a fence of stalked tubercles). Phyllidia\nvaricosa now has a low flat mantle, three blue-grey ridges with\nyellow-capped tubercles on them, yellow rhinophores, and a top-down mantle\ntexture repeating the ridges with transverse margin ridges.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b46fc80d	author	Will Norris
b46fc80d	added	11
b46fc80d	deleted	9
b46fc80d	files	1
b46fc80d	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
068281ff	author	Will Norris
068281ff	added	57
068281ff	deleted	0
068281ff	files	1
068281ff	body	Will reported actors with no textures. Small creatures borrowed sponge,\nsand and rock tiles at ~87 texels per unit, or one flat texel, so they\nrendered as flat colour (crab and shrimp 86 % of area under 3 texels,\nnudibranch 62 % flat black).\n\n- reef/uvmap.py: one pure-Python UV function for every face; generate.py,\n  the texel audit and the review renders all use it.\n- atlas.py cells 9-14: duster radioles and tube, crab, shrimp, nudibranch,\n  hermit shell and legs, crusts; cell 15 humbug sheen and fan/star\n  gradients. Anime saturates and posterises them.\n- Builders use semantic skin keys; zoanthid heads and discs map one\n  flower-head motif each (partition keeps explicit UVs).\n- Colours from sourced references (docs/reference/thai-reef-skin-colours.md).\n- New tests/test_thai_reef_skins.py; texcov --check passes.\n- Both levels and the menu bundle rebuilt (other tanks from HEAD).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
