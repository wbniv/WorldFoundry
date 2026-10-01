| Date | Change |
|------|--------|
| [2026-05-05](https://github.com/wbniv/WorldFoundry/commit/74008c54) | chore: accumulated session work — docs, qbert scripts, engine tweaks |
| [2026-04-18](https://github.com/wbniv/WorldFoundry/commit/ac9d9673) | docs(wf-status): close Android port; rename Deferred → Backlog; file plan follow-ups |
| [2026-04-18](https://github.com/wbniv/WorldFoundry/commit/97f176a1) | docs: Android Phase 0 4c done + OpenGL rewrite LOC accounting |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/1b3eeb13) | docs: mark Android Phase 0 step 4c (a+b) visually verified |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/f0eb7783) | feat(android): Phase 3 step 5 — AAssetManager backend for AssetAccessor |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/3b24f001) | feat(android): Phase 3 step 3 — Gradle project + AndroidManifest |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/4545c90c) | docs(android): Phase 0 step 4c scope — proper shader ports, not stubs |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/1724d092) | docs: update Android port plan + wf-status for Phase 0 steps 1/2/4a/4b |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/0f6c34ed) | docs(android): Phase 2 complete — mark plan + wf-status |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/bc9433ed) | docs(android): Phase 1 complete — CMake builds verified on Linux + Android |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/487730c1) | feat(android): Phase 1 — CMake build, NDK toolchain, arm64 porting fixes |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/bdc81b13) | docs(android-port): add per-phase time estimates (~5-6 weeks total) |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/b43b48bf) | docs(android-port): remove stale lua-not-special interim note |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/04290851) | docs(android-port): extend plan to cover Google TV / Chromecast |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/98911aec) | docs: rewrite wf-status summary; settle android gamepad question |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/44aaad7f) | docs: android plan + wf-status cleanup |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/6cd04979) | docs(android-port): clean up plan after review |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/a1d7cc65) | docs: close Jolt plan; settle Android/iOS open questions |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/f11f3d4f) | docs: lua-not-special plan + android Forth-only scripting update |
| [2026-04-16](https://github.com/wbniv/WorldFoundry/commit/d817b015) | docs: split mobile port investigation into Android + iOS plans |

<!--history-meta v1
74008c54	author	Will Norris
74008c54	added	1
74008c54	deleted	1
74008c54	files	1
74008c54	body	docs: new plans and investigations (qbert palette, round-clear, fall/lives,\n  cube-palette, camera-path revival, qbert-autopilot, zforth-coroutines);\n  updated level-building.md, level-design-troubleshooting.md, scripting-languages.md;\n  reference screenshots for per-round palette; session transcripts\n\nscripts/research/mame/qbert_palette_capture.lua: fix nil palette_dev —\n  emu.register_start is deprecated and fires before devices are ready;\n  moved DIP set + device lookup to frame 1 inside register_frame_done\n\nwflevels/qbert_practice/blender_create_qbert.py: apex respawn signal (mb[426])\n  replacing broken INDEXOF_X/Y/Z director writes\n\nengine/stubs/zfconf.h: dict size bump\nwfsource/source/mailbox/mailbox.inc: global mailbox range cap 0..998\nwfsource/source/gfx/gl/display.cc, main.cc: display/startup tweaks\nwflevels/marble-madness/*.iff, wfsource/source/game/cd.iff: binary level artifacts\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
ac9d9673	author	Will Norris
ac9d9673	added	1
ac9d9673	deleted	1
ac9d9673	files	1
ac9d9673	body	- Android port plan moved Active → Complete, marked Closed 2026-04-18.\n- Deferred table renamed Backlog; audio-assets-from-iff and Steam release\n  moved from Active to Backlog.\n- New plan docs/plans/2026-04-18-android-launcher-polish.md for the\n  remaining adaptive-icon XML work called out in the closure audit.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
97f176a1	author	Will Norris
97f176a1	added	6
97f176a1	deleted	6
97f176a1	files	1
97f176a1	body	Android port plan: mark 4c (a–f) all done. Notes the pre-legacy-gl-retire\ntag at 807d1ea for anyone who needs the last commit with backend_legacy.cc\npresent. Fog, rendmatt port, vestigial-call strip, and legacy retire all\nconfirmed; step (e) turned out to be a no-op because the remaining live\nfixed-function calls were already inside #if 0 or USE_ORDER_TABLES blocks.\n\nLOC tracking: new section "ff589c8 — Phase 0: retire immediate-mode GL"\nscoped to the 16 files the renderer seam + shader port actually touched\n(not the broader Android-port branch). Net: −541 LOC. The 8 per-variant\nrenderer TUs collapsed from 1,648 → 623 (−1,025) once the FLAG_TEXTURE ×\nFLAG_GOURAUD × FLAG_LIGHTING branching disappeared; that paid for the\nmodern backend (489), seam header (87), and factory stub (20).\nbackend_legacy.cc was transitional scaffolding — present from b868a26\nthrough 62ef11f but not in either endpoint.\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
1b3eeb13	author	Will Norris
1b3eeb13	added	3
1b3eeb13	deleted	3
1b3eeb13	files	1
1b3eeb13	body	Per-vertex normal attribute + directional lighting in the shader were\nalready plumbed end-to-end (backend, shader, camera.cc call sites).\nConfirmed on Linux: snowgoons with WF_RENDERER=modern renders at visual\nparity with the legacy fixed-function backend.\n\nRemaining 4c sub-steps: (c) fog, (d) rendmatt quads through the seam,\n(e) strip vestigial glMaterialfv/glShadeModel/glLightfv in display.cc,\n(f) retire backend_legacy.cc.\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
f0eb7783	author	Will Norris
f0eb7783	added	3
f0eb7783	deleted	3
f0eb7783	files	1
f0eb7783	body	hal/android/asset_accessor_aasset.cc (new): wraps\nAAssetManager_open / AAsset_read / AAsset_seek64 / AAsset_close /\nAAsset_getLength64 in the AssetAccessor interface. DiskFileHD sees\nthe same shape as on desktop (POSIX fd handles) — AAsset* just stands\nin.\n\nnative_app_entry.cc stashes app->activity->assetManager at\nandroid_main entry; asset_accessor_aasset.cc reads it during\n_PlatformSpecificInit (called from HALStart inside android_main's\nthread, so the UI thread has long since delivered the AAssetManager\npointer).\n\nhal/android/platform.cc switched over: HALCreateAAssetAccessor()\nreplaces HALCreatePosixAssetAccessor(). Fatal-errors if the pointer\nisn't stashed — programmer error, shouldn't ever fire.\n\nasset_accessor_posix.cc retired from hal/android/ (it was a dev-mode\nworkaround for adb push cd.iff → /data/local/tmp/; now the APK owns\nthe asset directly).\n\nAPK asset pipeline:\n- android/app/src/main/assets/cd.iff → symlink pointing at\n  wfsource/source/game/cd.iff (no copy, no staleness).\n- Gradle's default assets.srcDirs picks it up and bundles under\n  assets/ in the built APK.\n- At runtime AAssetManager_open("cd.iff") resolves directly to it.\n\nTaskfile push-assets task removed — no longer needed.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
3b24f001	author	Will Norris
3b24f001	added	8
3b24f001	deleted	8
3b24f001	files	1
3b24f001	body	android/ scaffolding:\n- settings.gradle.kts, build.gradle.kts (AGP 8.5.2)\n- app/build.gradle.kts: namespace=org.worldfoundry.wf_game,\n  compileSdk=34, minSdk=21, targetSdk=34, arm64-v8a only,\n  externalNativeBuild points at repo-root CMakeLists.txt\n- app/src/main/AndroidManifest.xml: NativeActivity with\n  android.app.lib_name=wf_game, landscape-locked, configChanges\n  to survive rotation/UI-mode flips. LAUNCHER + LEANBACK_LAUNCHER\n  intent-filters for phone/tablet + Google TV.\n- app/src/main/res/values/strings.xml\n- gradle.properties, .gitignore, README.md with setup + sideload\n  instructions.\n\nTaskfile: build-apk and install-apk targets.\n\nAPK build still requires the user to install Android SDK\nplatforms;android-34 + build-tools;34.0.0 + Gradle — the dev\nenvironment has NDK + platform-tools only. README documents the\ninstall path.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
4545c90c	author	Will Norris
4545c90c	added	16
4545c90c	deleted	3
4545c90c	files	1
4545c90c	body	Expand step 4c from a one-line bullet into six ordered sub-steps\n(a–f). Decision recorded: Android snowgoons keeps lit surfaces, fog,\nand matte background — no #ifndef __ANDROID__ strips. Shader ports\nfor directional lighting (N·L in vertex shader with ambient + three\ndir-lights, matching the current three-light fixed-function setup)\nand linear fog (eye-space-Z fragment mix) stand in for the retired\nglLightModelfv/glLightfv/glFogfv calls. Per-triangle normal promoted\nto a per-vertex attribute in the interleaved VBO. rendmatt.cc quads\ngo through the seam as two DrawTriangles per quad. Legacy backend\nretires after visual parity is confirmed.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
1724d092	author	Will Norris
1724d092	added	11
1724d092	deleted	9
1724d092	files	1
1724d092	body	Android port plan: mark Phase 0 as in progress. Itemise the four steps\nthat landed today (renderer backend seam, 7 TUs ported, matrix state\nrouted, modern VBO + shader backend) and call out step 4c as the\nremaining immediate-mode work in display.cc/camera.cc/rendmatt.cc.\n\nwf-status:\n- branch: 2026-first-working-gap → 2026-android\n- new "Graphics — retire immediate-mode GL" summary section\n- Android port row annotated "Phase 0 steps 1/2/4a/4b done"\n- Mobile port follow-up row refreshed\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
0f6c34ed	author	Will Norris
0f6c34ed	added	1
0f6c34ed	deleted	1
0f6c34ed	files	1
0f6c34ed	body	HAL lifecycle hooks + AssetAccessor POSIX backend landed. Phase 0 (GL rewrite)\nremains the next Android blocker; Phase 3 (Android platform proper) depends\non Phase 0.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
bc9433ed	author	Will Norris
bc9433ed	added	3
bc9433ed	deleted	3
bc9433ed	files	1
bc9433ed	body	Phase 1 verified:\n- Linux CMake binary launches snowgoons (smoke test)\n- Forth-only flag combination (Android-equivalent) compiles on Linux\n- Android build reaches expected Phase 0 boundary (GL/gl.h not found)\n\nPlan doc + wf-status updated. Next: Phase 2 (HAL lifecycle) or Phase 0 (GL rewrite).\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
487730c1	author	Will Norris
487730c1	added	5
487730c1	deleted	5
487730c1	files	1
487730c1	body	- CMakeLists.txt: full translation of build_game.sh; handles Linux + Android;\n  Android overrides force Forth-only scripting, no Steam, no REST API\n- scripts/gen_fennel_source.sh: helper for Fennel embed (avoids xxd path/symbol issues)\n- pigsys/cf_android.h: new Android platform config; defines __LINUX__ at end so\n  all 40+ downstream #if defined(__LINUX__) guards work without per-file patching\n- pigsys.hp: add #elif defined(__ANDROID__) → cf_android.h; rename ANDROID enum\n  member to MACHINE_ANDROID (NDK #define ANDROID 1 collides with enum name)\n- Taskfile.yml: add dev-setup (all deps), build-cmake, build-cmake-android tasks\n- 64-bit fixes: stack.cc const char*, collision.cc pointer→int32 truncation,\n  msgport.cc missing pragma paren, movementobject.hpi __LINE__ in pragma message\n- Redundant || defined(__ANDROID__) guards across 20 files (harmless with\n  __LINUX__ defined, but make intent explicit)\n- Android build reaches expected Phase 0 boundary: GL/gl.h not found\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
bdc81b13	author	Will Norris
bdc81b13	added	5
bdc81b13	deleted	0
bdc81b13	files	1
bdc81b13	body	Phase 0 (GL rewrite) 2-3 weeks; Phase 1 (CMake) 2-3 days;\nPhase 2 (HAL lifecycle) 2-3 days; Phase 3 (Android) 1 week;\nPhase 4 (smoke+perf) 2-3 days.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
b43b48bf	author	Will Norris
b43b48bf	added	0
b43b48bf	deleted	2
b43b48bf	files	1
b43b48bf	body	That plan landed in 7c9ed20; WF_LUA_ENGINE=none is available now.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
04290851	author	Will Norris
04290851	added	6
04290851	deleted	4
04290851	files	1
04290851	body	Same APK targets phone/tablet and Google TV. Add settled-decision row,\nruntime UI_MODE_TYPE_TELEVISION detection in Phase 3 input step,\nseparate TV verify step, and leanback manifest note in critical files.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
98911aec	author	Will Norris
98911aec	added	2
98911aec	deleted	1
98911aec	files	1
98911aec	body	- Summary: full 4-day recap across scripting, Blender pipeline, Jolt,\n  dead-code removal, tooling\n- android-port: gamepad moved to settled decisions table; performance\n  floor is the only remaining open question\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
44aaad7f	author	Will Norris
44aaad7f	added	3
44aaad7f	deleted	4
44aaad7f	files	1
44aaad7f	body	- android-port: gamepad in v1, arm32 removed, arm64-only\n- wf-status: remove stale Forth-backends item; mark CLI level load done\n  (-L<path> already in main.cc); update Blender pipeline status to\n  Phase 2c not started\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
6cd04979	author	Will Norris
6cd04979	added	35
6cd04979	deleted	28
6cd04979	files	1
6cd04979	body	- Remove Lua from critical files and Phase 1 steps (not in Android build)\n- Settle decisions table; trim open questions to the two genuinely open ones\n- lua-not-special added as prerequisite #1\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
a1d7cc65	author	Will Norris
a1d7cc65	added	3
a1d7cc65	deleted	3
a1d7cc65	files	1
a1d7cc65	body	- jolt-physics-finish: add Complete status header\n- android-port: settle asset bundling (cd.iff), API level (21),\n  remove MFi (iOS-only), rename gamepad question to Android InputDevice\n- ios-port: settle asset bundling (cd.iff), expand MFi definition\n  (Made for iPhone — Apple physical gamepad certification)\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
f11f3d4f	author	Will Norris
f11f3d4f	added	26
f11f3d4f	deleted	5
f11f3d4f	files	1
f11f3d4f	body	- New plan: make Lua optional (WF_LUA_ENGINE=lua54|none), peer to all\n  other engines. Fennel auto-enables Lua via #ifdef rather than a\n  build-script warning.\n- Android plan: updated scripting section — Forth-only target now lists\n  WF_LUA_ENGINE=none; notes lua-not-special plan as prerequisite.\n- wf-status: android plan summary updated to reflect Forth-only intent.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
d817b015	author	Will Norris
d817b015	added	91
d817b015	deleted	0
d817b015	files	1
d817b015	body	Promotes the combined investigation into two separate actionable plans\n(android-port, ios-port). iOS plan is explicitly blocked on Android.\nInvestigation file deleted; wf-status updated with new plan links.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
