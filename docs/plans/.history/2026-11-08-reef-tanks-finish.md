| Date | Change |
|------|--------|
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/4bb0d148) | Reef research: boxfish Gulf record closed (D2); humbug flagged (D1) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/fef6db28) | Reef: keep W5b's anime per-piece cost (Will); speed work deferred to TODO |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/65d165bf) | Reef W5b: rock-module kit, site tables, worst-visible and room-slot budgets |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/8decb672) | Reef plan: realistic P3 abort is the 32 MB room slot; W5b budget in bytes |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/094f53a6) | Reef plan: R0 device run P0–P3 on cast1; realistic 97-object load abort |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/a205df47) | Reef: ReefSettings level settings object (plan W5a) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/ed2b171e) | Reef plan: W5 R0 spike results; D9 (where ReefSettings appears) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/aac370a8) | Reef plan: W5 decisions D5-D8 recorded |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/09da72be) | Reef plan: W5 procedural reef (random rocks, rock count, clustered colonies) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/8163dff4) | Reef plan: W3 placement approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/1a30b727) | Reef: nothing floats, everything attaches (plan W3) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/5030e6cd) | Reef plan: W2 approved, W3 started |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/7e42d059) | Reef: rebuild the nudibranch model; W2 skins approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/068281ff) | Reef: creature skins in their own atlas cells (plan W2) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/2099c8e7) | Reef plan: W1 worms approved |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b8831c71) | Reef: rebuild the Christmas tree worms (plan W1) |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/04a42178) | Plan: reef finish, record the completed cast1 frame-rate gate |
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/b756367f) | Plan: finish the reef tanks (worms, skins, placement, acceptance) |

