| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/79f0728f) | Android: stay suspended until the window returns (fixes Home-then-reopen abort); condo results |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/3bb78cf2) | Plan the condo on the Chromecast HD, with mockups |

<!--history-meta v1
79f0728f	author	Will Norris
79f0728f	added	124
79f0728f	deleted	20
79f0728f	files	1
79f0728f	body	Home then reopen aborted both the condo and the aquarium on the real Chromecast HD\n(signal 6, GL error 1286 at gfx/gl/display.cc:866). APP_CMD_RESUME arrives about\n120 ms before APP_CMD_INIT_WINDOW, so the game loop drew into no EGL surface.\nHALIsSuspended() now also returns true until WFAndroidHasWindow(); the suspended\nloop keeps pumping events until the window is back.\n\nGuards: android-device-run.sh --resume (Home, reopen, require alive and drawing)\nand a static test. Verified on the device, both apps: alive after Home + reopen.\n\nThe condo plan gets its Verification results (59.9 fps release, 49 to 61 MB) and\nthe corrected finding: the assertion was missing --vram-* flags on Android, not a\nbad level. porting-status.md gains the condo on the Chromecast HD and CI build\n6abd6b03.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
3bb78cf2	author	Will Norris
3bb78cf2	added	112
3bb78cf2	deleted	0
3bb78cf2	files	1
3bb78cf2	body	Same recipe as the aquarium app (flavor, aquarium-style cd.iff, real-capture art), judged on a release build. Lists the risks found\ntoday (13x bigger level, 32-bit, a 1024-px texture the engine's 256-px limit rejects in debug builds, 4:3-only framing, remote vs\ngamepad controls) with a numbered Verification section, all PENDING. Three self-contained mockups: launcher row, running and controls,\nstates.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
-->
