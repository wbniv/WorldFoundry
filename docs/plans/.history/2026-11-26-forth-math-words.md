| Date | Change |
|------|--------|
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/a9cbca806) | Forth math plan: step 6 re-run after the triage; only Tide Harbour's actor budget fails |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/79e19d7a7) | Forth math: step 6 re-run after the collection fix |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/677552b8f) | Forth math: Pixel agreement run (Will's go-ahead); --approved override for refused devices |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/fbe8beb75) | Forth math verification 5: all 36 words bit-identical on cast1 and cast2 |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/f182f1080) | Forth math: exact fma without fmaf where there is no hardware FMA (D8) |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/61cb482a2) | Forth math on cast1 and cast2: CPU rows, VM cost, agreement (fma FAILs) |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/57abb43d2) | Plan: Forth math words part 2, verification recorded |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/7e365fa79) | Lava lamp mockup: colours through the Level Settings form; math plan Q1-Q3 accepted |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/a7e37975d) | Plan: Forth math words part 2, with a hardware support matrix |

<!--history-meta v1
a9cbca806	author	Will Norris
a9cbca806	added	21
a9cbca806	deleted	0
a9cbca806	files	1
a9cbca806	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
79e19d7a7	author	Will Norris
79e19d7a7	added	35
79e19d7a7	deleted	0
79e19d7a7	files	1
79e19d7a7	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
677552b8f	author	Will Norris
677552b8f	added	51
677552b8f	deleted	0
677552b8f	files	1
677552b8f	body	device_native_tests.py run still refuses phone-pixel-8-pro unless\n--approved records who agreed, and when (kept as approval.txt); the\nagreement check reads the Pixel only after such a run. Verification 5\nnow passes on all five targets.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
fbe8beb75	author	Will Norris
fbe8beb75	added	54
fbe8beb75	deleted	2
fbe8beb75	files	1
fbe8beb75	body	Re-run after D8 with WF Native Tests rebuilt (wf-native-tests-5e88a19a22b95a27,\nJ-a65c1a966084 on cast1, J-dd0d26859a46 on cast2): PC, WebAssembly and\nboth Chromecasts agree bit for bit on all 36 words, fma included; the\nPixel stays NOT RUN pending Will's go-ahead. The route plan's finding\nrecords Will's choice.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
f182f1080	author	Will Norris
f182f1080	added	3
f182f1080	deleted	0
f182f1080	files	1
f182f1080	body	Will chose option 1 (2026-11-26, "yes"). bionic's software fmaf, which\nthe Chromecasts' armeabi-v7a build calls because VFPv3 has no vfma,\nreturns 0x3f801001 for (1 + 2^-12)^2 - 1e-24 instead of 0x3f801000.\n\nforth_math.hpp gains ExactFmaf: the float product is exact in double, an\nerror-free two-sum adds c, the sum is rounded to odd, and one conversion\nto float rounds correctly (53 >= 24 + 2 bits). No rounding-mode change.\nFma keeps std::fma where the compiler reports an FMA instruction\n(__ARM_FEATURE_FMA, __FMA__, __FP_FAST_FMAF: AArch64, VFPv4/ARMv8 32-bit,\nx86 FMA3) and uses ExactFmaf elsewhere (armeabi-v7a, x86-64 at the SSE2\nbaseline, WebAssembly). WF_FORTH_MATH_SOFT_FMA forces it for tests; an\nx87 FLT_EVAL_METHOD 2 build is refused at compile time.\n\nforth_math_test checks ExactFmaf against glibc fmaf bit for bit: all\nedge-case triples (signed zeros, subnormals, FLT_MAX overflow, inf) and\n400,000 random cases (any finite floats, exact float ties nudged by tiny\nc, cancellation, subnormal results). task test-forth-math now builds five\nways, including -mfma (hardware path) and -DWF_FORTH_MATH_SOFT_FMA; all\nfive pass with 423,077 checks. A mutant without the round-to-odd step\nfails 10,050 of them. docs/forth-math-words.md and the plan's D8 say why.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
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
