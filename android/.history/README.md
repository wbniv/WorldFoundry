| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/2adf90a9) | Docs: the Chromecast OK button, the condo's A for doors and shade, the phone as a gamepad, and building without sudo |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/747442a4) | WIP aquarium Android/Chromecast app: product flavors, aquarium-only cd.iff, device script |
| [2026-04-18](https://github.com/wbniv/WorldFoundry/commit/53fff413) | feat(android): launcher icons, APK rename, asset-pipeline remediation note |
| [2026-04-18](https://github.com/wbniv/WorldFoundry/commit/732252cd) | docs(android): port closure audit — status table + summary paragraph |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/f0eb7783) | feat(android): Phase 3 step 5 — AAssetManager backend for AssetAccessor |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/63e016ac) | chore(android): turn SDK install into an idempotent Task |
| [2026-04-17](https://github.com/wbniv/WorldFoundry/commit/3b24f001) | feat(android): Phase 3 step 3 — Gradle project + AndroidManifest |

<!--history-meta v1
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
