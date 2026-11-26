| Date | Change |
|------|--------|
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/a7e37975d) | Plan: Forth math words part 2, with a hardware support matrix |

<!--history-meta v1
a7e37975d	author	Will Norris
a7e37975d	added	262
a7e37975d	deleted	0
a7e37975d	files	1
a7e37975d	body	Splits the lava lamp plan's E2 into its own plan: 27 words in three\ngroups (exact: floor ceil trunc round roundeven fma copysign fmod;\ninteger bits: popcount clz ctz; libm: exp expm1 exp2 pow ln log1p log2\nlog10 cbrt hypot and the hyperbolics). Marks which map to one hardware\ninstruction on each target (x86-64 as built, AArch64, the Chromecasts'\narmeabi-v7a build, ARMv8 32-bit, WebAssembly) and why it matters: the\nIEEE 754 required operations agree bit for bit everywhere. Phase 4\nreplaces four levels' hand-rolled floor loops.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
-->
