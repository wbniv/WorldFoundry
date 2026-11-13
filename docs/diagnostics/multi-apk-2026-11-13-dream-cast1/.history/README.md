| Date | Change |
|------|--------|
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/d217ea72) | Multi-APK dream attempt 2: Seahorse Release at HEAD on cast1; allow-standby pending |
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/8f3ed151) | Multi-APK acceptance: per-app validators and cast2 held input pass; dream blocked |

<!--history-meta v1
d217ea72	author	Will Norris
d217ea72	added	25
d217ea72	deleted	0
d217ea72	files	1
d217ea72	body	Record cast1's before-state, the denied allow-standby configure call\n(waiting on Will), the finding that allow-standby leaves the 2 h\nsleep_timeout in place, and the HEAD Seahorse Release install\n(B-fc80f79c72a5, 25dfeda6 -> bd599a28) with the Dream still selected.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
8f3ed151	author	Will Norris
8f3ed151	added	46
8f3ed151	deleted	0
8f3ed151	files	1
8f3ed151	body	One RECIPE batch on cast2 (B-be5ba75e20e7) ran menu-back against Aquarium\nand baseline-settings against Baseline, both passing; the Baseline job\ncovers held/released D-pad input through an owned check. A two-APK install\non a dreaming cast could not be staged: screensaver-trigger ended\ndream-not-observed on cast1, likely because both casts keep\nstay_on_while_plugged_in 3. Simpleperf's coordinator bug is fixed\nupstream; the two-APK rerun still needs profileable current builds.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
