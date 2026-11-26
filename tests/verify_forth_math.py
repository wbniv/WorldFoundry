#!/usr/bin/env python3
"""Every Forth math word, run in the real zForth VM.

    python3 tests/verify_forth_math.py        # also run by tests/test_forth_math_vm.py

Plans: docs/plans/2026-11-21-forth-trig-words.md, Verification 2, and docs/plans/2026-11-26-forth-math-words.md,
Verification 2 (its 27 words). The VM and the bootstrap are the
engine's own; the host registers the words from the shared table in engine/stubs/forth_math_zforth.hpp
and dispatches through the same HandleSyscall the bridge calls, so what runs here is the shipped glue.
It checks each word's value and stack effect, that a domain error aborts with the VM's external-abort
code and a named message and leaves the VM usable, and that 10 000 calls grow neither the dictionary
nor the stacks.
"""
from __future__ import annotations

import ast
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HOST = r'''
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#include "forth_math_zforth.hpp"
static zf_ctx ctx;
extern "C" zf_input_state zf_host_sys(zf_ctx* c, zf_syscall_id id, const char*) {
  if (id == ZF_SYSCALL_EMIT) zf_pop(c);
  else if (id == ZF_SYSCALL_TELL) { zf_pop(c); zf_pop(c); }
  else if ((int)id >= (int)ZF_SYSCALL_USER && wf::forthmath::HandleSyscall(c, (int)id - (int)ZF_SYSCALL_USER)) {}
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
static void report(int r) {
  zf_cell dsp = 0, rsp = 0, here = 0;
  zf_uservar_get(&ctx, ZF_USERVAR_DSP, &dsp); zf_uservar_get(&ctx, ZF_USERVAR_RSP, &rsp); zf_uservar_get(&ctx, ZF_USERVAR_HERE, &here);
  int n = (int)dsp; std::vector<float> st;
  for (int i = 0; i < n; i++) st.push_back(zf_pop(&ctx));
  std::printf("RESULT %d dsp %d rsp %d here %d :", r, n, (int)rsp, (int)here);
  for (int i = (int)st.size() - 1; i >= 0; i--) std::printf(" %.9g", st[i]);
  std::printf("\nEND\n"); std::fflush(stdout); std::fflush(stderr);
}
int main(int argc, char** argv) {
  zf_init(&ctx, 0); zf_bootstrap(&ctx);
  int r = (int)zf_eval(&ctx, slurp(argv[1]).c_str());
  if (r) { std::printf("LOADERR %d\n", r); return 1; }
  for (const auto& w : wf::forthmath::kWords) {            // as scripting_zforth.cc registers them
    char buf[64]; std::snprintf(buf, sizeof buf, ": %s %d sys ;", w.name, (int)ZF_SYSCALL_USER + w.custom);
    if ((int)zf_eval(&ctx, buf)) { std::printf("REGERR %s\n", w.name); return 1; }
  }
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.rfind("E ", 0) == 0) report((int)zf_eval(&ctx, line.c_str() + 2));
    else if (line.rfind("N ", 0) == 0) {                     // N <count> <forth>: run it count times
      int count = std::atoi(line.c_str() + 2); size_t sp = line.find(' ', 2);
      int rr = 0; for (int i = 0; i < count && !rr; i++) rr = (int)zf_eval(&ctx, line.c_str() + sp + 1);
      report(rr);
    }
  }
}
'''


def bootstrap() -> str:
    """The engine's core bootstrap and the vendor string words, as the hosts load them (bootstrap.fth)."""
    src = (ROOT / "engine/stubs/scripting_zforth.cc").read_text()
    core = src[src.index("static const char* kCoreBootstrap ="):src.index("void Init(")]
    core = re.sub(r"//[^\n]*", "", core)
    text = "".join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"', core))
    vendor = (ROOT / "engine/vendor/zforth-41db72d1/forth/core.zf").read_text()
    strings = vendor[vendor.index(': s"'):vendor.index("\n\n\n(", vendor.index(': ."'))]
    return text + "\n: emit 0 sys ; : tell 2 sys ;\n" + strings + "\n"


def build(tmp: Path, host: str = HOST, opt: tuple = ()):
    """Compile the VM and a host (this file's, or tests/forth_math_vm_cost.py's) into tmp/host."""
    (tmp / "bootstrap.fth").write_text(bootstrap())
    (tmp / "host.cc").write_text(host)
    inc = ["-I" + str(ROOT / "engine/stubs"), "-I" + str(ROOT / "engine/vendor/zforth-41db72d1/src/zforth")]
    subprocess.run(["cc", *opt, *inc, "-c", str(ROOT / "engine/vendor/zforth-41db72d1/src/zforth/zforth.c"), "-o", str(tmp / "vm.o")], check=True)
    subprocess.run(["c++", "-std=c++17", "-Wall", *opt, *inc, str(tmp / "host.cc"), str(tmp / "vm.o"), "-o", str(tmp / "host")], check=True)


