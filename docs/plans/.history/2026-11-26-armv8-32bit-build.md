| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/4e6b15da1) | ARMv8 32-bit plan: cast1 Aquarium restore verified |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/4f88937df) | ARMv8 32-bit Chromecast build: measured, recommend keeping ARMv7 |

<!--history-meta v1
4e6b15da1	author	Will Norris
4e6b15da1	added	3
4e6b15da1	deleted	2
4e6b15da1	files	1
4e6b15da1	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
4f88937df	author	Will Norris
4f88937df	added	306
4f88937df	deleted	0
4f88937df	files	1
4f88937df	body	Plan and results: docs/plans/2026-11-26-armv8-32bit-build.md. A measurement\nharness only; the shipped build is unchanged.\n\n- scripts/armv8_32bit_build.py: codegen probe (Forth words, a Jolt file),\n  container CMake build of libwf_dream.so for armeabi-v7a with and without\n  -march=armv8-a -mfpu=neon-fp-armv8 -mfloat-abi=softfp, instruction\n  histogram, APK packaging over the Gradle Aquarium, profile recipes and a\n  steady-window FPS summary.\n- scripts/device_native_tests.py: --arm32 armv8 builds the native test\n  suite for ARMv8 32-bit; results land in build/device-native-tests/<device>-armv8.\n  Test of the flag in tests/test_device_native_tests.py.\n\nResult: Lionfish FPS cast1 47.06 -> 47.24 (inside noise), cast2 30.01 ->\n30.03 (GPU-bound at native 4K); all 36 Forth words bit-identical with the\nPC on both casts both ways. TODO item left open as a decision for Will.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqPBXQwjNMi8EXwe2or
-->
