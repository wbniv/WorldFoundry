| Date | Change |
|------|--------|
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/61cb482a2) | Forth math on cast1 and cast2: CPU rows, VM cost, agreement (fma FAILs) |
| [2026-11-26](https://github.com/wbniv/WorldFoundry/commit/e2fca2b56) | WF Native Tests: run native test code on the Android devices through the coordinator's check |

<!--history-meta v1
61cb482a2	author	Will Norris
61cb482a2	added	4
61cb482a2	deleted	1
61cb482a2	files	1
61cb482a2	body	forth_math_agreement.py reads a device target's dump collected by\nscripts/device_native_tests.py instead of reporting every device NOT RUN,\nand its FAIL line names each failing word and target.\n\nRecorded in the math plan:\n- machine table: cast1 Amlogic S805X2, 4 x Cortex-A35 (0xd04), 1.8 GHz;\n  cast2 Amlogic S905D3, 4 x Cortex-A55 (0xd05), 1.908 GHz; both expose\n  vfpv4 to 32-bit code.\n- verification 4 on cast1: PASS (loop step 1,062 ns; floor 256, exp 314).\n- verification 5 on cast1 and cast2: 35 words bit-identical with the PC;\n  fma FAILs by one ulp on the plan's double-rounding vector, because\n  bionic's software fmaf (our armeabi-v7a code has no vfma) does not see\n  its own rounding-mode change. The Pixel stays NOT RUN.\nThe route plan lists the three fixes for Will to choose from.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
e2fca2b56	author	Will Norris
e2fca2b56	added	208
e2fca2b56	deleted	0
e2fca2b56	files	1
e2fca2b56	body	A NativeActivity APK with no Java (android/native-tests) runs a fixed suite\ncompiled into it (cpuinfo, the Forth math dump, the Forth math VM cost\nhost, an fmaf probe) and writes the framed output to its own wf.log. The\ncoordinator's ordinary check already returns the last 4 MB of that file as\nverified evidence, so no coordinator change was needed: the app is\nregistered with app-register as wf-native-tests.\n\nscripts/device_native_tests.py builds it in the linux-test container with\nthe SDK mounted read-only (armeabi-v7a and arm64-v8a; reproducible bit for\nbit), runs register + check + evidence through the coordinator CLI, and\ncollect checks the framing (start, every rc=0, done) and splits it per test\nunder build/device-native-tests/<device>/. run refuses the Pixel, and\nretries once when a launch over a dream loses the foreground to Home\n(cast1, J-cef38c6016d1).\n\nVerified on cast1 (J-35fecef59c35) and cast2 (J-1fa92c283b27).\nPlan: docs/plans/2026-11-26-device-native-test-route.md.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
-->
