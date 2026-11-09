| Date | Change |
|------|--------|
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/d49cc850) | Reef step 14 PASS: GL sweep identical; untextured GL/Metal scene strict pass |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/51bab0f5) | Metal: compile the style shader as a separate program (reef step 14 strict sweep) |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/93e7ba07) | Reef: step 12 PASS (anime Dream rerun, restore verified); step 14 S2 and Metal evidence |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/b9eba308) | Reef step 14: Metal sweep and GL/Metal scene recorded; caustics fixtures |

<!--history-meta v1
d49cc850	author	Will Norris
d49cc850	added	54
d49cc850	deleted	6
d49cc850	files	1
d49cc850	body	GL (Will: "Run it"): DESIGNER_CHEATS Debug engines at fd9349c8, b03f5cb5\nand HEAD render all 34 sweep levels pixel-identically with every style\nfield at 0 (baseline level asserts on the pre-style engines).\nscripts/style-gl-sweep.sh reproduces it.\n\nUntextured scene (Will: "Fix the scene"): with the boxes lifted 0.12 off\nthe floor the depth tie is gone; Metal run 6af1bd90 (scenes-only, 6 min)\nagainst GL gives S3 byte-identical and S1 within 1/255 on every pixel; the\nstrict test passes for both flat scenes. Row 14 struck as PASS; caustics\nstay off pending step 15.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
51bab0f5	author	Will Norris
51bab0f5	added	58
51bab0f5	deleted	0
51bab0f5	files	1
51bab0f5	body	With every style field at 0, the Metal style engine moved 3 pixels by\n1/255 against the pre-style engine (aquarium_arowana, snowgoons-blender),\ndeterministically. A probe without the style work in wf_vs was pixel-\nidentical (Codemagic 6af1ade1): under fast-math the unused eye/normal/\nabsorb/caustic arithmetic changed code generation for the position and\nfog math. kMSL now keeps every style addition under #ifdef WF_STYLE (as\nGL does), the host compiles a second library with WF_STYLE and binds its\npipelines only while style shading is active. Proof run 6af1b29c: the fix\non b03f5cb5 renders all 34 sweep levels identical to fd9349c8, and the\nstyle program's output is byte-identical to before.\ntests/test_metal_style_variants.py keeps the style-off text equal to the\npre-style shader token for token.\n\nAlso records the untextured-scene result (one raster tie-break pixel)\nand folds the caustics decision into step 15 (Will, 2026-11-09).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
93e7ba07	author	Will Norris
93e7ba07	added	44
93e7ba07	deleted	7
93e7ba07	files	1
93e7ba07	body	Step 12: the anime reef Dream ran 5 min 29 s once cast1 was back; Seahorse\nGrid, tank random and game APK 30554973 are restored and verified.\n\nStep 14: S2 caustics cost 0.55 ms per frame on cast1 (22.90 -> 22.62 FPS),\ninside the 2 ms gate; left off pending Will's look review. Will kept the\nstrict Metal gates ("Keep strict, investigate"). Run 6af1a232: repeats are\nbyte-identical, so the sweep's 3 pixels at 1/255 are a deterministic Metal\nrounding change (suspect: the new wf_vs outputs under fast-math); on the\ngeometry-only scenes every pixel over 1/255 is bilinear texture sampling\n(the same pixels in the S1 and S3 scenes), not the style math.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
b9eba308	author	Will Norris
b9eba308	added	64
b9eba308	deleted	0
b9eba308	files	1
b9eba308	body	macos-style-metal build 6af14d47 (12 Mac min): sweep fd9349c8 vs b03f5cb5\nover 35 levels is 32 identical, 2 off by 1/255 on 1-2 pixels, and one\nlevel asserts on both engines. The shared scene is within 1/255 on 99.97% of\npixels; about 95 silhouette pixels per frame exceed it. Both strict gates\nmiss by a few pixels, so the plan needs a gate decision (row 14).\n\nscripts/build-reef-caustic-variants.py makes the S2 off/on fixture levels\nfor the cast1 gate (off is byte-identical to the realistic reef, on\ndiffers in one byte).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
