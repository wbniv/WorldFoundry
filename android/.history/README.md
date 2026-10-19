| Date | Change |
|------|--------|
| [2026-10-02](https://github.com/wbniv/WorldFoundry/commit/1bfe10f5) | Update Android badges and aquarium banner; fix NativeActivity reopening |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/ccede076) | The snowgoons app is called Snowgoons |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/a40da0de) | The smb app ships the world select: Android menu drawer, Back held 1 s returns to the menu |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/6db30e3f) | Docs: one Android app per game (README flavor table, porting status) |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/55a66fb8) | Phone controller QR: the World Foundry logo in the middle (planet by default, or the whole logo), at ECC H |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/2adf90a9) | Docs: the Chromecast OK button, the condo's A for doors and shade, the phone as a gamepad, and building without sudo |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/747442a4) | WIP aquarium Android/Chromecast app: product flavors, aquarium-only cd.iff, device script |
| [2026-04-18](https://github.com/wbniv/WorldFoundry/commit/53fff413) | feat(android): launcher icons, APK rename, asset-pipeline remediation note |
| [2026-04-18](https://github.com/wbniv/WorldFoundry/commit/732252cd) | docs(android): port closure audit — status table + summary paragraph |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/f0eb7783) | feat(android): Phase 3 step 5 — AAssetManager backend for AssetAccessor |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/63e016ac) | chore(android): turn SDK install into an idempotent Task |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/3b24f001) | feat(android): Phase 3 step 3 — Gradle project + AndroidManifest |

<!--history-meta v1
1bfe10f5	author	Will Norris
1bfe10f5	added	5
1bfe10f5	deleted	1
1bfe10f5	files	1
ccede076	author	Will Norris
ccede076	added	1
ccede076	deleted	1
ccede076	files	1
ccede076	body	Asked by the user. android/app/src/snowgoons/res/values/strings.xml overrides\nmain's "World Foundry" (log viewer: "Snowgoons Log"); the id stays\norg.worldfoundry.wf_game so installs upgrade in place, and the other labels are\nunchanged. Its launcher icons already override main's in every density and\nform (the snowman); a new test pins that, another pins every app's label.\nREADME, the split plan (Icons table, mockups) and a note in the icons plan\nfollow.\nPlan: docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
a40da0de	author	Will Norris
a40da0de	added	1
a40da0de	deleted	1
a40da0de	files	1
a40da0de	body	android/app/src/smb/assets/cd.iff now links wflevels/smb-menu-cd.iff (the four levels at\nsmb-cd.iff's TOC entries, so the flag/axe LEVEL_TO_RUN chain 1, 2, 3, 0 is unchanged, plus\nshell-menu.fth and the MENU chunk). gfx/gl/android_window.cc draws the menu's rectangles with\nthe phone panel's GLES path (HUD program, own VAO/VBO, re-uploaded on change, reset on\nEGL_CONTEXT_LOST); display.cc registers it on Android. In a menu bundle, Back held 1 s returns\nto the menu (decided from the event's down time, early on a repeat); a short Back still leaves\nthe app (ANativeActivity_finish). The menu loop waits while the app is suspended, as StepFrame\ndoes, and logs through levelmenu::Log (logcat tag wf_game on Android).\ntests/test_game_apps_android.py: the smb flavor ships the menu bundle and its levels keep the\nplain bundle's TOC entries; the built-APK check compares against the shipped bundle.\nPlan: docs/plans/2026-10-01-level-menu-selector.md (Phase D)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
6db30e3f	author	Will Norris
6db30e3f	added	10
6db30e3f	deleted	7
6db30e3f	files	1
6db30e3f	body	android/README.md lists the smb and qbert flavors and the per-game bundles\n(snowgoons now ships wflevels/snowgoons-cd.iff), the install-apk app list and\nwhich release builds need the soundfont. docs/porting-status.md: SMB,\nsnowgoons and Q*bert run as their own apps on the real Chromecast HD.\nPlan: docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
55a66fb8	author	Will Norris
55a66fb8	added	1
55a66fb8	deleted	0
55a66fb8	files	1
55a66fb8	body	The code is now ECC H (version 4 for a typical URL) and a centred plate of whole modules carries the logo,\ndrawn as coloured rectangles like the rest of the overlay. Two grids from scripts/gen-qr-logo.py (task\ngen-qr-logo), generated into phonepad_logo.h from ../worldfoundry.org/src/assets/wflogo.png with its SHA-256:\n"full", the whole logo on a 9 x 11 plate (9.1 % of a 33-module code), and "planet", the picture with the\nWORLD and FOUNDRY strips cropped off (found from the pixels: the black bands), on 7 x 7 (4.5 %). wf_args.txt\n"qr_logo=planet|full|none" picks one (default planet), read by native_app_entry.cc and kept from the engine.\nThe plate is held to 10 % of the modules, never touches finder, timing, format or alignment modules, and is\nleft out on version 1 and on versions 7 and up. favicon.svg was not used: it has no text strips and no planet.\n\ntests/qr_decode.py gains Reed-Solomon correction and a per-block damage map. Tests: both logos, sampled from\nthe composited overlay, read back to the exact URL for four URLs, with only plate modules changed, every\nfunction module untouched and at most 3/4 of any block's budget used; a plate over 25 % of the code fails;\nplate geometry for versions 2 to 6; the header regenerates byte for byte (skips without the logo source).\nOn the Chromecast HD both decoded from real screenshots (planet: at most 4 of 8 codewords repaired per block;\nfull: 5 of 8); the planet build is left installed. Plan design item 4 and verification 22; mockup 3 redrawn.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
2adf90a9	author	Will Norris
2adf90a9	added	18
2adf90a9	deleted	3
2adf90a9	files	1
2adf90a9	body	android/README.md gains the condo flavor, both ABIs, the no-sudo build and a "Playing on a Chromecast" section;\ndocs/porting-status.md records the OK button, the phone controller (user-tested), the latency finding and what is still open.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
747442a4	author	Will Norris
747442a4	added	19
747442a4	deleted	5
747442a4	files	1
747442a4	body	The aquarium as its own Android app next to snowgoons: Gradle flavors (own\napplicationId, label, icon, TV banner, assets/cd.iff), an aquarium-only cd.iff, a\ndevice install/run script, 16:9 captures, tests, and a -fno-exceptions guard in\nfatal.cc. Both flavor APKs build locally. Saved as a WIP commit when the agent\nwas stopped to conserve tokens; the plan write-up and the Codemagic run are pending.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
53fff413	author	Will Norris
53fff413	added	6
53fff413	deleted	5
53fff413	files	1
53fff413	body	- Launcher icons at all 5 mipmap densities (48/72/96/144/192 px) from the\n  WF logo. mdpi crops out the WORLD top bar + FOUNDRY right column since\n  the text is unreadable at 48×48; higher densities keep the full logo.\n  AndroidManifest.xml now references @mipmap/ic_launcher + ic_launcher_round.\n- APK output renamed to worldfoundry-debug.apk (was app-debug.apk) so the\n  file is self-identifying when uploaded to Drive and sideloaded.\n- build.gradle.kts comment was flagged as "stale" by the port-closure audit;\n  on review it's describing a transitional three-symlink assets/ layout that\n  still needs real remediation per docs/plans/2026-04-18-audio-assets-from-iff.md.\n  Closure-doc + README updated to point at the plan instead of calling for a\n  comment deletion.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
732252cd	author	Will Norris
732252cd	added	15
732252cd	deleted	4
732252cd	files	1
732252cd	body	Closure audit doc names remaining work (launcher icons, stale gradle\ncomment); README table refreshed to Phases 1–3 ✅ + post-boot polish;\nwf-status.md gets a reverse-chronological port-closure paragraph.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
f0eb7783	author	Will Norris
f0eb7783	added	4
f0eb7783	deleted	1
f0eb7783	files	1
f0eb7783	body	hal/android/asset_accessor_aasset.cc (new): wraps\nAAssetManager_open / AAsset_read / AAsset_seek64 / AAsset_close /\nAAsset_getLength64 in the AssetAccessor interface. DiskFileHD sees\nthe same shape as on desktop (POSIX fd handles) — AAsset* just stands\nin.\n\nnative_app_entry.cc stashes app->activity->assetManager at\nandroid_main entry; asset_accessor_aasset.cc reads it during\n_PlatformSpecificInit (called from HALStart inside android_main's\nthread, so the UI thread has long since delivered the AAssetManager\npointer).\n\nhal/android/platform.cc switched over: HALCreateAAssetAccessor()\nreplaces HALCreatePosixAssetAccessor(). Fatal-errors if the pointer\nisn't stashed — programmer error, shouldn't ever fire.\n\nasset_accessor_posix.cc retired from hal/android/ (it was a dev-mode\nworkaround for adb push cd.iff → /data/local/tmp/; now the APK owns\nthe asset directly).\n\nAPK asset pipeline:\n- android/app/src/main/assets/cd.iff → symlink pointing at\n  wfsource/source/game/cd.iff (no copy, no staleness).\n- Gradle's default assets.srcDirs picks it up and bundles under\n  assets/ in the built APK.\n- At runtime AAssetManager_open("cd.iff") resolves directly to it.\n\nTaskfile push-assets task removed — no longer needed.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
63e016ac	author	Will Norris
63e016ac	added	13
63e016ac	deleted	44
63e016ac	files	1
63e016ac	body	task android-sdk-install installs cmdline-tools + platforms;android-34 +\nbuild-tools;34.0.0 under /usr/lib/android-sdk/ and Gradle 8.7 under\n/opt/gradle-8.7/, then writes android/local.properties and prints the\nenv-var lines the user needs to add to their shell rc.\n\nRe-runs are safe — each step checks for the artifact before installing.\n\nNew peer tasks:\n- task build-apk      — gradle assembleDebug (auto-signed)\n- task install-apk    — adb install + start NativeActivity\n- task push-assets    — adb push cd.iff to /data/local/tmp/wf/\n\nREADME updated to point at the tasks instead of reciting the install\ncommands inline.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
3b24f001	author	Will Norris
3b24f001	added	73
3b24f001	deleted	0
3b24f001	files	1
3b24f001	body	android/ scaffolding:\n- settings.gradle.kts, build.gradle.kts (AGP 8.5.2)\n- app/build.gradle.kts: namespace=org.worldfoundry.wf_game,\n  compileSdk=34, minSdk=21, targetSdk=34, arm64-v8a only,\n  externalNativeBuild points at repo-root CMakeLists.txt\n- app/src/main/AndroidManifest.xml: NativeActivity with\n  android.app.lib_name=wf_game, landscape-locked, configChanges\n  to survive rotation/UI-mode flips. LAUNCHER + LEANBACK_LAUNCHER\n  intent-filters for phone/tablet + Google TV.\n- app/src/main/res/values/strings.xml\n- gradle.properties, .gitignore, README.md with setup + sideload\n  instructions.\n\nTaskfile: build-apk and install-apk targets.\n\nAPK build still requires the user to install Android SDK\nplatforms;android-34 + build-tools;34.0.0 + Gradle — the dev\nenvironment has NDK + platform-tools only. README documents the\ninstall path.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