<!--history-meta v1
4bb0d148	author	Will Norris
4bb0d148	added	3
4bb0d148	deleted	3
4bb0d148	files	1
4bb0d148	body	D2: Ostracion cubicus is recorded at Hin Khao, Ko Tao (Sutthacheep et al.\n2022) and in 11 research-grade GBIF occurrences on the Ko Tao and\nChumphon pinnacles.\n\nD1: no citable Gulf of Thailand record for Dascyllus aruanus. GBIF has\nnone in the Gulf, iNaturalist only captive ones, and the Gulf surveys\nread list D. reticulatus and D. trimaculatus instead. Search log and\noptions for Will are in the research ledger; nothing swapped. Poster\nexport (steps 2, 13) stays blocked on D1 and the visual-review gate.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
fef6db28	author	Will Norris
fef6db28	added	1
fef6db28	deleted	1
fef6db28	files	1
fef6db28	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
65d165bf	author	Will Norris
65d165bf	added	13
65d165bf	deleted	1
65d165bf	files	1
65d165bf	body	Six modules (three heroes = today's rocks with their dressing, three new\nfillers), pivot-centred box colliders, 16-point site tables, nine colony\nclumps, visibility cells 200-205/210-218. Fixed is the heroes at their\nFixed pivots and cooks to the same meshes (0.04 mm; renders differ on\n<0.04 % of pixels). report_budget.py --cooked now fails the build on the\nworst visible set, anime hulls and the 32 MB Room #0 slot. Arch gains a\nlintel-only collider. P4 on cast1: 22.03 / 20.26 FPS (gate 20).\nOpen: anime Fixed is 0.93 ms slower than before, cause unknown.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
8decb672	author	Will Norris
8decb672	added	6
8decb672	deleted	4
8decb672	files	1
8decb672	body	A record job kept logcat: FatalError Lmalloc out of memory in Named\nRoom #0. Each mesh actor copies its mesh into the level's 32,000,000-byte\nslot; realistic P3 needs ~33.1 MB. Same level at 36 or 48 MB loads on\ncast1. Not an engine bug. Decision: W5b stays inside 32 MB with a\nbuild-time slot check; 36 MB is the tested fallback.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
094f53a6	author	Will Norris
094f53a6	added	26
094f53a6	deleted	8
094f53a6	files	1
094f53a6	body	Probes on copies of today's reef levels, three alternating runs each:\nhidden actors cost ~4-8 us/frame, one-shot moves cost nothing after\nentry. Realistic P3 (97 objects) aborts at load 4 of 4; anime P3 loads.\nCause unknown; W5b's realistic kit waits on it. P0 doubles as the\nre-run of original step 10 (22.95 / 21.19 FPS, both above 20).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
a205df47	author	Will Norris
a205df47	added	2
a205df47	deleted	2
a205df47	files	1
a205df47	body	A Director-owned level settings object, like the Jellyfish and Planted\ntanks': Layout (Fixed|Random, default Fixed until W5c), Rocks (1-5,\ndefault 3), Colonies (Sparse|Normal|Dense) and Seed (24-bit; 0 = a new\nreef on every entry). Both styles carry the catalog: generate.py copies\nsettings.oas/bindings next to each level and writes 'indices' into the\nactor map; both build.sh files run oas2oad and build-object-properties\n(the Jellyfish recipe); the screensaver catalog check knows ReefSettings.\nThe Director polls the four fields once a second (property@, and\nproperty-int-bytes@ for Seed) into mailboxes 860-863 for W5c. D9: a\nlevel settings object with no app code (Will). New test_thai_reef_settings\nplus a VM test that panel values reach the Director.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
ed2b171e	author	Will Norris
ed2b171e	added	25
ed2b171e	deleted	2
ed2b171e	files	1
ed2b171e	body	R0 code reading: moving and hiding pieces from Forth works, colliders\nfollow position but not rotation (one box per module, parked inside the\nroom), Forth's random is already reseeded per level, property@ and the\nTV panel work for a Director-owned catalog, the kit fits the limits, DFRM\nlobes are not worth it. The phone/coordinator settings path is\nPlanted-only today, so D9 asks whether W5a ships TV-panel-only. The\nrotation-latch bug R0 surfaced is fixed (4ca61197, c5b6bc33).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
aac370a8	author	Will Norris
aac370a8	added	2
aac370a8	deleted	2
aac370a8	files	1
aac370a8	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
09da72be	author	Will Norris
09da72be	added	169
09da72be	deleted	0
09da72be	files	1
09da72be	body	Will asked for clustered, random-ish placement like the Planted Tank,\nrandomly generated rocks with a viewer-set count, placement in Forth\nrather than engine code, and a settings object (the reef has none). The\nplan proposes a baked rock-module kit laid out by the Forth Director at\nlevel entry from a new ReefSettings object read with property@, with the\nPlanted Tank's founder-and-lineage colonies over pre-resolved site tables,\nan R0 feasibility spike and decisions D5-D8. Mock-ups render a colony\nprototype for three seeds and toy rock layouts for four seed/count pairs;\nW1-W3 sections gain their as-built screenshots.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
8163dff4	author	Will Norris
8163dff4	added	1
8163dff4	deleted	1
8163dff4	files	1
8163dff4	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
1a30b727	author	Will Norris
1a30b727	added	1
1a30b727	deleted	1
1a30b727	files	1
1a30b727	body	An audit against the rock and sand (the analytic rock matches the export\nto ~0.01 units) found zoanthid carpets, cup corals and crusts 0.35-0.6+\nunits in front of the rock, most attached actors and the cauliflower and\ntable corals off their rock, the clam and mushroom coral above the sand,\nthe nudibranch 0.33 above it and bobbing, the shrimp station in mid-air,\nand the hermit crab 0.31 under the sand.\n\n- reef/surface.py: host surfaces, ray casts and smooth normals.\n- reef/placement.py: one table of attached things, resolved at export;\n  anchor_map() reports the resolved positions and generate.py reads them.\n- Polyps, cups and arch cups placed on the surface along its normal;\n  crusts conformed; the coral head's crab and humbugs move with it.\n- Nudibranch crawls flat on the sand at the left rock's foot and turns\n  to face its direction of travel; shrimp wait on the cave floor.\n- W3 tests in test_thai_reef_placement.py; movement tests read the\n  resolved station and host (the old nudibranch test required the bob).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
5030e6cd	author	Will Norris
5030e6cd	added	1
5030e6cd	deleted	1
5030e6cd	files	1
5030e6cd	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
7e42d059	author	Will Norris
7e42d059	added	1
7e42d059	deleted	1
7e42d059	files	1
7e42d059	body	Will approved every W2 skin except the nudibranch, which had barely\nchanged: its old tiles already approximated the colours and the model was\nthe problem (a tall blob with a fence of stalked tubercles). Phyllidia\nvaricosa now has a low flat mantle, three blue-grey ridges with\nyellow-capped tubercles on them, yellow rhinophores, and a top-down mantle\ntexture repeating the ridges with transverse margin ridges.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
068281ff	author	Will Norris
068281ff	added	3
068281ff	deleted	2
068281ff	files	1
068281ff	body	Will reported actors with no textures. Small creatures borrowed sponge,\nsand and rock tiles at ~87 texels per unit, or one flat texel, so they\nrendered as flat colour (crab and shrimp 86 % of area under 3 texels,\nnudibranch 62 % flat black).\n\n- reef/uvmap.py: one pure-Python UV function for every face; generate.py,\n  the texel audit and the review renders all use it.\n- atlas.py cells 9-14: duster radioles and tube, crab, shrimp, nudibranch,\n  hermit shell and legs, crusts; cell 15 humbug sheen and fan/star\n  gradients. Anime saturates and posterises them.\n- Builders use semantic skin keys; zoanthid heads and discs map one\n  flower-head motif each (partition keeps explicit UVs).\n- Colours from sourced references (docs/reference/thai-reef-skin-colours.md).\n- New tests/test_thai_reef_skins.py; texcov --check passes.\n- Both levels and the menu bundle rebuilt (other tanks from HEAD).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
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
