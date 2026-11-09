| Date | Change |
|------|--------|
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/d7e225a7) | Dream release: cast1 now runs the Release Aquarium Dream (ecf5e860) |
| [2026-11-09](https://github.com/wbniv/WorldFoundry/commit/12caf005) | Aquarium Dream ships as Release: 2.98 -> 21.8 FPS on the reef (cast1) |

<!--history-meta v1
d7e225a7	author	Will Norris
d7e225a7	added	2
d7e225a7	deleted	2
d7e225a7	files	1
d7e225a7	body	Will, 2026-11-09: cast1 should run the Release Dream, not the old Debug\n5dfdba1f. Installed through the coordinator (J-86a904b436e0,\ninstalled_sha256 ecf5e860...); Seahorse Grid stays selected, tank\nrandom, game APK untouched (J-aaef14afe56b).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
12caf005	author	Will Norris
12caf005	added	53
12caf005	deleted	0
12caf005	files	1
12caf005	body	Measured on cast1 through the coordinator (profile workflow, 3 runs,\nSurfaceFlinger presents of the Dream app's player), same HEAD bundle:\nreef 2.98 -> 21.80 FPS, anime reef 2.72 -> 19.98, clownfish 29.97 ->\n59.45. The Release Dream (screensaver-show) ran the reef with no\nassertion and its settings provider ready.\n\nDebug was never chosen: the screensaver's release build type had no\nsigningConfig, so only Debug produced an installable APK (fixed in\na39d33c8). New task build-aquarium-screensaver-apk (levels in the\ncontainer, then :screensaver:assembleAquariumRelease on the host);\nREADME updated; tests/test_screensaver_release_build.py guards the\nRelease variant. Seahorse Grid and Planted stay Debug (unmeasured).\ncast1 restored: Seahorse Grid selected, tank random, Aquarium\nscreensaver 5dfdba1f reinstalled, game APK untouched.\n\nEvidence: docs/diagnostics/dream-release-2026-11-09/.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
