#!/usr/bin/env python3
"""What a Forth math word costs in the real zForth VM, per call.

    scripts/in-linux-container.sh python3 tests/forth_math_vm_cost.py [--calls 10000] [--repeats 7]

Plan: docs/plans/2026-11-26-forth-math-words.md, Phase 0 and Verification 4: "the VM dominates". The VM,
the bootstrap and the word table are the engine's own (tests/verify_forth_math.py builds them), compiled
with -O2. Each case is a colon definition that runs a word `--calls` times in a `do ... loop`, timed as one
zf_eval with a steady clock; the same loop with the word replaced by nothing (`2 drop`) is subtracted, so
the number is the word's own cost: the call into the word, its `sys`, the host's dispatch and the maths.
`nop-sys` is a syscall that pops a value and pushes it back, the cheapest a word can be. The best of
`--repeats` runs is reported, to keep scheduler noise out.

    python3 tests/forth_math_vm_cost.py --device chromecast-test-01

reads the same replies from a device instead: the WF Native Tests APK runs this file's HOST against the
requests `requests(DEVICE_CALLS, DEVICE_REPEATS)` generates, and `scripts/device_native_tests.py run`
collects its output to build/device-native-tests/<device>/forth-math-vm-cost.txt
(docs/plans/2026-11-26-device-native-test-route.md). The PC and the device share one request script
and one parser.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import verify_forth_math as vfm  # noqa: E402

NOP = 250            # a custom syscall number no word uses; this host answers it with pop-and-push

HOST = r'''
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include "forth_math_zforth.hpp"
static zf_ctx ctx;
extern "C" zf_input_state zf_host_sys(zf_ctx* c, zf_syscall_id id, const char*) {
  const int custom = (int)id - (int)ZF_SYSCALL_USER;
  if (id == ZF_SYSCALL_EMIT) zf_pop(c);
  else if (id == ZF_SYSCALL_TELL) { zf_pop(c); zf_pop(c); }
  else if (custom == NOP) zf_push(c, zf_pop(c));
  else if ((int)id >= (int)ZF_SYSCALL_USER && wf::forthmath::HandleSyscall(c, custom)) {}
  else { std::fprintf(stderr, "unexpected syscall %d\n", (int)id); std::abort(); }
  return ZF_INPUT_INTERPRET;
}
extern "C" void zf_host_trace(zf_ctx*, const char*, va_list) {}
extern "C" zf_cell zf_host_parse_num(zf_ctx* c, const char* s) {
  char* e; float n = strtof(s, &e);
  if (*e) { std::fprintf(stderr, "Unknown: %s\n", s); zf_abort(c, ZF_ABORT_NOT_A_WORD); }
  return n;
}
static std::string slurp(const char* path) {
  FILE* f = std::fopen(path, "r"); std::string s; char buf[4096]; size_t n;
  while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) s.append(buf, n);
  std::fclose(f); return s;
}
int main(int argc, char** argv) {
  zf_init(&ctx, 0); zf_bootstrap(&ctx);
  if ((int)zf_eval(&ctx, slurp(argv[1]).c_str())) { std::printf("LOADERR\n"); return 1; }
  for (const auto& w : wf::forthmath::kWords) {
    char buf[64]; std::snprintf(buf, sizeof buf, ": %s %d sys ;", w.name, (int)ZF_SYSCALL_USER + w.custom);
    if ((int)zf_eval(&ctx, buf)) { std::printf("REGERR %s\n", w.name); return 1; }
  }
  char buf[64]; std::snprintf(buf, sizeof buf, ": nop-sys %d sys ;", (int)ZF_SYSCALL_USER + NOP);
  zf_eval(&ctx, buf);
  std::string line;
  while (std::getline(std::cin, line)) {             // a definition to compile, or "T name" to time one run of it
    if (line.rfind("T ", 0) == 0) {
      const auto t0 = std::chrono::steady_clock::now();
      const int r = (int)zf_eval(&ctx, line.c_str() + 2);
      const auto t1 = std::chrono::steady_clock::now();
      std::printf("TIME %d %lld\n", r, (long long)std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count());
    } else std::printf("DEF %d\n", (int)zf_eval(&ctx, line.c_str()));
    std::fflush(stdout);
  }
  return 0;
}
'''.replace("NOP", str(NOP))

CASES = [  # (label, the call with its arguments and the drop of its results)
    ("loop alone (subtracted)", "2 drop"),
    ("nop-sys (trivial syscall)", "2 nop-sys drop"),
    ("sqrt", "2 sqrt drop"),
    ("atan2-rev", "1 2 atan2-rev drop"),
    ("floor", "2.7 floor drop"),
    ("exp", "1.5 exp drop"),
    ("pow", "2 0.5 pow drop"),
    ("fma", "2 3 4 fma drop"),
]


DEVICE_CALLS = 10000  # what the WF Native Tests APK runs (scripts/device_native_tests.py builds it in)
DEVICE_REPEATS = 31
DEVICE_RESULTS = ROOT / "build/device-native-tests"


def requests(calls: int, repeats: int) -> list[str]:
    """The host's whole input: per case, its definition, one warm-up run and `repeats` timed runs."""
    lines = []
    for i, (_, call) in enumerate(CASES):
        lines.append(f": bench{i} {calls} 0 do {call} loop ;")
        lines += [f"T bench{i}"] * (1 + repeats)
    return lines


