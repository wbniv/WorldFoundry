# WF Native Tests

A small Android app that runs native test programs from this repo on a device and writes their output where the chromecast coordinator's ordinary `check` workflow already collects it. Plan: [docs/plans/2026‑11‑26‑device-native-test-route.md](../../docs/plans/2026-11-26-device-native-test-route.md).

- Package `org.worldfoundry.nativetests`, coordinator app id `wf-native-tests`, activity `android.app.NativeActivity`. No Java code and no Gradle.
- Libraries for `armeabi-v7a` (both Chromecasts) and `arm64-v8a` (the Pixel and the tablet).
- On launch it truncates `/sdcard/Android/data/org.worldfoundry.nativetests/files/wf.log`, runs every test on a worker thread, frames each one's output with `=== begin` and `=== end … rc=… ms=…`, and ends with `=== wf-native-tests done tests=… failed=…`. The screen is amber while it runs, then green (all passed) or red.
- `check` saves the last 4 MB of that `wf.log` as evidence; nothing in the coordinator was changed for this.

## Tests (suite version 2)

| Test | Source |
|---|---|
| `cpuinfo` | [`cpuinfo.cc`](cpuinfo.cc): `/proc/cpuinfo` as a process of this ABI sees it, `uname`, `AT_HWCAP`/`AT_HWCAP2`, SoC properties, per-core maximum frequency |
| `forth-math-dump` | [`tests/forth_math_dump.cpp`](../../tests/forth_math_dump.cpp), unchanged, for `tests/forth_math_agreement.py` |
| `forth-math-vm-cost` | the `HOST` program in [`tests/forth_math_vm_cost.py`](../../tests/forth_math_vm_cost.py) and the engine's zForth VM, fed the request script that file generates |
| `fmaf-probe` | [`fmaf_probe.cc`](fmaf_probe.cc): bionic's `fmaf` on the halfway case it rounds wrongly, whether `fesetround` works, and the same algorithm written out (plan, Findings) |

Adding a test: compile its program into the library in `scripts/device_native_tests.py` (a `main()` is renamed with `-Dmain=…`), add a row to `kTests` in [`main.cc`](main.cc), and raise `kSuiteVersion`.

## Use

```bash
python3 scripts/device_native_tests.py build                                  # container build, about 30 s
python3 scripts/device_native_tests.py run --device chromecast-test-02         # register, check, evidence, collect
python3 tests/forth_math_agreement.py --target pc --target chromecast-test-02
python3 tests/forth_math_vm_cost.py --device chromecast-test-02
```

`run` refuses `phone-pixel-8-pro` (Will's daily phone). The build signs with `build/device-native-tests/signing/development-signing.p12`, created on first build and ignored by Git; keep it, or uninstall the app from each device before installing a build signed with a new key.
