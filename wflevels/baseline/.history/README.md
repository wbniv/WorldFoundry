| Date | Change |
|------|--------|
| [2026-10-31](https://github.com/wbniv/WorldFoundry/commit/2905d27f) | Main cd.iff: one manifest lists its levels; rebuild the stale bundle |
| [2026-10-31](https://github.com/wbniv/WorldFoundry/commit/e6fe62eb) | Baseline: add a ladder of eight Utah teapots (52 to 16 256 faces) |
| [2026-10-30](https://github.com/wbniv/WorldFoundry/commit/bf6bf9a3) | Add authored level memory configuration |
| [2026-10-06](https://github.com/wbniv/WorldFoundry/commit/dec3bf39) | Add verified baseline to the main CD at level 7 |
| [2026-10-06](https://github.com/wbniv/WorldFoundry/commit/8064c760) | Connect baseline and planted tank to a shared runtime settings host |
| [2026-10-06](https://github.com/wbniv/WorldFoundry/commit/ef6806c2) | Implement reusable World Foundry baseline level and verification toolkit |

<!--history-meta v1
2905d27f	author	Will Norris
2905d27f	added	2
2905d27f	deleted	1
2905d27f	files	1
2905d27f	body	Adding a level to wfsource/source/game/cd.iff meant editing a hand-written\nlist in the Taskfile, a second copy in tests/level_menu_harness.py, and\nhard-coded names and indices in wflevels/baseline/verify.py. The copies had\ndrifted: the committed bundle held an old baseline and a stale qbert entry\n(its level was committed 2026-10-27, cd.iff on 2026-10-17), the checker\nexpected 9 TOC entries against the bundle's 10 (the UIFT font), and\ntest_identical_without_manifest[cd.iff] was failing.\n\nwflevels/main-cd.manifest is now the one list, in TOC order (position = level\nindex), with the rules for changing it: append only, because shell.fth boots\nlevel 0, the SMB flag and axe chain levels by index, and scripts and device\nchecks name an index (the baseline is 7). It reuses the level-menu manifest\ngrammar without title or prompt (this bundle has no menu).\n\n- scripts/cd_manifest.py reads and validates it (standalone files only, no\n  duplicates, printable names, files must exist).\n- scripts/build-main-cd.py packs it; `task build-cd-iff` calls it instead of\n  a hand-written cdpack command. The rebuilt bundle is byte-identical to what\n  the old command produced (SHA-256 797a5bf12b43...): the refactor changes no\n  bytes.\n- verify.py and level_menu_harness.py read the manifest; the baseline's level\n  index comes from it, not a literal 7, and verify.py now checks the UIFT\n  entry (a chunk header plus the font file).\n- tests/test_main_cd_manifest.py: the manifest is valid and ordered, the\n  loader rejects each kind of bad manifest, the committed bundle matches it,\n  the build script reproduces the committed bytes, and no hand-written copy\n  of the list reappears.\n- docs/level-building.md: "Adding a level to the main cd.iff".\n\nThe bundle is rebuilt: the baseline entry grows by 788480 bytes (the teapots)\nand the qbert entry is refreshed to its committed level.\n\nVerified: test_main_cd_manifest.py and test_level_menu.py, 44 passed; the\ndesktop session loads the baseline from the bundle as level 7, 162 of 162\nchecks. test_engine_smb_menu_chain_and_return still fails at its screenshot\nstep (the menu chain itself passes); it runs smb-menu-cd.iff and the engine,\nnot this bundle, and fails the same way twice, so it is left for its owner.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqSWpcGmU9ZTVy7HDyx
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
