| Date | Change |
|------|--------|
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/db989b40b) | Tide Harbour: nighttime 100-float cast1 profile, 24.58 FPS steady (J-f98fe5c023f4) |
| [2026-11-24](https://github.com/wbniv/WorldFoundry/commit/a54cbd6ec) | Add Loy Krathong to Tide Harbour |

<!--history-meta v1
db989b40b	author	Will Norris
db989b40b	added	11
db989b40b	deleted	0
db989b40b	files	1
db989b40b	body	Shipped Clocks code (APK 4ab6bddd..., built from 42533e702), Every night\nand Krathong count 100 set through the TV settings form, normal 1.2 s\nlaunches. Whole 440 s run 33.51 FPS; steady 100-float window 185-385 s\n24.58 FPS, p50 33.37 ms, p95 50.05 ms, 99.8 % missed refresh. D7's 30 FPS\ngate fails; 30 FPS breaks near 75-80 floats. Prior settings (Festival\nnights, 30) restored in the same run. TODO [T5] item updated, still Will's call.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
a54cbd6ec	author	Will Norris
a54cbd6ec	added	76
a54cbd6ec	deleted	0
a54cbd6ec	files	1
-->
