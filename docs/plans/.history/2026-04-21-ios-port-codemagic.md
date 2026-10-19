| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/ffeecfa7) | iOS Phase 3: record status (implemented, CI-unverified) and the prepared simulator check |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/1f284673) | docs: iOS Phase 2C-B done on simulator; aquarium-platforms step 3 PASS (builds 6abd4a70, 6abd4f31) |
| [2026-05-05](https://github.com/wbniv/WorldFoundry/commit/74008c54) | chore: accumulated session work — docs, qbert scripts, engine tweaks |
| [2026-04-22](https://github.com/wbniv/WorldFoundry/commit/230f0e33) | docs(ios): Phase 2B3 verified — Metal RendererBackend links clean |
| [2026-04-22](https://github.com/wbniv/WorldFoundry/commit/5916ff3e) | docs(ios): Phase 2B2 verified — full engine links on iOS Sim |
| [2026-04-22](https://github.com/wbniv/WorldFoundry/commit/b821e9ae) | ios: Phase 2A verified — cornflower blue screenshot confirms Metal + CAMetalLayer + CADisplayLink |
| [2026-04-22](https://github.com/wbniv/WorldFoundry/commit/52895027) | ios: Phase 1 end-to-end verified via Codemagic sim-verify harness — HALGetAssetAccessor opens cd.iff from bundle; update plan + wf-status |
| [2026-04-22](https://github.com/wbniv/WorldFoundry/commit/5216fbe9) | ios: Phase 1 build green — include .app in Codemagic artifacts |
| [2026-04-21](https://github.com/wbniv/WorldFoundry/commit/d6699bd6) | ios: mark Phase 0 complete in plan + wf-status |
| [2026-04-21](https://github.com/wbniv/WorldFoundry/commit/7b4cb4a4) | ios: Phase 0 scaffolding — codemagic.yaml + plan refinements |
| [2026-04-21](https://github.com/wbniv/WorldFoundry/commit/8c5ba2a6) | iOS |

<!--history-meta v1
ffeecfa7	author	Will Norris
ffeecfa7	added	16
ffeecfa7	deleted	1
ffeecfa7	files	1
ffeecfa7	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
1f284673	author	Will Norris
1f284673	added	9
1f284673	deleted	0
1f284673	files	1
1f284673	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
74008c54	author	Will Norris
74008c54	added	1
74008c54	deleted	1
74008c54	files	1
74008c54	body	docs: new plans and investigations (qbert palette, round-clear, fall/lives,\n  cube-palette, camera-path revival, qbert-autopilot, zforth-coroutines);\n  updated level-building.md, level-design-troubleshooting.md, scripting-languages.md;\n  reference screenshots for per-round palette; session transcripts\n\nscripts/research/mame/qbert_palette_capture.lua: fix nil palette_dev —\n  emu.register_start is deprecated and fires before devices are ready;\n  moved DIP set + device lookup to frame 1 inside register_frame_done\n\nwflevels/qbert_practice/blender_create_qbert.py: apex respawn signal (mb[426])\n  replacing broken INDEXOF_X/Y/Z director writes\n\nengine/stubs/zfconf.h: dict size bump\nwfsource/source/mailbox/mailbox.inc: global mailbox range cap 0..998\nwfsource/source/gfx/gl/display.cc, main.cc: display/startup tweaks\nwflevels/marble-madness/*.iff, wfsource/source/game/cd.iff: binary level artifacts\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
230f0e33	author	Will Norris
230f0e33	added	1
230f0e33	deleted	1
230f0e33	files	1
230f0e33	body	Codemagic build 19 succeeded for commit 9f2dfa5. Metal backend\ncompiled + linked, AVFoundation/AudioToolbox/CoreAudio in link line,\nno runtime regressions (cornflower blue + cd.iff accessor still\nworking). Nothing drives the backend yet; Phase 2C wires MetalView's\nCADisplayLink to the engine frame loop + SetCurrentEncoder handoff.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
5916ff3e	author	Will Norris
5916ff3e	added	1
5916ff3e	deleted	1
5916ff3e	files	1
5916ff3e	body	~120 engine sources now compile and link for arm64 iOS Simulator.\nwf_game.app runs on iPhone 17 Pro with MetalView init + cd.iff\nopened in unified log, cornflower-blue clear still on screen.\n\nPhase 2B3 next: backend_metal.mm + MSL shaders.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
b821e9ae	author	Will Norris
b821e9ae	added	1
b821e9ae	deleted	1
b821e9ae	files	1
52895027	author	Will Norris
52895027	added	1
52895027	deleted	1
52895027	files	1
5216fbe9	author	Will Norris
5216fbe9	added	1
5216fbe9	deleted	1
5216fbe9	files	1
5216fbe9	body	**BUILD SUCCEEDED** confirmed in xcodebuild.log: wf_game.app linked,\nresources copied (cd.iff, level0.mid), storyboard compiled, Info.plist\nprocessed, dSYM generated, bundle validated. The artifact zip only\ncontained the log because the CMake RUNTIME_OUTPUT_DIRECTORY puts the\n.app under engine/Debug/ while my artifact glob was build-ios-sim/**.\nAdd engine/**/*.app + dSYM to the globs so next run ships the bundle.\n\nAlso update plan + wf-status to mark Phase 1 build green.
d6699bd6	author	Will Norris
d6699bd6	added	1
d6699bd6	deleted	1
d6699bd6	files	1
d6699bd6	body	Codemagic pipeline reached per-source compilation and stopped at the expected\nHAL gap (GL/gl.h not found in gfx/renderer.hp). That's stronger than the plan's\nPhase 0 verify bar (which was a CMake-stage error) — pipeline is end-to-end\ngreen, iOS-specific code is the only remaining gap.
7b4cb4a4	author	Will Norris
7b4cb4a4	added	2
7b4cb4a4	deleted	2
7b4cb4a4	files	1
7b4cb4a4	body	- codemagic.yaml: ios-simulator-debug workflow, mac_mini_m2, triggers on 2026-ios\n- plan: cut from 2026-android (not master — master is stale); push-per-step during bring-up, batch later\n- 2026-04-16-ios-port.md: stubbed, redirects to 2026-04-21 plan\n- wf-status.md: Summary paragraph prepended; moved Backlog → Active; branch flipped to 2026-ios\n\nPhase 0 "verify" is a failing Codemagic run pointing at missing hal/ios/ —\nthat failure is the signal the pipeline reaches the Mac toolchain.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
8c5ba2a6	author	Will Norris
8c5ba2a6	added	139
8c5ba2a6	deleted	0
8c5ba2a6	files	1
-->
