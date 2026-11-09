| Date | Change |
|------|--------|
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/b9eba308) | Reef step 14: Metal sweep and GL/Metal scene recorded; caustics fixtures |

<!--history-meta v1
b9eba308	author	Will Norris
b9eba308	added	64
b9eba308	deleted	0
b9eba308	files	1
b9eba308	body	macos-style-metal build 6af14d47 (12 Mac min): sweep fd9349c8 vs b03f5cb5\nover 35 levels is 32 identical, 2 off by 1/255 on 1-2 pixels, and one\nlevel asserts on both engines. The shared scene is within 1/255 on 99.97% of\npixels; about 95 silhouette pixels per frame exceed it. Both strict gates\nmiss by a few pixels, so the plan needs a gate decision (row 14).\n\nscripts/build-reef-caustic-variants.py makes the S2 off/on fixture levels\nfor the cast1 gate (off is byte-identical to the realistic reef, on\ndiffers in one byte).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
