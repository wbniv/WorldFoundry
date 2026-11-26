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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--calls", type=int, default=10000)
    ap.add_argument("--repeats", type=int, default=7)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="forth-math-cost-") as t:
        tmp = Path(t)
        vfm.build(tmp, host=HOST, opt=("-O2",))
        proc = subprocess.Popen([str(tmp / "host"), str(tmp / "bootstrap.fth")], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True)

        def say(line: str) -> list:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            return proc.stdout.readline().split()

        best = {}
        for i, (label, call) in enumerate(CASES):
            reply = say(f": bench{i} {args.calls} 0 do {call} loop ;")
            assert reply == ["DEF", "0"], (label, reply)
            say(f"T bench{i}")                                   # warm up
            runs = []
            for _ in range(args.repeats):
                tag, rc, ns = say(f"T bench{i}")
                assert tag == "TIME" and rc == "0", (label, tag, rc)
                runs.append(int(ns))
            best[label] = min(runs)
        proc.stdin.close()
        proc.wait(timeout=10)
    base = best[CASES[0][0]]
    print(f"{args.calls} calls per run, best of {args.repeats}, VM compiled -O2; loop overhead {base / args.calls:.1f} ns per iteration")
    print(f"{'word':28s} {'ns per call':>12s} {'vs nop-sys':>11s}")
    nop = (best[CASES[1][0]] - base) / args.calls
    for label, _ in CASES[1:]:
        per = (best[label] - base) / args.calls
        print(f"{label:28s} {per:12.1f} {per / nop:10.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
