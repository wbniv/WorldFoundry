| Date | Change |
|------|--------|
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/95c2a96fd) | Aquarium: the applicationId becomes org.worldfoundry.game.aquarium (Will: the combined app is not called screensaver) |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/417ce50eb) | WF Clocks: applicationId org.worldfoundry.game.clocks (not pushed: lands with the registry change) |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/9e4f57ee4) | Menu key latch: record the verification (tests pass; APK build not run, the root volume cannot hold a full tree) and the README line |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/338950b34) | One Aquarium app: README for the two modes; plan verification recorded |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/1d35537cb) | WF Clocks: Tide Harbour is level 1, so the chooser appears; outputs committed and checked |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/35ec55da4) | WF Clocks: two-entry test build so the chooser appears for acceptance |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/596fc5585) | WF Clocks: its own icon and TV banner (a clock on brass gears), drawn by script |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/a727335ac) | WF Clocks: the TV remote drives the chooser; Back returns to it |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/eedb594c6) | WF Clocks: build-clocks-apk and clocks-bundle tasks, README row |
| [2026-11-21](https://github.com/wbniv/WorldFoundry/commit/c4ea9a0fd) | Aquarium roster: the screensaver bundle, tests and README read wflevels/aquarium-menu.manifest |
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/cd6b9e9e0) | Migrate runtime settings to actor OADs and preserve diagnostics |
| [2026-11-10](https://github.com/wbniv/WorldFoundry/commit/5e02476ed) | Seahorse Grid and Planted Dreams ship as Release (cast1: 4.2->29.6, 6.1->40.0 FPS) |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/12caf0057) | Aquarium Dream ships as Release: 2.98 -> 21.8 FPS on the reef (cast1) |
| [2026-10-24](https://github.com/wbniv/WorldFoundry/commit/fe4288505) | Take the default orientation from a string resource |
| [2026-10-24](https://github.com/wbniv/WorldFoundry/commit/9aebf986e) | Document the screensavers' orientation setting |
| [2026-10-23](https://github.com/wbniv/WorldFoundry/commit/d6995edd4) | Remove live screensaver logo overlay |
| [2026-10-23](https://github.com/wbniv/WorldFoundry/commit/d4b4070ae) | Split Android screensavers into flavor APKs |
| [2026-10-22](https://github.com/wbniv/WorldFoundry/commit/749e3bbfa) | docs: refresh planted tank verification status |
| [2026-10-22](https://github.com/wbniv/WorldFoundry/commit/80f43e987) | Use generic Settings catalogs for screensaver controls |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/d1676c334) | Planted Tank: generate the APK's coordinator settings from the OAD |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/3d56263d5) | Planted Tank Phase 4a: Taskfile build and test entries, coordinator and README docs |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/8876f6cd0) | Planted Tank screensaver: Java side (PlantedConfig, settings, provider, activity, Dream) |
| [2026-10-19](https://github.com/wbniv/WorldFoundry/commit/0df0c0ada) | Add branded aquarium and seahorse screensavers |
| [2026-10-18](https://github.com/wbniv/WorldFoundry/commit/54f44b515) | Add live aquarium screensaver with per-tank players |

<!--history-meta v1
95c2a96fd	author	Will Norris
95c2a96fd	added	2
95c2a96fd	deleted	2
95c2a96fd	files	1
95c2a96fd	body	Only the Gradle applicationId changes: the code package (namespace) stays org.worldfoundry.screensaver.\nThe provider authority and its meta-data follow ${applicationId}. A guard test pins both.\nNOT for 2026-new-level until the coordinator release that knows the new package is deployed\n(docs/handoffs/2026-11-22-game-package-rename-request.md in the coordinator repo).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
417ce50eb	author	Will Norris
417ce50eb	added	3
417ce50eb	deleted	3
417ce50eb	files	1
417ce50eb	body	Will's package standard org.worldfoundry.game.{name} (docs/plans/2026-11-22-one-aquarium-apk.md, D5). The clocks\nflavor's applicationId changes from org.worldfoundry.clocks; the namespace (org.worldfoundry.screensaver) does not.\nThe manifest's settings authority and the Dream's SETTINGS_AUTHORITY meta-data follow the id (${applicationId}.settings);\nthe provider's unused hard-coded AUTHORITY constant is gone. Docs, Taskfile, roster and TODO say the new id; am start\nexamples already use full class names (a leading dot resolves against the applicationId). The merged manifest from\nGradle has package org.worldfoundry.game.clocks and authorities org.worldfoundry.game.clocks.settings.\n\nA new applicationId is a new app: the old org.worldfoundry.clocks stays installed until removed by hand, saved settings\nstart fresh, the Dream must be selected again, and the coordinator registry entry clocks-screensaver (package, activity,\ndream_component, preview_activity, settings_authority) must change in the same administrator upgrade as the Aquarium's.\ntests/test_clocks_package_name.py guards the id and walks the tree for the old one.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqS8xiqchQY9wRjgxXo
9e4f57ee4	author	Will Norris
9e4f57ee4	added	1
9e4f57ee4	deleted	1
9e4f57ee4	files	1
9e4f57ee4	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQESZuwDoX7Vv9xJp5
338950b34	author	Will Norris
338950b34	added	14
338950b34	deleted	2
338950b34	files	1
338950b34	body	android/screensaver/README.md: the launcher activity shows the tank menu, the table of\nwhat each start does, the two bundles, and that the menu has no phone controller.\nThe plan records the built APK (17 386 111 bytes), Verification 1 to 3 and 8 with raw\noutput, and what steps 4 to 7 should show on Cast1.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQESZuwDoX7Vv9xJp5
1d35537cb	author	Will Norris
1d35537cb	added	2
1d35537cb	deleted	2
1d35537cb	files	1
1d35537cb	body	wflevels/clocks-menu.manifest gains exactly one line, appended:\n  level tide_harbour-standalone.iff | Tide Harbour | Tide Harbour\nThe roster is two clocks, so the engine shows its chooser instead of\nstarting the only level. The tests that pinned a one-clock roster now pin\n[minute_machine, tide_harbour] (tests/test_clocks_bundle.py), the\nclocks-bundle task's dependencies (tests/test_clocks_screensaver_catalog.py)\nand the README's roster; tests/test_clocks_remote_input.py pins no roster\nand is unchanged.\n\nPlan Q12, applied pending Will: both clocks' built .iff files and\nwflevels/clocks-cd.iff are committed (no longer git-ignored), and\ntask clocks-check (scripts/clocks-levels.sh check, the aquarium's\nrecipe) rebuilds them from a clean copy of the inputs in the Blender\ncontainer and lists any stale file; task clocks-regenerate rewrites\nthem. Minute Machine's rebuild leaves its tracked .lev and actor-map.json\nbyte-identical, which also proves the clock_common hoist changed nothing.\n\n  python3 scripts/pack-clocks-bundle.py (Linux container):\n  L0: 202752 bytes at sector 2 (minute_machine-standalone.iff)\n  L1: 256000 bytes at sector 101 (tide_harbour-standalone.iff)\n  MENU: 85 bytes at sector 226 ("WF Clocks", 2 entries)\n  pytest tests/test_clocks_bundle.py tests/test_clocks_screensaver_catalog.py tests/test_clocks_remote_input.py\n  25 passed\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
35ec55da4	author	Will Norris
35ec55da4	added	1
35ec55da4	deleted	0
35ec55da4	files	1
35ec55da4	body	With one clock the engine auto-starts it, so the remote-driven chooser\ncannot be seen. task build-clocks-two-entry-apk writes a throwaway\nmanifest (Minute Machine twice: minute_machine, minute_machine_b) and\nbundle under android/screensaver/build/clocks-two-entry/ and builds the\nclocks flavor with -PwfClocksManifest / -PwfClocksAssets, which\nbuild.gradle.kts now honours (defaults: the shipped manifest and\nsrc/clocks/assets). The shipped roster and its cd.iff link are not\ntouched; the test APK is copied to\nandroid/screensaver/build/clocks-two-entry/screensaver-clocks-two-entry-release.apk\nand checked for both ABIs. Same package id, so it replaces the shipped\napp on a device.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
596fc5585	author	Will Norris
596fc5585	added	1
596fc5585	deleted	1
596fc5585	files	1
596fc5585	body	The clocks flavor reused Minute Machine's render, so the banner read "Minute Machine" and the icon\nwas one clock level's picture. scripts/gen-wf-clocks-art.py now draws a 1280 x 720 frame and a\n720 x 720 tile (deterministic, the repository's Atkinson font); gen-screensaver-android-icons.py\nclocks turns them into the launcher icons and the banner titled "WF Clocks". The icon's bezel sits\ninside Android's inner two thirds, so neither the adaptive nor the legacy icon clips it.\n\nTest: tests/test_wf_clocks_art.py (committed art equals what the script draws; sizes; safe area).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
a727335ac	author	Will Norris
a727335ac	added	3
a727335ac	deleted	3
a727335ac	files	1
a727335ac	body	ClocksActivity maps D-pad up/down and OK (centre, Enter, gamepad A) to\nthe engine's EJ_BUTTONF_* bits (1 << EJ_BUTTONB_* of hal/sjoystic.h) and\nsends the held set through TankPlayer.buttons to a new\ndream_host.cc nativeButtons, which the game thread applies each frame\nwith the engine's own _HALSetJoystickButtons. Buttons are released on\nkey-up and on pause. Back in a clock picked from the chooser asks the\nengine to return to it (nativeBackToMenu -> levelmenu::RequestReturn,\nthe level-menu plan's rule); Back on the chooser, or with the LEVEL\nextra, finishes. Dreams, the preview and the other flavors never call\nnativeButtons, so the pump never touches their buttons.\n\ntests/test_clocks_remote_input.py pins the JNI symbols, the key table\nand its bits against sjoystic.h, release on key-up and pause, the Back\nrule, and that only ClocksActivity forwards input.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
eedb594c6	author	Will Norris
eedb594c6	added	11
eedb594c6	deleted	0
eedb594c6	files	1
eedb594c6	body	clocks-bundle packs wflevels/clocks-menu.manifest in the Linux container\n(cdpack built there); build-clocks-apk builds the Release APK and fails\nunless both lib/arm64-v8a and lib/armeabi-v7a libwf_dream.so are in it\n(Chromecasts are armeabi-v7a only; the Pixel and the tablet arm64-v8a).\nThe README gets the clocks row, its settings authority and a WF Clocks\nsection (launcher chooser, the LEVEL extra, the Dream, the provider).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPZiAJGsGH8BoMrdUT
c4ea9a0fd	author	Will Norris
c4ea9a0fd	added	1
c4ea9a0fd	deleted	1
c4ea9a0fd	files	1
c4ea9a0fd	body	build-aquarium-screensaver-levels.py takes TANKS from the manifest (scripts/level_manifest.py) and\nnames any id without a wflevels/<id>/ directory; the menu, input and Sea Stars tests read the\nmanifest instead of TankChoice.IDS or hard-coded counts; the Dream's plants variant is compared with\nits saltwater edit. New task test-level-catalog. The plain-Java tests named wf-tv-media-phase0-jdk:local,\nan image no tracked Dockerfile builds; wf-linux-test now carries openjdk-21-jdk-headless (own layer)\nand both Java test tasks use it.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQK4d6bNq4g8sreMn2
cd6b9e9e0	author	Will Norris
cd6b9e9e0	added	8
cd6b9e9e0	deleted	8
cd6b9e9e0	files	1
5e02476ed	author	Will Norris
5e02476ed	added	8
5e02476ed	deleted	11
5e02476ed	files	1
5e02476ed	body	Measured on cast1 through the coordinator profile workflow, 3 runs each,\nDebug and Release from the same bundles: Seahorse Grid 4.18 -> 29.64 FPS,\nPlanted Tank 6.06 -> 39.99. Each Release Dream ran in the real Dream path\n(screensaver-show + screensaver-status) with no assertion and its settings\nprovider ready.\n\nbuild-planted-apk now assembles PlantedRelease; new\nbuild-seahorse-screensaver-apk (bundles in the container, then\nassembleSeahorseRelease). tests/test_screensaver_release_build.py covers\nall three Dream tasks. README and device-coordinator.md give the Release\noutputs. cast1: Seahorse Grid selected, Release Dreams installed for\nSeahorse (25dfeda6) and Planted (bccdf04b), settings and game APK\nuntouched.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
12caf0057	author	Will Norris
12caf0057	added	5
12caf0057	deleted	3
12caf0057	files	1
12caf0057	body	Measured on cast1 through the coordinator (profile workflow, 3 runs,\nSurfaceFlinger presents of the Dream app's player), same HEAD bundle:\nreef 2.98 -> 21.80 FPS, anime reef 2.72 -> 19.98, clownfish 29.97 ->\n59.45. The Release Dream (screensaver-show) ran the reef with no\nassertion and its settings provider ready.\n\nDebug was never chosen: the screensaver's release build type had no\nsigningConfig, so only Debug produced an installable APK (fixed in\na39d33c8). New task build-aquarium-screensaver-apk (levels in the\ncontainer, then :screensaver:assembleAquariumRelease on the host);\nREADME updated; tests/test_screensaver_release_build.py guards the\nRelease variant. Seahorse Grid and Planted stay Debug (unmeasured).\ncast1 restored: Seahorse Grid selected, tank random, Aquarium\nscreensaver 5dfdba1f reinstalled, game APK untouched.\n\nEvidence: docs/diagnostics/dream-release-2026-11-09/.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
fe4288505	author	Will Norris
fe4288505	added	1
fe4288505	deleted	1
fe4288505	files	1
fe4288505	body	R.string.default_orientation (src/main/res/values/orientation.xml,\nlandscape) is the one shared default; a flavor would override it with\nits own res/values/orientation.xml, and none does. OrientationSettings\nfalls back to it when nothing valid is saved, and so do the providers'\nreported values; an invalid resource value falls back to landscape.\nOrientationChoice.savedOrDefault takes the default as an argument so\nOrientationChoiceTest stays Android-free.\n\nPlan: docs/plans/2026-10-24-screensaver-landscape-orientation.md\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01PkFSbo6jcue9Gfyb6U9HVs
9aebf986e	author	Will Norris
9aebf986e	added	30
9aebf986e	deleted	3
9aebf986e	files	1
9aebf986e	body	android/screensaver/README.md: the three values, where they are\napplied, each provider's setting ID and the screensaver-setting\ncommand, and that the coordinator's Seahorse Grid entry still needs a\nsettings_authority before the tray lists it.\n\nPlan: docs/plans/2026-10-24-screensaver-landscape-orientation.md\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01PkFSbo6jcue9Gfyb6U9HVs
d6995edd4	author	Will Norris
d6995edd4	added	1
d6995edd4	deleted	1
d6995edd4	files	1
d4b4070ae	author	Will Norris
d4b4070ae	added	8
d4b4070ae	deleted	8
d4b4070ae	files	1
749e3bbfa	author	Will Norris
749e3bbfa	added	3
749e3bbfa	deleted	5
749e3bbfa	files	1
80f43e987	author	Will Norris
80f43e987	added	2
80f43e987	deleted	2
80f43e987	files	1
d1676c334	author	Will Norris
d1676c334	added	2
d1676c334	deleted	2
d1676c334	files	1
d1676c334	body	Will's decision (docs/plans/2026-10-21-planted-tank-screensaver.md): the APK's\nsettings come from the OAD, not a second copy in Java.\n\n- scripts/gen-planted-capabilities.py reads the compiled settings-class OAD\n  (type name ending in Settings) through build-object-properties.py's\n  normalizer (new oad_schema()) and writes the schema-1 capabilities JSON.\n  Labelled choices (radio, labelled slider) become choice; Hold's number\n  keeps the 1/2/5/10 min presets, validated against the OAD range; Paused\n  is dropped; checkbox/text/bare-number fields are skipped with a warning.\n- build_planted() writes it to the planted flavor's assets (gitignored).\n- PlantedSettingsProvider.getCapabilities serves the asset with the saved\n  values overlaid (same document as before) and throws if it is missing.\n- PlantedConfigTest takes the generated JSON and fails when PlantedConfig\n  and the OAD disagree; tests/test_planted_capabilities.py pins the\n  document; task test-planted-screensaver runs both.\n- Docs: replace the unconfirmed "coordinator does not register the\n  package" claim with what the APK declares.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
3d56263d5	author	Will Norris
3d56263d5	added	2
3d56263d5	deleted	0
3d56263d5	files	1
3d56263d5	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
8876f6cd0	author	Will Norris
8876f6cd0	added	23
8876f6cd0	deleted	0
8876f6cd0	files	1
8876f6cd0	body	Phase 2a of docs/plans/2026-10-21-planted-tank-screensaver.md. PlantedConfig is a\npure-Java validator for water, seed, speed, hold and the developer keys, with a\nplain-javac test. PlantedSettings, PlantedSettingsProvider, PlantedTankActivity and\nPlantedTankDreamService wrap it; TankPlayer gains an additive configure(line) that\ncalls nativeConfigure only when set. The planted flavor manifest and strings are in\nsrc/planted; the Gradle flavor itself is not in this commit.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
0df0c0ada	author	Will Norris
0df0c0ada	added	5
0df0c0ada	deleted	1
0df0c0ada	files	1
54f44b515	author	Will Norris
54f44b515	added	20
54f44b515	deleted	0
54f44b515	files	1
-->
