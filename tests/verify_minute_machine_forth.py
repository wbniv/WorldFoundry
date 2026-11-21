#!/usr/bin/env python3
"""Run the generated Minute Machine director in the real zForth VM and compare it with timeline.py.

No engine, no display: the VM from engine/vendor is compiled with a host that provides the three
mailbox words. Each case sets WALL_HOUR, WALL_MINUTE and WALL_SECOND, runs one frame (mm-tick) and
checks every actor write against timeline.all_poses. Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md.

    python3 tests/verify_minute_machine_forth.py            # also run by tests/test_minute_machine_forth.py
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
sys.path.insert(0, str(ROOT / "wflevels" / "minute_machine"))
import forth  # noqa: E402
import timeline as tl  # noqa: E402

HOST = r'''
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "zforth.h"
static zf_ctx ctx;
static std::map<int, float> mbx;
struct W { int actor, idx; float val; };
static std::vector<W> writes;
extern "C" zf_input_state zf_host_sys(zf_ctx*c, zf_syscall_id id, const char*) {
  if (id == ZF_SYSCALL_EMIT) zf_pop(c);
  else if (id == ZF_SYSCALL_TELL) { zf_pop(c); zf_pop(c); }
  else if ((int)id == 128) { int i = (int)zf_pop(c); zf_push(c, mbx.count(i) ? mbx[i] : 0.0f); }
  else if ((int)id == 129) { int i = (int)zf_pop(c); float v = zf_pop(c); mbx[i] = v; }
  else if ((int)id == 201) { double t = (double)zf_pop(c); t -= floor(t); zf_push(c, (zf_cell)sin(6.283185307179586 * t)); }
  else if ((int)id == 130) { int a = (int)zf_pop(c); int i = (int)zf_pop(c); float v = zf_pop(c); writes.push_back({a, i, v}); }
  else { fprintf(stderr, "unexpected syscall %d\n", (int)id); std::abort(); }
  return ZF_INPUT_INTERPRET;
}
extern "C" void zf_host_trace(zf_ctx*, const char*, va_list) {}
extern "C" zf_cell zf_host_parse_num(zf_ctx* c, const char* s) {
  char* e; float n = strtof(s, &e);
  if (*e) { fprintf(stderr, "Unknown: %s\n", s); zf_abort(c, ZF_ABORT_NOT_A_WORD); }
  return n;
}
static std::string slurp(const char* path) {
  FILE* f = fopen(path, "r"); std::string s; char buf[4096]; size_t n;
  while ((n = fread(buf, 1, sizeof buf, f)) > 0) s.append(buf, n);
  fclose(f); return s;
}
static int eval(const std::string& s) { return (int)zf_eval(&ctx, s.c_str()); }
int main(int argc, char** argv) {
  zf_init(&ctx, 0); zf_bootstrap(&ctx);
  for (int i = 1; i < argc; i++) { int r = eval(slurp(argv[i])); if (r) { printf("LOADERR %s %d\n", argv[i], r); return 1; } }
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    if (line[0] == 'M') { int i; float v; sscanf(line + 2, "%d %f", &i, &v); mbx[i] = v; }
    else if (line[0] == 'T') {
      writes.clear();
      int r = eval("mm-tick");
      zf_cell d = 0, rs = 0; zf_uservar_get(&ctx, ZF_USERVAR_DSP, &d); zf_uservar_get(&ctx, ZF_USERVAR_RSP, &rs);
      printf("RESULT %d dsp %d rsp %d\n", r, (int)d, (int)rs);
      for (auto& w : writes) printf("W %d %d %.9g\n", w.actor, w.idx, w.val);
      printf("END\n"); fflush(stdout);
      if (r) { zf_abort(&ctx, ZF_OK); }
    }
  }
}
'''

CONSTANTS = ["X_POS", "Y_POS", "Z_POS", "ROTATION_A", "ROTATION_B", "ROTATION_C", "X_SCALE", "Y_SCALE", "Z_SCALE",
             "WALL_HOUR", "WALL_MINUTE", "WALL_SECOND"]


def mailbox_ids():
    text = (ROOT / "wfsource/source/mailbox/mailbox.inc").read_text()
    ids = {}
    for name, value in re.findall(r"MAILBOXENTRY\(\s*([A-Z0-9_]+)\s*,\s*(\d+)\s*\)", text):
        ids[name] = int(value)
    return ids


def build(tmp: Path):
    src = (ROOT / "engine/stubs/scripting_zforth.cc").read_text()
    core = src[src.index("static const char* kCoreBootstrap ="):src.index("void Init(")]
    core = re.sub(r"//[^\n]*", "", core)
    bootstrap = "".join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"', core))
    vendor = (ROOT / "engine/vendor/zforth-41db72d1/forth/core.zf").read_text()
    strings = vendor[vendor.index(': s"'):vendor.index("\n\n\n(", vendor.index(': ."'))]
    ids = mailbox_ids()
    consts = "\n".join(f"{ids[n]} constant INDEXOF_{n}" for n in CONSTANTS)
    (tmp / "bootstrap.fth").write_text(bootstrap + "\n: emit 0 sys ; : tell 2 sys ;\n" + strings +
                                       "\n: read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ; : sin-rev 201 sys ;\n" + consts + "\n")
    ix = forth.default_indices()
    (tmp / "director.fth").write_text(forth.definitions(ix))
    (tmp / "host.cc").write_text(HOST)
    inc = ["-I" + str(ROOT / "engine/stubs"), "-I" + str(ROOT / "engine/vendor/zforth-41db72d1/src/zforth")]
    subprocess.run(["cc", *inc, "-c", str(ROOT / "engine/vendor/zforth-41db72d1/src/zforth/zforth.c"), "-o", str(tmp / "vm.o")], check=True)
    subprocess.run(["c++", "-std=c++17", *inc, str(tmp / "host.cc"), str(tmp / "vm.o"), "-o", str(tmp / "host")], check=True)
    return ids, ix


class Host:
    def __init__(self, tmp: Path, ids):
        self.ids = ids
        self.proc = subprocess.Popen([str(tmp / "host"), str(tmp / "bootstrap.fth"), str(tmp / "director.fth")],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def frame(self, sod: float):
        h, m = int(sod // 3600) % 24, int(sod // 60) % 60
        sec = sod % 60.0
        # the engine's float32 mailbox, never rounding up to 60
        for name, v in (("WALL_HOUR", h), ("WALL_MINUTE", m), ("WALL_SECOND", sec)):
            self.proc.stdin.write(f"M {self.ids[name]} {v!r}\n")
        self.proc.stdin.write("T\n")
        self.proc.stdin.flush()
        head = self.proc.stdout.readline().split()
        if not head or head[0] != "RESULT":
            raise RuntimeError(f"host: {head}")
        writes = {}
        while True:
            line = self.proc.stdout.readline().split()
            if line[0] == "END":
                break
            writes[(int(line[1]), int(line[2]))] = float(line[3])
        return int(head[1]), int(head[3]), int(head[5]), writes

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def compare(host: Host, ix, ids, times, verbose=False):
    fields = [("X_POS", 0), ("Y_POS", 1), ("Z_POS", 2), ("ROTATION_A", 3), ("ROTATION_B", 4), ("ROTATION_C", 5),
              ("X_SCALE", 6), ("Y_SCALE", 7), ("Z_SCALE", 8)]
    worst = {"pos": 0.0, "rot": 0.0, "scale": 0.0}
    bad = []
    for sod in times:
        r, dsp, rsp, writes = host.frame(sod)
        if r != 0 or dsp != 0 or rsp != 0:
            bad.append(f"{sod}: VM result {r}, data stack {dsp}, return stack {rsp}")
            continue
        poses = tl.all_poses(sod)
        for name, pose in poses.items():
            for fname, k in fields:
                key = (ix[forth.ACTOR_OF.get(name, name)], ids[fname])
                if key not in writes:
                    continue                     # a piece's static channels are placed by the level, not the director
                want, got = pose[k], writes[key]
                if fname.startswith("ROTATION"):
                    d, kind, lim = abs((got - want + .5) % 1.0 - .5), "rot", .5 / 360
                elif fname.endswith("SCALE"):
                    d, kind, lim = abs(got - want), "scale", 1e-3 * max(1.0, abs(want)) + 2e-4
                else:
                    d, kind, lim = abs(got - want), "pos", 1e-3
                worst[kind] = max(worst[kind], d)
                if d > lim:
                    bad.append(f"{sod:.3f} {name}.{fname}: forth {got:.6f} reference {want:.6f}")
    return worst, bad


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mm-forth-") as t:
        tmp = Path(t)
        ids, ix = build(tmp)
        host = Host(tmp, ids)
        times = [tl.__dict__["m"](0) * 0 + s for s in ()]  # placeholder, replaced below
        times = []
        for base in (10 * 3600 + 8 * 60, 12 * 3600 + 59 * 60, 13 * 3600, 23 * 3600 + 59 * 60, 0.0):
            times += [base + s for s in (0.0, 0.1, 0.35, 0.7, 1.2, 2.2, 5.0, 12.3, 15.5, 19.9, 20.5, 21.5, 22.5, 30.0, 41.5,
                                         47.0, 50.5, 52.2, 54.0, 55.1, 56.5, 57.5, 58.4, 59.2, 59.99)]
        worst, bad = compare(host, ix, ids, times)
        host.close()
    print(f"{len(times)} frames; worst position {worst['pos']*1000:.4f} mm, rotation {worst['rot']*360:.4f} deg, scale {worst['scale']:.6f}")
    for b in bad[:30]:
        print("FAIL", b)
    print("PASS" if not bad else f"FAIL: {len(bad)} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