def best_per_case(replies: list[str], repeats: int) -> dict:
    """The fastest timed run of each case, from the host's replies to `requests`; asserts every reply."""
    words = [r.split() for r in replies if r.strip()]
    per_case = 2 + repeats
    if len(words) != per_case * len(CASES):
        raise ValueError(f"expected {per_case * len(CASES)} replies ({len(CASES)} cases, {repeats} repeats), got {len(words)}")
    best = {}
    for i, (label, _) in enumerate(CASES):
        block = words[i * per_case:(i + 1) * per_case]
        if block[0] != ["DEF", "0"]:
            raise ValueError(f"{label}: definition failed: {block[0]}")
        runs = []
        for reply in block[1:]:
            if len(reply) != 3 or reply[0] != "TIME" or reply[1] != "0":
                raise ValueError(f"{label}: bad timed run: {reply}")
            runs.append(int(reply[2]))
        best[label] = min(runs[1:])                              # runs[0] is the warm-up
    return best


def table(best: dict, calls: int, repeats: int, where: str) -> str:
    base = best[CASES[0][0]]
    out = [f"{where}: {calls} calls per run, best of {repeats}, VM compiled -O2; loop overhead {base / calls:.1f} ns per iteration",
           f"{'word':28s} {'ns per call':>12s} {'vs nop-sys':>11s}"]
    nop = (best[CASES[1][0]] - base) / calls
    for label, _ in CASES[1:]:
        per = (best[label] - base) / calls
        out.append(f"{label:28s} {per:12.1f} {per / nop:10.2f}x")
    return "\n".join(out)


def run_local(calls: int, repeats: int) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="forth-math-cost-") as t:
        tmp = Path(t)
        vfm.build(tmp, host=HOST, opt=("-O2",))
        r = subprocess.run([str(tmp / "host"), str(tmp / "bootstrap.fth")], input="\n".join(requests(calls, repeats)) + "\n",
                           capture_output=True, text=True, check=True, timeout=600)
        return r.stdout.splitlines()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--calls", type=int, default=10000)
    ap.add_argument("--repeats", type=int, default=7)
    ap.add_argument("--device", help="read a device's collected replies instead of running here "
                                     f"(its run used --calls {DEVICE_CALLS} --repeats {DEVICE_REPEATS})")
    args = ap.parse_args()
    if args.device:
        path = DEVICE_RESULTS / args.device / "forth-math-vm-cost.txt"
        if not path.exists():
            print(f"{args.device}: NOT RUN: no collected result at {path.relative_to(ROOT)}; "
                  f"run `python3 scripts/device_native_tests.py run --device {args.device}`")
            return 1
        print(table(best_per_case(path.read_text().splitlines(), DEVICE_REPEATS), DEVICE_CALLS, DEVICE_REPEATS, args.device))
        return 0
    print(table(best_per_case(run_local(args.calls, args.repeats), args.repeats), args.calls, args.repeats, "pc"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
