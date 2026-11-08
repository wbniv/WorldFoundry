| Date | Change |
|------|--------|
| [2026-11-08](https://github.com/wbniv/WorldFoundry/commit/1a30b727) | Reef: nothing floats, everything attaches (plan W3) |

<!--history-meta v1
1a30b727	author	Will Norris
1a30b727	added	76
1a30b727	deleted	0
1a30b727	files	1
1a30b727	body	An audit against the rock and sand (the analytic rock matches the export\nto ~0.01 units) found zoanthid carpets, cup corals and crusts 0.35-0.6+\nunits in front of the rock, most attached actors and the cauliflower and\ntable corals off their rock, the clam and mushroom coral above the sand,\nthe nudibranch 0.33 above it and bobbing, the shrimp station in mid-air,\nand the hermit crab 0.31 under the sand.\n\n- reef/surface.py: host surfaces, ray casts and smooth normals.\n- reef/placement.py: one table of attached things, resolved at export;\n  anchor_map() reports the resolved positions and generate.py reads them.\n- Polyps, cups and arch cups placed on the surface along its normal;\n  crusts conformed; the coral head's crab and humbugs move with it.\n- Nudibranch crawls flat on the sand at the left rock's foot and turns\n  to face its direction of travel; shrimp wait on the cave floor.\n- W3 tests in test_thai_reef_placement.py; movement tests read the\n  resolved station and host (the old nudibranch test required the bob).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
