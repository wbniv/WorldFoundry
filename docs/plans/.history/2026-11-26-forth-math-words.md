| Date | Change |
|------|--------|
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/7e365fa79) | Lava lamp mockup: colours through the Level Settings form; math plan Q1-Q3 accepted |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/a7e37975d) | Plan: Forth math words part 2, with a hardware support matrix |

<!--history-meta v1
7e365fa79	author	Will Norris
7e365fa79	added	4
7e365fa79	deleted	4
7e365fa79	files	1
7e365fa79	body	The mockup's colour swatches are replaced by a working replica of the\nlevel's Level Settings form (Clock / Lava lamp / Display sheets,\nLava color and Water color rows, Apply), since the colours belong to\nthe LavaLampSettings object. The math plan records Will's yes to\nQ1-Q3, and TODO gains the ARMv8 32-bit Chromecast build measurement.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
a7e37975d	author	Will Norris
a7e37975d	added	262
a7e37975d	deleted	0
a7e37975d	files	1
a7e37975d	body	Splits the lava lamp plan's E2 into its own plan: 27 words in three\ngroups (exact: floor ceil trunc round roundeven fma copysign fmod;\ninteger bits: popcount clz ctz; libm: exp expm1 exp2 pow ln log1p log2\nlog10 cbrt hypot and the hyperbolics). Marks which map to one hardware\ninstruction on each target (x86-64 as built, AArch64, the Chromecasts'\narmeabi-v7a build, ARMv8 32-bit, WebAssembly) and why it matters: the\nIEEE 754 required operations agree bit for bit everywhere. Phase 4\nreplaces four levels' hand-rolled floor loops.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
-->
