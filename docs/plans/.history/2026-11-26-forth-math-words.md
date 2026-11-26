| Date | Change |
|------|--------|
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/61cb482a2) | Forth math on cast1 and cast2: CPU rows, VM cost, agreement (fma FAILs) |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/57abb43d2) | Plan: Forth math words part 2, verification recorded |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/7e365fa79) | Lava lamp mockup: colours through the Level Settings form; math plan Q1-Q3 accepted |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/a7e37975d) | Plan: Forth math words part 2, with a hardware support matrix |

<!--history-meta v1
61cb482a2	author	Will Norris
61cb482a2	added	86
61cb482a2	deleted	7
61cb482a2	files	1
61cb482a2	body	forth_math_agreement.py reads a device target's dump collected by\nscripts/device_native_tests.py instead of reporting every device NOT RUN,\nand its FAIL line names each failing word and target.\n\nRecorded in the math plan:\n- machine table: cast1 Amlogic S805X2, 4 x Cortex-A35 (0xd04), 1.8 GHz;\n  cast2 Amlogic S905D3, 4 x Cortex-A55 (0xd05), 1.908 GHz; both expose\n  vfpv4 to 32-bit code.\n- verification 4 on cast1: PASS (loop step 1,062 ns; floor 256, exp 314).\n- verification 5 on cast1 and cast2: 35 words bit-identical with the PC;\n  fma FAILs by one ulp on the plan's double-rounding vector, because\n  bionic's software fmaf (our armeabi-v7a code has no vfma) does not see\n  its own rounding-mode change. The Pixel stays NOT RUN.\nThe route plan lists the three fixes for Will to choose from.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
57abb43d2	author	Will Norris
57abb43d2	added	104
57abb43d2	deleted	9
57abb43d2	files	1
57abb43d2	body	Phases 1, 2 and 4 struck through as done; Phase 0 and 3 done on the PC and\nin WebAssembly (the VM dominates: a loop step is 274 ns, a word adds 32-89;\nPC and WASM agree on every bit of 74,990 results). Device rows pending: no\ncoordinator workflow runs a native binary or reads /proc/cpuinfo. Steps 1-3\nand 7 PASS; step 4 and 5 PASS for PC/WASM, NOT RUN on devices; step 6's\npytest command as written is interrupted by unrelated collection errors,\nwith the per-level runs recorded.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
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
