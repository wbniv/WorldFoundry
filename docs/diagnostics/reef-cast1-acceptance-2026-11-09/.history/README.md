| Date | Change |
|------|--------|
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/13b3d659) | Reef W4: cast1 acceptance record; Dream host VRAM width fix |

<!--history-meta v1
13b3d659	author	Will Norris
13b3d659	added	123
13b3d659	deleted	0
13b3d659	files	1
13b3d659	body	Steps 9 and 10 PASS on today's release APK 83efd2c6 (realistic 22.50,\nanime 20.69 FPS with Layout = Random). E7.1 FAIL: six pairs at 71.25 ms\nagainst 69.09-69.28 ms on 17 Oct. E7.2 reported: 1.615 vs 0.625 ms CPU\nper frame, 16 vs 2 draws. Step 12 partial: the realistic reef Dream ran\n5 min; cast1 left the network during the anime hold, so the restore is\nstill to do. Step 15 captures are ready for Will.\n\nThe Aquarium Dream asserted on both reefs (w = 1024, VRAMWidth = 1024):\ndream_host.cc passed no --vram-width. It now passes 2048, the same as the\naquarium app's wf_args.txt; tests/test_dream_host_vram.py keeps them in\nstep.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
