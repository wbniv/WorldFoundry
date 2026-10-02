| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/a5301461) | Docs: the SMB world select on the Chromecast HD (Phase D: menu, D-pad, OK, level start PASS; Back held for the user) |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/5f44746b) | Docs: the SMB world select on the desktop (plan verification 1-7 PASS, 8-9 pending; porting status) |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/b754c2de) | Plan: the level menu, SMB world select first (accepted for SMB), mockups reworked |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/924e73a9) | Plan: a level menu for the multi-level cd.iff (engine overlay, MENU chunk from a manifest, opt-in task) |

<!--history-meta v1
a5301461	author	Will Norris
a5301461	added	31
a5301461	deleted	5
a5301461	files	1
a5301461	body	The smb release APK, built from a clean worktree of committed HEAD, shows the menu at launch\nat 59.9 fps, moves on DPAD_DOWN and starts World 1-2 on OK (LEVEL_TO_RUN=1, from logcat);\nthree screenshots in the plan. Holding Back to return, and a short Back leaving the app, wait\nfor the user's hands on the remote. Porting status updated; notes on the shared tree's stale\nsmb APK (the menu APK was built in the worktree).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
5f44746b	author	Will Norris
5f44746b	added	140
5f44746b	deleted	8
5f44746b	files	1
5f44746b	body	Plan: phases A-C done, the Forth -1 -> -2 finding, raw output under each verification step,\nthe engine's captured menu frame and the 720p TV-hint render, and notes on two unrelated\nfailures seen in neighbouring suites (a soundfont leak in test_game_shutdown, a stale\naquarium APK). Porting status: one line under Linux. android/README.md is left for Phase D.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
b754c2de	author	Will Norris
b754c2de	added	116
b754c2de	deleted	91
b754c2de	files	1
b754c2de	body	The smb app's W1-1..W1-4 world select is the primary case (desktop first, Android in\nPhase D after the split lands); the seven-level desktop bundle is the second, shown in\nthe mockups. Adds a prompt line to the MENU chunk, the input table (remote, gamepad,\nphone, keyboard), the files and cost, and SMB verification steps incl. the chain.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
924e73a9	author	Will Norris
924e73a9	added	220
924e73a9	deleted	0
924e73a9	files	1
924e73a9	body	Options (Forth shell menu, engine/HAL overlay, menu level), the decision (overlay, like the\nphone panel), the MENU chunk format, return-to-menu via a HAL request, defaults to confirm,\nand six mockups (default, moved, scrolling, long name, TV hint, one level or none).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
-->
