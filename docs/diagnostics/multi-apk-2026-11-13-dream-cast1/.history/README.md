| Date | Change |
|------|--------|
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/8f3ed151) | Multi-APK acceptance: per-app validators and cast2 held input pass; dream blocked |

<!--history-meta v1
8f3ed151	author	Will Norris
8f3ed151	added	46
8f3ed151	deleted	0
8f3ed151	files	1
8f3ed151	body	One RECIPE batch on cast2 (B-be5ba75e20e7) ran menu-back against Aquarium\nand baseline-settings against Baseline, both passing; the Baseline job\ncovers held/released D-pad input through an owned check. A two-APK install\non a dreaming cast could not be staged: screensaver-trigger ended\ndream-not-observed on cast1, likely because both casts keep\nstay_on_while_plugged_in 3. Simpleperf's coordinator bug is fixed\nupstream; the two-APK rerun still needs profileable current builds.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
