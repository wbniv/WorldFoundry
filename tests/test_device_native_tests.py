"""`collect` in scripts/device_native_tests.py: accept a complete WF Native Tests log, refuse a broken one.

Plan: docs/plans/2026-11-26-device-native-test-route.md, verification 2. A device run whose suite did not
finish (the check's duration ran out, or the app died) must fail loudly, never pass on partial output.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("device_native_tests", ROOT / "scripts/device_native_tests.py")
dnt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dnt)

GOOD = """=== wf-native-tests 1 start abi=armeabi-v7a
=== begin cpuinfo
processor\t: 0
Features\t: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt lpae evtstrm
=== end cpuinfo rc=0 ms=4
=== begin forth-math-dump
floor 0 40000000
floor 1 ERR
=== end forth-math-dump rc=0 ms=1903
=== wf-native-tests done tests=2 failed=0
"""


def test_complete_log_splits_per_test(tmp_path):
    log = tmp_path / "wf.log"
    log.write_text(GOOD)
    summary = dnt.collect("cast-x", log, tmp_path / "out")
    assert (tmp_path / "out/forth-math-dump.txt").read_text() == "floor 0 40000000\nfloor 1 ERR\n"
    assert "Features" in (tmp_path / "out/cpuinfo.txt").read_text()
    assert summary["abi"] == "armeabi-v7a"
    assert json.loads((tmp_path / "out/summary.json").read_text())["tests"]["cpuinfo"] == {"rc": 0, "ms": 4}


@pytest.mark.parametrize("text, message", [
    ("", "not a WF Native Tests log"),
    (GOOD.split("=== end forth-math-dump")[0], "forth-math-dump began and never ended"),
    (GOOD.replace("=== wf-native-tests done tests=2 failed=0\n", ""), "no \"=== wf-native-tests done\" line"),
    (GOOD.replace("forth-math-dump rc=0", "forth-math-dump rc=1").replace("failed=0", "failed=1"), "failed: forth-math-dump rc=1"),
    (GOOD.replace("tests=2", "tests=3"), "done line says tests=3"),
    (GOOD + GOOD, "more than one run"),
    (GOOD.replace("=== begin cpuinfo\n", "stray\n=== begin cpuinfo\n"), "text outside any test"),
])
def test_broken_logs_are_refused(tmp_path, text, message):
    with pytest.raises(dnt.CollectError, match=message.replace("(", r"\(").replace(")", r"\)")):
        dnt.split(text)


def test_run_refuses_the_daily_phone():
    with pytest.raises(SystemExit, match="daily phone"):
        dnt.run("phone-pixel-8-pro", 90, None)


def script_for(arm32):
    return dnt.CONTAINER_SCRIPT.format(ndk=dnt.NDK_VERSION, build_tools=dnt.BUILD_TOOLS, platform=dnt.PLATFORM,
                                       api=dnt.API, abis=" ".join(dnt.ABIS), arm32=dnt.ARM32_FLAGS[arm32])


def test_arm32_armv8_changes_only_the_armeabi_v7a_flags():
    """--arm32 armv8 (docs/plans/2026-11-26-armv8-32bit-build.md) adds the ARMv8 flags to armeabi-v7a, nothing else."""
    v7, v8 = script_for("armv7"), script_for("armv8")
    v7a = next(line for line in v8.splitlines() if line.strip().startswith("armeabi-v7a)"))
    assert "-march=armv8-a -mfpu=neon-fp-armv8 -mfloat-abi=softfp" in v7a
    assert "-march" not in next(line for line in v8.splitlines() if line.strip().startswith("arm64-v8a)"))
    assert "-march" not in v7
    assert [a for a in v7.splitlines() if "armeabi-v7a)" not in a] == [b for b in v8.splitlines() if "armeabi-v7a)" not in b]


def test_arm32_results_have_their_own_directory():
    assert dnt.label("chromecast-test-02") == "chromecast-test-02"
    assert dnt.label("chromecast-test-02", "armv8") == "chromecast-test-02-armv8"
