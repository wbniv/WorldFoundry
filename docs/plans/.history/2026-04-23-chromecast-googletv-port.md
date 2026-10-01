| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/47be054a) | Chromecast HD runs the aquarium: fix 32-bit ARM pool alignment, check the APK's ABIs in the device script |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/747442a4) | WIP aquarium Android/Chromecast app: product flavors, aquarium-only cd.iff, device script |
| [2026-04-23](https://github.com/wbniv/WorldFoundry/commit/943a14e6) | chromecast: Phase 0 + Phase 1 — TV banner image + Codemagic Android workflow |
| [2026-04-23](https://github.com/wbniv/WorldFoundry/commit/2a23a3bb) | android: Phase 1 — Codemagic android-apk-debug workflow |
| [2026-04-23](https://github.com/wbniv/WorldFoundry/commit/bfbd45d7) | docs: add chromecast/Google TV port plan (party-games-platform branch) |

<!--history-meta v1
47be054a	author	Will Norris
47be054a	added	1
47be054a	deleted	1
47be054a	files	1
47be054a	body	First run of the engine on 32-bit ARM (the Chromecast HD, Amlogic S805X2, armeabi-v7a only). MemPoolConstruct asserted that the\nentry size is a multiple of WF_POINTER_ALIGN (8 on 32-bit ARM); sizeof(SMsg) is 20 there and the app aborted. Round the entry\nsize up instead (no-op on 64-bit); MemPoolAllocate compares the rounded size. The device script compared the device ABIs with a\nhard-coded arm64 check: compare with the APK's actual lib/<abi> instead. Record the real-device result and correct the plan\n(the HD model is 32-bit only) in docs/porting-status.md and the Chromecast plan.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
747442a4	author	Will Norris
747442a4	added	2
747442a4	deleted	2
747442a4	files	1
747442a4	body	The aquarium as its own Android app next to snowgoons: Gradle flavors (own\napplicationId, label, icon, TV banner, assets/cd.iff), an aquarium-only cd.iff, a\ndevice install/run script, 16:9 captures, tests, and a -fno-exceptions guard in\nfatal.cc. Both flavor APKs build locally. Saved as a WIP commit when the agent\nwas stopped to conserve tokens; the plan write-up and the Codemagic run are pending.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
943a14e6	author	Will Norris
943a14e6	added	139
943a14e6	deleted	0
943a14e6	files	1
943a14e6	body	Phase 0: add 640×360 tv_banner.png placeholder + android:banner attribute to\nAndroidManifest; Google TV leanback launcher shows a tile instead of blank.\n\nPhase 1: android-apk-debug workflow in codemagic.yaml (Linux/free minutes);\nbuilds debug arm64 APK on every 2026-ios push, artifact downloadable without\na local Android SDK. NDK r26c installed via sdkmanager if absent on the agent.\n\nPlan: docs/plans/2026-04-23-chromecast-googletv-port.md\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
2a23a3bb	author	Will Norris
2a23a3bb	added	6
2a23a3bb	deleted	16
2a23a3bb	files	1
2a23a3bb	body	Linux instance (linux_x2), NDK r26c pinned, assembleDebug, APK artifact.\nManual trigger from Codemagic dashboard (no webhook yet).\n\nSee docs/plans/2026-04-23-chromecast-googletv-port.md Phase 1.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
bfbd45d7	author	Will Norris
bfbd45d7	added	141
bfbd45d7	deleted	0
bfbd45d7	files	1
bfbd45d7	body	Phase 0 already done (7219b5f). Phase 1 (Codemagic Android workflow) next.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
