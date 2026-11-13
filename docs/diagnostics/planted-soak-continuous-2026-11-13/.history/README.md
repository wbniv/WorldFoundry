| Date | Change |
|------|--------|
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/ea997773) | Planted soak: continuous-sampling repeat on cast2 fails the 4 MiB PSS gate |

<!--history-meta v1
ea997773	author	Will Norris
ea997773	added	76
ea997773	deleted	0
ea997773	files	1
ea997773	body	The 914.8 s gap in J-c21e98845289 was the host laptop suspending\n(09:30-09:45 +0700) under a sampler timed with time.monotonic().\nThe repeat holds a systemd-inhibit sleep:idle lock, times on the wall\nclock and aborts on gaps over 60 s. J-bf9150654784: 50 reloads, PID\n30527 throughout, no crash; final-ten-minute PSS spread 11,848 KiB\n(34 samples, largest gap 20.6 s), mostly GL mtrack. Limit unchanged.\ncast2 settings and Seahorse Grid selection restored and read back.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
