| Date | Change |
|------|--------|
| [2026-11-14](https://github.com/wbniv/WorldFoundry/commit/41c48094) | Q*bert: the game no longer ends before the first key press |

<!--history-meta v1
41c48094	author	Will Norris
41c48094	added	227
41c48094	deleted	0
41c48094	files	1
41c48094	body	On cast1 every D-pad edge reached the player script with the right bit, yet\nQ*bert never hopped after the intro. The game was already over: on L1R1 Ugg\nand the green ball spawned the moment INTRO_DONE latched, Ugg climbed to the\napex in 106 frames and took all three lives in three frames, so every later\nkey press landed in the game-over restart guard. Same on the desktop engine.\nAll three defects date from d378b752, which made the enemy scripts compile.\n\n- Green ball, Ugg and Wrong-Way spawn only from L2 / L3: their spawn blocks\n  now test the same round gate the director uses to arm their timers (an\n  unarmed timer reads 0, which meant "spawn now").\n- A death costs one life and clears the board (enemies retired, Coily reset,\n  sequencer reloaded); before, a contact took a life every frame.\n- No spawns during game over, so a restart begins on an empty board.\n- The restart guard's `else drop` underran the stack while a key was held as\n  the game-over hold ran out: the `zforth error 3 calling _wfs0` lines on cast1.\n\nThe Blender pipeline cannot export a loadable Q*bert level at HEAD (index\ndrift; CamShot Target names a missing object), so the level outputs are the\ncommitted .lev plus exactly the generator's script delta, built with\nbuild_level_binary.sh and cdpack. tests/level_script_vm runs every actor\nscript of an exported level like the engine does; test_qbert_remote_hop\nfails 4/4 on the old level and passes on the new one.\n\nPlan: docs/plans/2026-11-14-qbert-remote-hop.md\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
