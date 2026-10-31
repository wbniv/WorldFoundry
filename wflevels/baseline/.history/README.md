| Date | Change |
|------|--------|
| [2026-10-31](https://github.com/wbniv/WorldFoundry/commit/e6fe62eb) | Baseline: add a ladder of eight Utah teapots (52 to 16 256 faces) |
| [2026-10-30](https://github.com/wbniv/WorldFoundry/commit/bf6bf9a3) | Add authored level memory configuration |
| [2026-10-06](https://github.com/wbniv/WorldFoundry/commit/dec3bf39) | Add verified baseline to the main CD at level 7 |
| [2026-10-06](https://github.com/wbniv/WorldFoundry/commit/8064c760) | Connect baseline and planted tank to a shared runtime settings host |
| [2026-10-06](https://github.com/wbniv/WorldFoundry/commit/ef6806c2) | Implement reusable World Foundry baseline level and verification toolkit |

<!--history-meta v1
e6fe62eb	author	Will Norris
e6fe62eb	added	11
e6fe62eb	deleted	0
e6fe62eb	files	1
e6fe62eb	body	The baseline had no curved, many-face mesh to measure renderer, memory and\nload-time cost against. It now has eight Utah teapots in a row at y = 10, one\nper tessellation level (n = 1, 2, 3, 4, 6, 8, 12, 16): 52, 240, 552, 992,\n2256, 4032, 9120 and 16256 faces, 33500 in all, each with a standing label\nboard. They are visual-only platform actors in a new TEAPOTS collection,\ncreated last so actor ids 1-21 do not move (the new actors are 22-30).\n\nReference data: Newell's 32-patch Bezier teapot, vendored verbatim as\nwflevels/baseline/data/teapotCGA.bpt (source, hash and provenance in\ndata/README.md). Cross-checked against the three.js TeapotGeometry table:\nall 32 patches identical, same order. wflevels/baseline/teapot.py tessellates\nit with no Blender dependency. Every level has 64n^2 - 8n faces except n = 1,\nwhich has 52: four more triangles are collinear and are dropped.\n\nWinding needs no correction. A prototype suggested mixed patch orientation;\nan orientation pass written for it flipped zero triangles at every level, so\nit was removed. The tests check consistency and outward winding per shell,\nwith a mutation test showing the checks fail on broken winding.\n\ngenerate.py gains add_teapots() (also run by build()) and --add-teapots\n<blend>, which appends the collection to the reviewed baseline.blend without\nregenerating it and refuses to run twice.\n\nMemory: the full ladder did not fit the authored 4000000-byte room budget\n(Lmalloc out of memory loading Room 0). It needs about 6.7 MB per slot, so\nmemory-settings.json now authors room_asset_bytes = 8000000. The settings\ncatalogs and bindings carry that value; nothing else in them changed.\n\nVerified: tests/test_baseline_teapots.py (30), task baseline:verify and\ntask baseline:check (118 descriptor checks plus every structural and native\ncheck, 60 FPS on the desktop). Not done: the Pixel install is queued behind a\ncoordinator maintenance window and cast2 is unreachable (needs its Wireless\ndebugging address), so the frame rate on the devices is unmeasured. The main\ncd.iff is not rebuilt: it already drifted (qbert entry, and verify.py --bundle\nexpects 9 TOC entries, now 10); recorded in the plan.\n\nAlso adds the plan for cleaning the baseline settings down to two owners\n(Field types, the 27 sensible type x showAs cases; and Runtime settings), with\nreal cast1 captures of Pick in 3D. Plan only; nothing in it is built.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqSWpcGmU9ZTVy7HDyx
bf6bf9a3	author	Will Norris
bf6bf9a3	added	10
bf6bf9a3	deleted	1
bf6bf9a3	files	1
dec3bf39	author	Will Norris
dec3bf39	added	13
dec3bf39	deleted	4
dec3bf39	files	1
8064c760	author	Will Norris
8064c760	added	10
8064c760	deleted	8
8064c760	files	1
ef6806c2	author	Will Norris
ef6806c2	added	93
ef6806c2	deleted	0
ef6806c2	files	1
-->
