#!/usr/bin/env python3
"""Run native test code on the Android devices through the chromecast coordinator's ordinary `check`.

    python3 scripts/device_native_tests.py build
    python3 scripts/device_native_tests.py run --device chromecast-test-01 [--duration 90]
    python3 scripts/device_native_tests.py collect --device chromecast-test-01 --wf-log PATH
    python3 scripts/device_native_tests.py run --arm32 armv8 --device chromecast-test-02

`--arm32 armv8` (build and run) compiles the armeabi-v7a library for ARMv8 32-bit instead of the NDK's
ARMv7 default (docs/plans/2026-11-26-armv8-32bit-build.md): the APK is frozen as wf-native-tests-armv8-<sha16>.apk
and the results land in build/device-native-tests/<device>-armv8/, so
`tests/forth_math_agreement.py --target <device>-armv8` compares that build with the others. It is a
measurement option; the shipped engine build is unchanged.

Plan: docs/plans/2026-11-26-device-native-test-route.md. `build` makes the WF Native Tests APK
(android/native-tests: a NativeActivity with no Java) in the linux-test container, with the Android SDK
mounted read-only, for armeabi-v7a and arm64-v8a. The APK runs a fixed suite compiled into it and writes
the output to its own wf.log, which `check` returns as evidence. `run` registers the APK as the
coordinator app `wf-native-tests`, runs a `check` on one device, downloads the evidence and collects it.
`collect` checks the framing (a start line, every test's `rc=0`, the done line) and writes one file per
test under build/device-native-tests/<device>/, where tests/forth_math_agreement.py and
tests/forth_math_vm_cost.py read them.

Never point this at phone-pixel-8-pro (Will's daily phone) without his go-ahead: `run` refuses it unless
`--approved "<who, date, words>"` records that go-ahead (printed, and kept beside the results as approval.txt).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

SOURCE = ROOT / "android/native-tests"
SDK = Path(os.environ.get("WF_ANDROID_SDK", "/home/will/android-sdk-local"))
NDK_VERSION = "26.2.11394342"           # android/app/build.gradle.kts ndkVersion
BUILD_TOOLS = "34.0.0"
PLATFORM = "android-34"
API = 26                                # minSdkVersion in the manifest
ABIS = {"armeabi-v7a": "armv7a-linux-androideabi", "arm64-v8a": "aarch64-linux-android"}
WORK = ROOT / "build-docker/native-tests"           # /build/native-tests in the container
ARTIFACTS = ROOT / "build/coordinator-artifacts"    # the only root apk-stage accepts
RESULTS = ROOT / "build/device-native-tests"
KEY = RESULTS / "signing/development-signing.p12"   # outside build-docker, so a wipe there keeps updates installable
APP = "wf-native-tests"
PACKAGE = "org.worldfoundry.nativetests"
ACTIVITY = "android.app.NativeActivity"
MIN_FREE_BYTES = 6 * 1024**3
# The armeabi-v7a code generation: the NDK default (ARMv7-A, VFPv3-D16 + NEON) or ARMv8 32-bit (vrint, vfma).
ARM32_FLAGS = {"armv7": "", "armv8": "-march=armv8-a -mfpu=neon-fp-armv8 -mfloat-abi=softfp"}
REFUSED_DEVICES = {"phone-pixel-8-pro": "Will's daily phone: never without his go-ahead"}

START = re.compile(r"^=== wf-native-tests (\d+) start abi=(\S+)$")
BEGIN = re.compile(r"^=== begin (\S+)$")
END = re.compile(r"^=== end (\S+) rc=(-?\d+) ms=(\d+)$")
DONE = re.compile(r"^=== wf-native-tests done tests=(\d+) failed=(\d+)$")


class CollectError(Exception):
    pass


# ---------------------------------------------------------------- collect

def split(text: str) -> dict:
    """Check the framing of a WF Native Tests wf.log and return {"version", "abi", "tests": {name: {rc, ms, output}}}.

    Raises CollectError naming what is missing: no start line, a test that began and never ended (the app
    died or the check's duration ran out), a test that failed, or no done line."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if START.match(line)]
    if not starts:
        raise CollectError('no "=== wf-native-tests ... start" line: this is not a WF Native Tests log')
    if len(starts) > 1:
        raise CollectError(f"{len(starts)} start lines: the log holds more than one run")
    version, abi = START.match(lines[starts[0]]).groups()
    tests: dict = {}
    current = None
    body: list[str] = []
    done = None
    for line in lines[starts[0] + 1:]:
        if current is None:
            if m := BEGIN.match(line):
                current, body = m.group(1), []
            elif m := DONE.match(line):
                done = (int(m.group(1)), int(m.group(2)))
                break
            elif line.strip():
                raise CollectError(f"text outside any test: {line[:120]!r}")
        elif (m := END.match(line)) and m.group(1) == current:
            tests[current] = {"rc": int(m.group(2)), "ms": int(m.group(3)), "output": "\n".join(body) + ("\n" if body else "")}
            current = None
        else:
            body.append(line)
    if current is not None:
        raise CollectError(f"test {current} began and never ended: the app died, or the check's duration ran out "
                           f"(last output: {body[-1][:120]!r})" if body else f"test {current} began and never ended")
    if done is None:
        last = next(reversed(tests), None)
        raise CollectError('no "=== wf-native-tests done" line: the suite did not finish within the check\'s duration'
                           + (f" (last test ended: {last})" if last else ""))
    failed = [f"{name} rc={t['rc']}" for name, t in tests.items() if t["rc"]]
    if done != (len(tests), len(failed)):
        raise CollectError(f"done line says tests={done[0]} failed={done[1]}, the log shows {len(tests)} and {len(failed)}")
    if failed:
        raise CollectError("failed: " + ", ".join(failed))
    return {"version": int(version), "abi": abi, "tests": tests}


def collect(device: str, wf_log: Path, out: Path | None = None) -> dict:
    run = split(wf_log.read_text(errors="replace"))
    out = out or RESULTS / device
    out.mkdir(parents=True, exist_ok=True)
    for name, t in run["tests"].items():
        (out / f"{name}.txt").write_text(t["output"])
    summary = {"device": device, "version": run["version"], "abi": run["abi"], "source": str(wf_log),
               "tests": {name: {"rc": t["rc"], "ms": t["ms"]} for name, t in run["tests"].items()}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("collect: " + " · ".join(f"{n} rc={t['rc']} {t['ms']:,} ms" for n, t in run["tests"].items()))
    print(f"         → {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}/"
          "{" + ",".join(run["tests"]) + "}.txt")
    return summary


# ---------------------------------------------------------------- build

def png(width: int, height: int, rgb: tuple) -> bytes:
    """A solid-colour PNG, so the launcher banner needs no binary file in Git."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    row = b"\x00" + bytes(rgb) * width
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height, 9)) + chunk(b"IEND", b""))


def c_bytes(name: str, data: bytes) -> str:
    body = ",".join(str(b) for b in data)
    return f"static const unsigned char {name}[] = {{{body}}};\n"


def generate(work: Path) -> None:
    import forth_math_vm_cost as cost
    import verify_forth_math as vfm
    gen = work / "gen"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "vm_cost_host.cc").write_text(cost.HOST)
    requests = ("\n".join(cost.requests(cost.DEVICE_CALLS, cost.DEVICE_REPEATS)) + "\n").encode()
    (gen / "suite_inputs.inc").write_text(
        "// Generated by scripts/device_native_tests.py; do not edit.\n"
        + c_bytes("kVmCostBootstrap", vfm.bootstrap().encode())
        + c_bytes("kVmCostRequests", requests))
    res = work / "res/drawable"
    res.mkdir(parents=True, exist_ok=True)
    (res / "banner.png").write_bytes(png(320, 180, (0x2F, 0x85, 0x5A)))


CONTAINER_SCRIPT = r'''
set -euo pipefail
sdk=/opt/android-sdk
ndk=$sdk/ndk/{ndk}
bin=$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin
tools=$sdk/build-tools/{build_tools}
jar=$sdk/platforms/{platform}/android.jar
work=/build/native-tests
rm -rf "$work/obj" "$work/apk"
mkdir -p "$work/apk"
for abi in {abis}; do
    case $abi in
        armeabi-v7a) triple=armv7a-linux-androideabi{api}; arch=(-mthumb {arm32}) ;;
        arm64-v8a)   triple=aarch64-linux-android{api};    arch=() ;;
    esac
    obj=$work/obj/$abi; mkdir -p "$obj" "$work/apk/lib/$abi"
    cc="$bin/clang --target=$triple"; cxx="$bin/clang++ --target=$triple"
    flags=(-O3 -fPIC -ffunction-sections -fdata-sections "${{arch[@]}}")
    inc=(-I/src/engine/stubs -I/src/tests -I/src/engine/vendor/zforth-41db72d1/src/zforth -I"$work/gen" -I"$ndk/sources/android/native_app_glue")
    $cc "${{flags[@]}}" -c "$ndk/sources/android/native_app_glue/android_native_app_glue.c" -o "$obj/glue.o"
    # The VM and the cost host at -O2, as tests/forth_math_vm_cost.py compiles them on the PC; the rest at the
    # engine's Release -O3. Every file keeps the NDK's default FPU for the ABI, as the engine build does.
    vm=("${{flags[@]/-O3/-O2}}")
    $cc "${{vm[@]}}" "${{inc[@]}}" -c /src/engine/vendor/zforth-41db72d1/src/zforth/zforth.c -o "$obj/zforth.o"
    $cxx -std=c++17 -Wall "${{flags[@]}}" "${{inc[@]}}" -c /src/android/native-tests/main.cc -o "$obj/main.o"
    $cxx -std=c++17 -Wall "${{flags[@]}}" "${{inc[@]}}" -c /src/android/native-tests/cpuinfo.cc -o "$obj/cpuinfo.o"
    $cxx -std=c++17 -Wall "${{flags[@]}}" "${{inc[@]}}" -c /src/android/native-tests/fmaf_probe.cc -o "$obj/fmaf_probe.o"
    $cxx -std=c++17 "${{flags[@]}}" "${{inc[@]}}" -Dmain=wf_nt_forth_math_dump_main -c /src/tests/forth_math_dump.cpp -o "$obj/dump.o"
    $cxx -std=c++17 "${{vm[@]}}" "${{inc[@]}}" -Dmain=wf_nt_forth_math_vm_cost_main -c "$work/gen/vm_cost_host.cc" -o "$obj/vmcost.o"
    $cxx --target=$triple -shared -static-libstdc++ -Wl,--gc-sections -Wl,-u,ANativeActivity_onCreate \
        "$obj"/*.o -landroid -llog -lm -o "$work/apk/lib/$abi/libwfnativetests.so"
    $bin/llvm-strip --strip-unneeded "$work/apk/lib/$abi/libwfnativetests.so"
done
"$tools/aapt" package -f -M /src/android/native-tests/AndroidManifest.xml -S "$work/res" -I "$jar" -F "$work/unsigned.apk"
(cd "$work/apk" && for abi in {abis}; do "$tools/aapt" add -v "$work/unsigned.apk" "lib/$abi/libwfnativetests.so" >/dev/null; done)
"$tools/zipalign" -f -p 4 "$work/unsigned.apk" "$work/aligned.apk"
if [ ! -f /keys/development-signing.p12 ]; then
    keytool -genkeypair -keystore /keys/development-signing.p12 -storetype PKCS12 -storepass android -keypass android \
        -alias wfnativetests -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=World Foundry Native Tests Development" >/dev/null 2>&1
fi
"$tools/apksigner" sign --ks /keys/development-signing.p12 --ks-pass pass:android --out "$work/signed.apk" "$work/aligned.apk"
"$tools/apksigner" verify "$work/signed.apk"
'''


def free_bytes() -> int:
    return shutil.disk_usage(ROOT).free


def label(device: str, arm32: str = "armv7") -> str:
    """The results directory name of a device run: the device, or <device>-armv8 for the ARMv8 32-bit build."""
    return device if arm32 == "armv7" else f"{device}-{arm32}"


def build(arm32: str = "armv7") -> Path:
    if free_bytes() < MIN_FREE_BYTES:
        sys.exit(f"build: only {free_bytes() / 1024**3:.1f} GB free on the disk; stopping below 6 GB")
    for need in (SDK / "ndk" / NDK_VERSION, SDK / "build-tools" / BUILD_TOOLS, SDK / "platforms" / PLATFORM):
        if not need.exists():
            sys.exit(f"build: missing {need} (set WF_ANDROID_SDK to an SDK that has it)")
    WORK.mkdir(parents=True, exist_ok=True)
    KEY.parent.mkdir(parents=True, exist_ok=True)
    generate(WORK)
    script = CONTAINER_SCRIPT.format(ndk=NDK_VERSION, build_tools=BUILD_TOOLS, platform=PLATFORM, api=API,
                                     abis=" ".join(ABIS), arm32=ARM32_FLAGS[arm32])
    env = dict(os.environ, WF_CONTAINER_MOUNTS=f"{SDK}:/opt/android-sdk:ro {KEY.parent}:/keys",
               WF_CONTAINER_MEMORY=os.environ.get("WF_CONTAINER_MEMORY", "4g"))
    if subprocess.run([str(ROOT / "scripts/in-linux-container.sh"), "bash", "-c", script], env=env).returncode:
        sys.exit("build: the container build failed (its output is above)")
    signed = WORK / "signed.apk"
    digest = hashlib.sha256(signed.read_bytes()).hexdigest()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    prefix = "wf-native-tests-" if arm32 == "armv7" else f"wf-native-tests-{arm32}-"
    frozen = ARTIFACTS / f"{prefix}{digest[:16]}.apk"
    shutil.copyfile(signed, frozen)
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in [*sorted(SOURCE.glob("*")), ROOT / "tests/forth_math_dump.cpp", ROOT / "tests/forth_math_vm_cost.py",
                         ROOT / "tests/data/forth_math_vectors.inc", ROOT / "engine/stubs/forth_math.hpp",
                         ROOT / "engine/stubs/forth_math_zforth.hpp", ROOT / "engine/stubs/scripting_zforth.cc"]
               if p.is_file()}
    receipt = {"apk": str(frozen), "sha256": digest, "package": PACKAGE, "activity": ACTIVITY, "app": APP,
               "abis": list(ABIS), "ndk": NDK_VERSION, "arm32": arm32, "armeabi_v7a_flags": ARM32_FLAGS[arm32],
               "sources": sources}
    (RESULTS / ("receipt.json" if arm32 == "armv7" else f"receipt-{arm32}.json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"build: {frozen.relative_to(ROOT)} ({', '.join(ABIS)}), sha256 {digest}")
    return frozen


# ---------------------------------------------------------------- run

def coordinator(operation: str, **env: str) -> subprocess.CompletedProcess:
    """One coordinator CLI operation, as `task chromecast:<operation>` runs it."""
    full = dict(os.environ, **{f"WF_CC_{k.upper()}": v for k, v in env.items()})
    r = subprocess.run([sys.executable, str(ROOT / "scripts/chromecast.py"), "task", operation], env=full,
                       capture_output=True, text=True, cwd=ROOT)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r


def run(device: str, duration: int, apk: Path | None, approved: str | None = None, arm32: str = "armv7") -> int:
    if device in REFUSED_DEVICES:
        if not approved:
            sys.exit(f"run: {device}: {REFUSED_DEVICES[device]} (pass --approved \"<who, date, words>\" to record it)")
        print(f"run: {device}: approved: {approved}")
    apk = apk or build(arm32)
    name = label(device, arm32)
    r = coordinator("app-register", app=APP, apk=str(apk), activity=ACTIVITY, replace="true")
    if r.returncode:
        sys.exit(f"run: app-register failed (rc={r.returncode})")
    r = coordinator("check", device=device, app=APP, apk=str(apk), reinstall="true", duration=str(duration))
    if r.returncode and "target-left-foreground" in r.stdout:
        # Launched over a running dream, the device wakes to the Home screen moments after our launch and
        # Home takes the foreground (cast1, J-cef38c6016d1: original foreground DreamActivity, Home resumed
        # 5 s after `am start`). The first attempt has woken the device, so one more attempt finds Home.
        print("run: the check lost the foreground to the Home screen (launched over a dream); trying once more")
        r = coordinator("check", device=device, app=APP, apk=str(apk), reinstall="true", duration=str(duration))
    job = re.search(r"Accepted (J-[0-9a-f]+)", r.stdout)
    if not job:
        sys.exit("run: the check was not accepted")
    job = job.group(1)
    out = RESULTS / name / job
    e = coordinator("evidence", job=job, out=str(out))
    logs = sorted(out.rglob("wf.log"))
    if e.returncode or not logs:
        sys.exit(f"run: no wf.log in the evidence of {job} (check rc={r.returncode}, evidence rc={e.returncode})")
    print(f"evidence: {logs[0].relative_to(ROOT)} ({logs[0].stat().st_size:,} bytes)")
    if approved:
        (RESULTS / name).mkdir(parents=True, exist_ok=True)
        (RESULTS / name / "approval.txt").write_text(f"{approved}\njob {job}\n")
    try:
        collect(name, logs[0])
    except CollectError as error:
        print(f"collect: {error}", file=sys.stderr)
        return 1
    return 0 if r.returncode == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build the WF Native Tests APK in the container")
    b.add_argument("--arm32", choices=list(ARM32_FLAGS), default="armv7", help="armeabi-v7a code generation (default the NDK's ARMv7)")
    c = sub.add_parser("collect", help="check and split a WF Native Tests wf.log")
    c.add_argument("--device", required=True)
    c.add_argument("--wf-log", type=Path, required=True)
    c.add_argument("--out", type=Path, help="default build/device-native-tests/<device>")
    r = sub.add_parser("run", help="build, register, check on one device, download and collect")
    r.add_argument("--device", required=True)
    r.add_argument("--duration", type=int, default=30, help="the check's wait, seconds (a deadline; the done line is the signal)")
    r.add_argument("--apk", type=Path, help="an already built APK under build/coordinator-artifacts")
    r.add_argument("--arm32", choices=list(ARM32_FLAGS), default="armv7", help="armeabi-v7a code generation (default the NDK's ARMv7)")
    r.add_argument("--approved", help="the recorded go-ahead for a refused device, e.g. \"Will, 2026-11-26: run pixel\"")
    args = ap.parse_args()
    if args.command == "build":
        build(args.arm32)
        return 0
    if args.command == "collect":
        try:
            collect(args.device, args.wf_log, args.out)
        except CollectError as error:
            print(f"collect: {error}", file=sys.stderr)
            return 1
        return 0
    return run(args.device, args.duration, args.apk, args.approved, args.arm32)


if __name__ == "__main__":
    sys.exit(main())
