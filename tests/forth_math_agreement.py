#!/usr/bin/env python3
"""Do the Forth math words give the same answers on every machine we run on?

    python3 tests/forth_math_agreement.py --target pc --target wasm [--target <device> ...]

Plan: docs/plans/2026-11-26-forth-math-words.md, Phase 3 and Verification 5. tests/forth_math_dump.cpp
runs all 36 words on the shared vectors and 2000 more arguments each, and prints every result's float
bits. This script builds and runs it per target and compares the targets with the first one:

  * groups A and B (floor ... fmod, popcount clz ctz) must be bit-identical, refusals included;
  * group C and the trig words must agree on which arguments are refused, and their spread is
    reported per word in float ulps (the plan's bar: at most one).

Targets:
  pc     g++ and glibc in the wf-linux-test container (docker/Dockerfile.linux-test)
  wasm   em++ (Emscripten), run under Emscripten's Node. The compiler is $EMCC_DIR/em++, by default the
         repo's pinned emsdk (engine/vendor/emsdk-6.0.0/upstream/emscripten; `task setup-emsdk`).
  <device>  an Android device by coordinator name: the same tests/forth_math_dump.cpp, compiled by the NDK into
         the WF Native Tests APK and run on the device through the coordinator's ordinary `check`
         (docs/plans/2026-11-26-device-native-test-route.md). This script reads the collected output,
         build/device-native-tests/<device>/forth-math-dump.txt; produce it with
         `python3 scripts/device_native_tests.py run --device <device>`. A device with no collected run
         reports NOT RUN and is left out of the comparison.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXACT = {"floor", "ceil", "trunc", "round", "roundeven", "fma", "copysign", "fmod", "popcount", "clz", "ctz"}
TRIG = {"sin-rev", "cos-rev", "tan-rev", "asin-rev", "acos-rev", "atan-rev", "atan2-rev", "sincos-rev", "sqrt"}
DEFAULT_EMCC_DIR = ROOT / "engine/vendor/emsdk-6.0.0/upstream/emscripten"


def run_pc(tmp: Path) -> str:
    cmd = ("set -euo pipefail; g++ -std=c++17 -O2 -I/src/engine/stubs -I/src/tests /src/tests/forth_math_dump.cpp "
           "-o /tmp/dump && /tmp/dump")
    r = subprocess.run(["docker", "run", "--rm", "--ulimit", "core=0", "--memory", "2g", "-v", f"{ROOT}:/src:ro",
                        "wf-linux-test:local", "bash", "-c", cmd], capture_output=True, text=True, check=True)
    return r.stdout


def run_wasm(tmp: Path) -> str:
    emdir = Path(os.environ.get("EMCC_DIR", DEFAULT_EMCC_DIR))
    empp = emdir / "em++"
    if not empp.exists():
        sys.exit(f"wasm: no Emscripten at {emdir} (run `task setup-emsdk`, or set EMCC_DIR to an emscripten directory)")
    out = tmp / "dump.js"
    subprocess.run([str(empp), "-std=c++17", "-O2", "-sENVIRONMENT=node", f"-I{ROOT / 'engine/stubs'}", f"-I{ROOT / 'tests'}",
                    str(ROOT / "tests/forth_math_dump.cpp"), "-o", str(out)], check=True, capture_output=True, text=True)
    cfg = emdir.parent.parent / ".emscripten"
    node = "node"
    if cfg.exists():                                   # Emscripten's own Node, as its config names it
        for line in cfg.read_text().splitlines():
            if line.startswith("NODE_JS"):
                node = line.split("=", 1)[1].strip().strip("'\"").replace("$CFGDIR", str(cfg.parent))
    version = subprocess.run([str(emdir / "emcc"), "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    print(f"wasm: {version}; node {subprocess.run([node, '--version'], capture_output=True, text=True).stdout.strip()}")
    return subprocess.run([node, str(out)], capture_output=True, text=True, check=True).stdout


DEVICE_RESULTS = ROOT / "build/device-native-tests"


def run_device(device: str) -> str | None:
    """The collected forth-math-dump output of a device, or None (and a NOT RUN line) if there is none."""
    path = DEVICE_RESULTS / device / "forth-math-dump.txt"
    if not path.exists():
        print(f"{device}: NOT RUN: no collected result at {path.relative_to(ROOT)}; "
              f"run `python3 scripts/device_native_tests.py run --device {device}`")
        return None
    summary = json.loads((path.parent / "summary.json").read_text())
    print(f"{device}: WF Native Tests v{summary['version']}, {summary['abi']}, NDK clang and bionic libm; "
          f"collected from {summary['source']}")
    return path.read_text()


def parse(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        word, k, v = line.split()
        out[(word, int(k))] = None if v == "ERR" else [int(x, 16) for x in v.split(",")]
    return out


def ordered(u: int) -> int:
    """Float bits as an integer that counts ulps across zero."""
    return u if u < 0x80000000 else 0x80000000 - u


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--target", action="append", required=True)
    args = ap.parse_args()
    results = {}
    with tempfile.TemporaryDirectory(prefix="forth-math-agree-") as t:
        tmp = Path(t)
        for target in args.target:
            if target == "pc":
                results[target] = parse(run_pc(tmp))
            elif target == "wasm":
                results[target] = parse(run_wasm(tmp))
            elif target == "phone-pixel-8-pro" and not (DEVICE_RESULTS / target / "approval.txt").exists():
                print(f"{target}: NOT RUN: Will's daily phone; needs an approved `device_native_tests.py run --approved`")
            elif (text := run_device(target)) is not None:
                results[target] = parse(text)
    if len(results) < 2:
        print("fewer than two targets ran: nothing to compare")
        return 1
    names = list(results)
    ref = results[names[0]]
    failures = []                                      # (word, target)
    print(f"{len(ref)} results per target; reference {names[0]}")
    print(f"{'word':12s} {'group':6s} " + " ".join(f"{n:>22s}" for n in names[1:]))
    for word in sorted({w for w, _ in ref}, key=lambda w: (w not in TRIG, w not in EXACT, w)):
        group = "trig" if word in TRIG else ("A/B" if word in EXACT else "C")
        cells = []
        for other in names[1:]:
            got = results[other]
            keys = [k for k in ref if k[0] == word]
            status = sum((ref[k] is None) != (got.get(k) is None) or k not in got for k in keys)
            diff = worst = 0
            for k in keys:
                a, b = ref[k], got.get(k)
                if a is None or b is None:
                    continue
                for x, y in zip(a, b):
                    d = abs(ordered(x) - ordered(y))
                    diff += d != 0
                    worst = max(worst, d)
            bad = status or (group == "A/B" and diff) or worst > 1
            if bad:
                failures.append((word, other))
            cells.append(f"{'FAIL ' if bad else ''}{diff} differ, max {worst} ulp" + (f", {status} refusal" if status else ""))
        print(f"{word:12s} {group:6s} " + " ".join(f"{c:>22s}" for c in cells))
    print("PASS" if not failures else "FAIL: " + ", ".join(f"{w} on {t}" for w, t in failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
