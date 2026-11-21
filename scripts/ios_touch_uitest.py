#!/usr/bin/env python3
"""Real taps on the chapter's touch controls in the iOS Simulator (Codemagic).

Layer 3 of finding-your-way docs/plans/2026-11-08-ios-touch-parity.md. The
chapter run (scripts/ios_sim_chapter.py) presses the controls with
WF_TOUCH_SCRIPT, which skips UIKit's touch delivery. This runs the XCUITest
bundle in ios/uitests/ instead: XCUITest synthesises touch events that reach
wf_game through UIKit, so a pass means a tap on the glass of the simulator
reaches WFTouchHudView and comes out as the right joystick bits.

  1. xcodegen generates ios/uitests/WFTouchUITests.xcodeproj (installed with
     Homebrew if missing); xcodebuild build-for-testing builds it once.
  2. Per simulator (the iPhone and iPad ios_sim_chapter.py picks): boot,
     install the chapter copy of wf_game.app, xcodebuild test-without-building
     against it, keep the transcript, the .xcresult (zipped) and the app's
     touch log lines.
  3. Print one line per device and orientation from the TOUCHTEST lines the
     tests print (ios/uitests/tests/WFTouchUITests.swift).

Exit status 0 only when every check on every device passed. summarize() is
host-tested in tests/test_ios_touch_uitest.py.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UITESTS = REPO / "ios" / "uitests"
PROJECT = UITESTS / "WFTouchUITests.xcodeproj"
DERIVED = REPO / "build-uitests"
TOUCHTEST = re.compile(r"^TOUCHTEST (\w+) ([\w-]+) (PASS|FAIL) ?(.*)$", re.M)
EXPECTED = ["hud-present", "card-narrows", "hidden-b-ignored", "c-closes-card", "full-hud", "b-d-up", "released"]


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}", flush=True)


def summarize(text: str) -> dict:
    """{orientation: {"checks": {name: (ok, detail)}, "ok": bool}} from TOUCHTEST lines.
    An orientation is ok only when every expected check printed PASS (a check that never
    printed, because the test stopped early, counts as a failure)."""
    out: dict = {}
    for orientation, name, verdict, detail in TOUCHTEST.findall(text):
        out.setdefault(orientation, {"checks": {}})["checks"][name] = (verdict == "PASS", detail.strip())
    for o in out.values():
        o["missing"] = [n for n in EXPECTED if n not in o["checks"]]
        o["ok"] = not o["missing"] and all(ok for ok, _ in o["checks"].values())
    return out


def sh(cmd: list[str], log_to: Path | None = None, **kw) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    r = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if log_to:
        log_to.write_text(r.stdout + r.stderr)
    return r


def error_tail(text: str, n: int = 40) -> str:
    lines = [l for l in text.splitlines() if re.search(r"error|Error|FAIL|failed|\*\* TEST", l)]
    return "\n".join(lines[-n:]) or "\n".join(text.splitlines()[-n:])


def build(out: Path) -> bool:
    if not shutil.which("xcodegen"):
        sh(["brew", "install", "xcodegen"], out / "ios-touch-brew.log")
    r = sh(["xcodegen", "generate", "--spec", str(UITESTS / "project.yml")], out / "ios-touch-xcodegen.log")
    if r.returncode != 0:
        log("xcodegen failed:\n" + error_tail(r.stdout + r.stderr))
        return False
    r = sh(["xcodebuild", "build-for-testing", "-project", str(PROJECT), "-scheme", "WFTouchUITests",
            "-destination", "generic/platform=iOS Simulator", "-derivedDataPath", str(DERIVED)],
           out / "ios-touch-xcodebuild-build.log")
    log(f"build-for-testing exit {r.returncode}")
    if r.returncode != 0:
        log(error_tail(r.stdout + r.stderr))
    return r.returncode == 0


def run_device(label: str, udid: str, name: str, app: Path, out: Path) -> dict:
    log(f"=== {label}: {name} ({udid}) ===")
    sh(["xcrun", "simctl", "boot", udid])
    sh(["xcrun", "simctl", "bootstatus", udid, "-b"])
    if sh(["xcrun", "simctl", "install", udid, str(app)]).returncode != 0:
        return {"error": "install failed"}
    result = out / f"ios-touch-{label}.xcresult"
    shutil.rmtree(result, ignore_errors=True)
    env = dict(os.environ, TEST_RUNNER_WF_LAUNCH_ARGS=os.environ.get("FYW_LAUNCH_ARGS", ""))
    t0 = time.monotonic()
    r = sh(["xcodebuild", "test-without-building", "-project", str(PROJECT), "-scheme", "WFTouchUITests",
            "-destination", f"id={udid}", "-derivedDataPath", str(DERIVED), "-resultBundlePath", str(result),
            # Clones of the simulator would not have the chapter app installed.
            "-parallel-testing-enabled", "NO"],
           out / f"ios-touch-{label}-xcodebuild.log", env=env)
    seconds = int(time.monotonic() - t0) + 10
    applog = sh(["xcrun", "simctl", "spawn", udid, "log", "show", "--predicate",
                 # Every wf_game line, not only the touch ones: build 6af131a7's launches
                 # aborted at level load (LMalloc::Allocate -> FatalError), and the
                 # arguments and the engine's last lines are the evidence.
                 'processImagePath CONTAINS "wf_game"',
                 "--style", "compact", "--last", f"{seconds}s"]).stdout
    (out / f"ios-touch-{label}-app.log").write_text(applog)
    text = r.stdout + r.stderr
    if result.exists() and not TOUCHTEST.search(text):
        # Newer Xcodes may keep the tests' stdout in the result bundle only.
        c = sh(["xcrun", "xcresulttool", "get", "log", "--type", "console", "--path", str(result)])
        (out / f"ios-touch-{label}-console.log").write_text(c.stdout + c.stderr)
        text += "\n" + c.stdout
    if result.exists():
        shutil.make_archive(str(result), "zip", result.parent, result.name)
        shutil.rmtree(result, ignore_errors=True)
    sh(["xcrun", "simctl", "shutdown", udid])
    s = summarize(text)
    if not s:
        log(f"{label}: no TOUCHTEST lines; xcodebuild exit {r.returncode}:\n" + error_tail(text))
    return {"exit": r.returncode, "summary": s, "app_touch_lines": applog.count("touch buttons")}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app", type=Path, required=True, help="the chapter copy of wf_game.app")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("ios_sim_chapter", REPO / "scripts" / "ios_sim_chapter.py")
    chapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chapter)
    if not build(a.out):
        print("TOUCH REAL TAPS: NOT RUN (the UI-test project did not build; see ios-touch-xcodebuild-build.log)")
        return 1
    runtime, devices = chapter.pick_devices()
    log(f"runtime: {runtime}")
    rc = 0 if devices else 1
    print(f"=== real taps (XCUITest, runtime {runtime}) ===")
    for label, udid, name in devices:
        v = run_device(label, udid, name, a.app, a.out)
        summary = v.get("summary") or {}
        if not summary:
            print(f"TOUCH REAL TAPS {label.upper()}: NOT RUN ({v.get('error') or 'xcodebuild exit ' + str(v.get('exit'))}; "
                  f"see ios-touch-{label}-xcodebuild.log)")
            rc = 1
            continue
        for orientation in ("landscape", "portrait"):
            o = summary.get(orientation)
            if not o:
                print(f"TOUCH REAL TAPS {label.upper()} {orientation}: NOT RUN")
                rc = 1
                continue
            rc |= 0 if o["ok"] else 1
            print(f"TOUCH REAL TAPS {label.upper()} {orientation}: {'PASS' if o['ok'] else 'FAIL'}"
                  + (f" (missing {', '.join(o['missing'])})" if o["missing"] else ""))
            for n, (ok, detail) in o["checks"].items():
                print(f"  {n}: {'PASS' if ok else 'FAIL'} {detail}")
        print(f"  app log: {v.get('app_touch_lines')} 'touch buttons' lines")
    return rc


if __name__ == "__main__":
    sys.exit(main())