class Host:
    def __init__(self, tmp: Path):
        self.err = open(tmp / "stderr.txt", "w+")
        self.proc = subprocess.Popen([str(tmp / "host"), str(tmp / "bootstrap.fth")], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.err, text=True)
        self.err_pos = 0

    def run(self, line: str, prefix: str = "E "):
        self.proc.stdin.write(prefix + line + "\n")
        self.proc.stdin.flush()
        head = self.proc.stdout.readline()
        assert head.startswith("RESULT"), head
        self.proc.stdout.readline()                               # END
        left, _, values = head.partition(" :")
        f = left.split()
        self.err.flush()
        self.err.seek(self.err_pos)
        message = self.err.read()
        self.err_pos = self.err.tell()
        return {"rc": int(f[1]), "dsp": int(f[3]), "rsp": int(f[5]), "here": int(f[7]),
                "stack": [float(v) for v in values.split()], "err": message}

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


EXTERNAL = 12     # ZF_ABORT_EXTERNAL
failures = []
checks = 0


def check(ok: bool, what: str):
    global checks
    checks += 1
    if not ok:
        failures.append(what)
        print("FAIL", what)


def close(a: float, b: float, tol: float = 2e-6) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(b))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="forth-math-") as t:
        tmp = Path(t)
        build(tmp)
        h = Host(tmp)
        tau = 2 * math.pi
        cases = [  # (forth, expected stack bottom to top)
            ("0.25 sin-rev", [1.0]), ("0.125 sin-rev", [math.sin(tau * 0.125)]), ("0 sin-rev", [0.0]),
            ("0.5 cos-rev", [-1.0]), ("0.125 cos-rev", [math.cos(tau * 0.125)]), ("-0.3 cos-rev", [math.cos(tau * 0.7)]),
            ("0.1 tan-rev", [math.tan(tau * 0.1)]), ("0.125 tan-rev", [1.0]),
            ("0.5 asin-rev", [1 / 12]), ("1 asin-rev", [0.25]), ("-1 asin-rev", [-0.25]),
            ("0.5 acos-rev", [1 / 6]), ("-1 acos-rev", [0.5]), ("1 acos-rev", [0.0]),
            ("1 atan-rev", [0.125]), ("-1 atan-rev", [-0.125]),
            ("1 1 atan2-rev", [0.125]), ("1 0 atan2-rev", [0.25]), ("0 -1 atan2-rev", [0.5]), ("-1 0 atan2-rev", [-0.25]),
            ("0 0 atan2-rev", [0.0]),
            ("0.125 sincos-rev", [math.sin(tau * 0.125), math.cos(tau * 0.125)]),
            ("0.25 sincos-rev", [1.0, 0.0]),
            ("2 sqrt", [math.sqrt(2)]), ("0 sqrt", [0.0]), ("144 sqrt", [12.0]),
            ("1.0000001 asin-rev", [0.25]),                          # 1e-7 over: clamped
            (": f 0.3 cos-rev 0.3 sin-rev + ; f", [math.cos(tau * 0.3) + math.sin(tau * 0.3)]),
            (": g 0.2 0 > if 0.25 sin-rev else 0 then ; g", [1.0]),
            # the second plan's words: A, exact
            ("2.7 floor", [2.0]), ("-2.7 floor", [-3.0]), ("2.2 ceil", [3.0]), ("-2.7 trunc", [-2.0]),
            ("2.5 round", [3.0]), ("-2.5 round", [-3.0]), ("2.5 roundeven", [2.0]), ("3.5 roundeven", [4.0]),
            ("2 3 4 fma", [10.0]), ("3 -0.5 copysign", [-3.0]), ("-3 2 copysign", [3.0]),
            ("7 3 fmod", [1.0]), ("-7 3 fmod", [-1.0]), ("370.5 360 fmod", [10.5]),
            # B, integer bits
            ("255 popcount", [8.0]), ("16777215 popcount", [24.0]), ("0 clz", [32.0]), ("1 clz", [31.0]),
            ("16777216 clz", [7.0]), ("0 ctz", [32.0]), ("40 ctz", [3.0]), ("1024 31 swap clz -", [10.0]),
            # C, libm
            ("1 exp", [math.e]), ("0 exp", [1.0]), ("1e-7 expm1", [math.expm1(1e-7)]), ("10 exp2", [1024.0]),
            ("2 0.5 pow", [math.sqrt(2)]), ("-2 3 pow", [-8.0]), ("2.718281828 ln", [1.0]), ("1e-7 log1p", [math.log1p(1e-7)]),
            ("1024 log2", [10.0]), ("1000 log10", [3.0]), ("-27 cbrt", [-3.0]), ("3 4 hypot", [5.0]),
            ("1 sinh", [math.sinh(1)]), ("1 cosh", [math.cosh(1)]), ("0.5 tanh", [math.tanh(0.5)]),
            ("1 asinh", [math.asinh(1)]), ("2 acosh", [math.acosh(2)]), ("0.5 atanh", [math.atanh(0.5)]),
            (": lerp ( a b t -- x ) >r over - r> swap rot fma ; 2 6 0.25 lerp", [3.0]),
        ]
        for forth, want in cases:
            r = h.run(forth)
            ok = r["rc"] == 0 and r["dsp"] == len(want) and r["rsp"] == 0 and len(r["stack"]) == len(want) and \
                all(close(g, w) for g, w in zip(r["stack"], want))
            if r["rc"] == 0 and forth.startswith("0.125 tan-rev"):
                ok = ok and close(r["stack"][0], math.tan(tau * 0.125))
            check(ok, f"{forth}: {r}")

        # the tangent's poles: huge, finite, not an error (decision D3)
        r = h.run("0.25 tan-rev")
        check(r["rc"] == 0 and r["dsp"] == 1 and abs(r["stack"][0]) > 1e10, f"tan-rev at a pole: {r}")

        # domain errors: the VM's external-abort code, a message naming the word, and a usable VM afterwards
        for forth, word, why in [("2 asin-rev", "asin-rev", "outside -1 to 1"), ("-1.5 acos-rev", "acos-rev", "outside -1 to 1"),
                                 ("1.00001 asin-rev", "asin-rev", "outside -1 to 1"), ("-1 sqrt", "sqrt", "negative"),
                                 ("0.5 1 2 asin-rev", "asin-rev", "outside -1 to 1"),
                                 ("1 0 fmod", "fmod", "divisor is zero"), ("-1 popcount", "popcount", "not a whole number"),
                                 ("0.5 clz", "clz", "not a whole number"), ("16777218 ctz", "ctz", "not a whole number"),
                                 ("89 exp", "exp", "result is not a finite number"), ("128 exp2", "exp2", "result is not a finite number"),
                                 ("-8 0.5 pow", "pow", "negative base"), ("0 -1 pow", "pow", "zero to a negative power"),
                                 ("10 39 pow", "pow", "result is not a finite number"), ("0 ln", "ln", "zero or negative"),
                                 ("-1 log1p", "log1p", "-1 or less"), ("-1 log2", "log2", "zero or negative"),
                                 ("0 log10", "log10", "zero or negative"), ("0.5 acosh", "acosh", "less than 1"),
                                 ("1 atanh", "atanh", "1 or more"), ("1e30 cosh", "cosh", "result is not a finite number"),
                                 ("3e38 10 0 fma", "fma", "result is not a finite number"), ("3e38 3e38 hypot", "hypot", "result is not a finite number"),
                                 ("5 1 0 fmod", "fmod", "divisor is zero")]:
            r = h.run(forth)
            check(r["rc"] == EXTERNAL and word in r["err"] and why in r["err"] and r["dsp"] == 0 and r["rsp"] == 0,
                  f"{forth} should abort naming {word}: {r}")
            r2 = h.run("0.25 sin-rev")
            check(r2["rc"] == 0 and r2["dsp"] == 1 and close(r2["stack"][0], 1.0), f"VM unusable after {forth}: {r2}")

        # 10 000 calls of every word grow neither the dictionary nor the stacks
        before = h.run(": stable 0.3 cos-rev drop ; stable")["here"]
        for word_call in ["0.3 cos-rev drop", "0.3 sin-rev drop", "0.3 tan-rev drop", "0.3 asin-rev drop", "0.3 acos-rev drop",
                          "0.3 atan-rev drop", "1 2 atan2-rev drop", "0.3 sincos-rev drop drop", "2 sqrt drop",
                          "2.7 floor drop", "2.2 ceil drop", "-2.7 trunc drop", "2.5 round drop", "2.5 roundeven drop",
                          "2 3 4 fma drop", "3 -1 copysign drop", "7 3 fmod drop", "255 popcount drop", "255 clz drop",
                          "40 ctz drop", "1 exp drop", "0.1 expm1 drop", "3 exp2 drop", "2 0.5 pow drop", "2 ln drop",
                          "0.1 log1p drop", "8 log2 drop", "100 log10 drop", "27 cbrt drop", "3 4 hypot drop", "1 sinh drop",
                          "1 cosh drop", "0.5 tanh drop", "1 asinh drop", "2 acosh drop", "0.5 atanh drop"]:
            r = h.run(f"10000 {word_call}", prefix="N ")
            check(r["rc"] == 0 and r["dsp"] == 0 and r["rsp"] == 0 and r["here"] == before, f"10000 x {word_call}: {r}")
        h.close()
    header = (ROOT / "engine/stubs/forth_math_zforth.hpp").read_text()
    words = len(re.findall(r'\{"[^"]+",\s*\d+,\s*"', header[header.index("constexpr WordInfo kWords[]"):header.index("constexpr int kFirstCustom")]))
    print(f"{checks} checks across {words} words in the real zForth VM:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
