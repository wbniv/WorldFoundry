| Date | Change |
|------|--------|
| [2026-05-05](https://github.com/wbniv/WorldFoundry/commit/74008c54) | chore: accumulated session work — docs, qbert scripts, engine tweaks |
| [2026-04-18](https://github.com/wbniv/WorldFoundry/commit/ac9d9673) | docs(wf-status): close Android port; rename Deferred → Backlog; file plan follow-ups |

<!--history-meta v1
74008c54	author	Will Norris
74008c54	added	1
74008c54	deleted	1
74008c54	files	1
74008c54	body	docs: new plans and investigations (qbert palette, round-clear, fall/lives,\n  cube-palette, camera-path revival, qbert-autopilot, zforth-coroutines);\n  updated level-building.md, level-design-troubleshooting.md, scripting-languages.md;\n  reference screenshots for per-round palette; session transcripts\n\nscripts/research/mame/qbert_palette_capture.lua: fix nil palette_dev —\n  emu.register_start is deprecated and fires before devices are ready;\n  moved DIP set + device lookup to frame 1 inside register_frame_done\n\nwflevels/qbert_practice/blender_create_qbert.py: apex respawn signal (mb[426])\n  replacing broken INDEXOF_X/Y/Z director writes\n\nengine/stubs/zfconf.h: dict size bump\nwfsource/source/mailbox/mailbox.inc: global mailbox range cap 0..998\nwfsource/source/gfx/gl/display.cc, main.cc: display/startup tweaks\nwflevels/marble-madness/*.iff, wfsource/source/game/cd.iff: binary level artifacts\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
ac9d9673	author	Will Norris
ac9d9673	added	30
ac9d9673	deleted	0
ac9d9673	files	1
ac9d9673	body	- Android port plan moved Active → Complete, marked Closed 2026-04-18.\n- Deferred table renamed Backlog; audio-assets-from-iff and Steam release\n  moved from Active to Backlog.\n- New plan docs/plans/2026-04-18-android-launcher-polish.md for the\n  remaining adaptive-icon XML work called out in the closure audit.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
-->
