#!/usr/bin/env python3
"""Run the generated lava lamp director in the real zForth VM and compare it with model.py.

No engine, no display: the VM from engine/vendor is compiled with a host that provides the mailbox words, property@,
deform-block (recorded, not applied) and the shipped Forth maths. Checks (docs/plans/2026-11-26-lava-lamp.md,
Verification 5 and 6):

  - trace: from the warmed state, 1,800 model steps (ll-step), every blob cell and phase against model.Lamp.step,
    within 1e-5 (the words do the same float32 operations in the same order, so the difference is normally 0);
  - frames: the DELTA_TIME accumulator (whole steps, at most four, a long frame's remainder dropped);
  - pose: the deform blocks, visibility, positions and scale of every wax mesh against model.pose, merges included;
  - settings: property@ answers change the wax tint and the four tint actors, and nothing is re-sent unchanged;
  - time: the starlight digits at 09:59, 10:00, 23:59 and 00:00, dashes before 2026-01-01, nothing with Time display Off;
  - the stacks stay balanced.

    python3 tests/verify_lava_lamp_forth.py            # also run by tests/test_lava_lamp.py
    python3 tests/verify_lava_lamp_forth.py --palette  # only the 64 colour pairings
"""
from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import level_modules  # noqa: E402
import verify_minute_machine_forth as mm  # noqa: E402  (the VM host and bootstrap builder; it imports Minute Machine's forth)

L, M, forth = level_modules.load("lava_lamp", "lamp", "model", "forth")

F = M.F

HOST = (mm.HOST
        .replace('static std::vector<W> writes;',
                 'static std::vector<W> writes;\nstatic std::map<std::pair<int,int>, float> props;\n'
                 'struct D { int block, n, kind, actor; };\nstatic std::vector<D> deforms;')
        .replace('  else if ((int)id >= 128 && wf::forthmath::HandleSyscall(c, (int)id - 128)) {}',
                 '''  else if ((int)id == 178) { int f = (int)zf_pop(c); int a = (int)zf_pop(c); auto it = props.find({a, f});
    zf_push(c, it == props.end() ? 0.0f : it->second); zf_push(c, it == props.end() ? 0.0f : 1.0f); }
  else if ((int)id == 184) { float dt = zf_pop(c); int n = (int)zf_pop(c); int stride = (int)zf_pop(c); int first = (int)zf_pop(c);
    std::vector<float> cells(n * stride); for (int i = 0; i < n * stride; i++) cells[i] = mbx.count(first + i) ? mbx[first + i] : 0.0f;
    wf::lava::Pairs(cells.data(), stride, n, dt); for (int i = 0; i < n * stride; i++) mbx[first + i] = cells[i]; }
  else if ((int)id == 182) { int a = (int)zf_pop(c); int k = (int)zf_pop(c); int n = (int)zf_pop(c); int b = (int)zf_pop(c);
    deforms.push_back({b, n, k, a}); zf_push(c, 0.0f); }
  else if ((int)id >= 128 && wf::forthmath::HandleSyscall(c, (int)id - 128)) {}''')
        .replace("else if (line[0] == 'T') {", '''else if (line[0] == 'R') { int i; sscanf(line + 2, "%d", &i); printf("V %d %.9g\\n", i, mbx.count(i) ? mbx[i] : 0.0f); fflush(stdout); }
    else if (line[0] == 'P') { int a, f; float v; sscanf(line + 2, "%d %d %f", &a, &f, &v); props[{a, f}] = v; }
    else if (line[0] == 'Q') { props.clear(); }
    else if (line[0] == 'E') { char w[64]; sscanf(line + 2, "%63s", w); writes.clear(); deforms.clear(); int r = eval(w);
      zf_cell d = 0, rs = 0; zf_uservar_get(&ctx, ZF_USERVAR_DSP, &d); zf_uservar_get(&ctx, ZF_USERVAR_RSP, &rs);
      printf("RESULT %d dsp %d rsp %d\\n", r, (int)d, (int)rs);
      for (auto& w : writes) printf("W %d %d %.9g\\n", w.actor, w.idx, w.val);
      for (auto& x : deforms) printf("D %d %d %d %d\\n", x.block, x.n, x.kind, x.actor);
      printf("END\\n"); fflush(stdout); if (r) { zf_abort(&ctx, ZF_OK); } }
    else if (line[0] == 'T') {'''))
HOST = HOST.replace('#include "forth_math_zforth.hpp"', '#include "forth_math_zforth.hpp"\n#include "lava_pairs.hpp"', 1)
assert "(int)id == 182" in HOST and "line[0] == 'E'" in HOST and "lava_pairs.hpp" in HOST

CONSTANTS = ["X_POS", "Z_POS", "ROTATION_B", "X_SCALE", "Y_SCALE", "Z_SCALE",
             "WALL_HOUR", "WALL_MINUTE", "WALL_SECOND", "WALL_DAY", "DELTA_TIME"]


class Lamp(mm.Host):
    def __init__(self, tmp: Path, ids, ix, fields):
        super().__init__(tmp, ids)
        self.ix, self.fields = ix, fields

    def put(self, cell: int, v) -> None:
        self.proc.stdin.write(f"M {cell} {float(v)!r}\n")

    def read(self, cell: int) -> float:
        self.proc.stdin.write(f"R {cell}\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline().split()
        assert line[0] == "V" and int(line[1]) == cell, line
        return float(line[2])

    def run(self, word: str):
        self.proc.stdin.write(f"E {word}\n")
        self.proc.stdin.flush()
        head = self.proc.stdout.readline().split()
        if not head or head[0] != "RESULT":
            raise RuntimeError(f"host: {head}")
        writes, deforms = {}, []
        while True:
            line = self.proc.stdout.readline().split()
            if line[0] == "END":
                break
            if line[0] == "W":
                writes[(int(line[1]), int(line[2]))] = float(line[3])
            else:
                deforms.append(tuple(int(v) for v in line[1:]))
        return (int(head[1]), int(head[3]), int(head[5])), writes, deforms

    def settings(self, values) -> None:
        self.proc.stdin.write("Q\n")
        if values is not None:
            for name, v in values.items():
                self.proc.stdin.write(f"P {self.ix['LavaLampSettings']} {self.fields[name]} {v}\n")

    def load_state(self, lamp: M.Lamp) -> None:
        for i, b in enumerate(lamp.blobs):
            for f in L.BLOB_FIELDS:
                self.put(forth.cell(i, f), b[f])
        self.put(L.P1, lamp.p1)
        self.put(L.P2, lamp.p2)
        self.put(L.P3, lamp.p3)

    def state(self, n: int):
        cells = {}
        for i in range(n):
            for f in L.BLOB_FIELDS:
                cells[(i, f)] = self.read(forth.cell(i, f))
        cells[("p", 1)], cells[("p", 2)], cells[("p", 3)] = self.read(L.P1), self.read(L.P2), self.read(L.P3)
        return cells


def ref_state(lamp: M.Lamp):
    cells = {(i, f): float(b[f]) for i, b in enumerate(lamp.blobs) for f in L.BLOB_FIELDS}
    cells[("p", 1)], cells[("p", 2)], cells[("p", 3)] = float(lamp.p1), float(lamp.p2), float(lamp.p3)
    return cells


def balanced(res, what, bad):
    if res != (0, 0, 0):
        bad.append(f"{what}: VM result {res[0]}, data stack {res[1]}, return stack {res[2]}")


def check_trace(host: Lamp, bad, steps=1800):
    lamp = M.warmed()
    host.load_state(lamp)
    worst, exact = 0.0, 0
    for s in range(steps):
        res, _w, _d = host.run("ll-step")
        balanced(res, f"step {s}", bad)
        lamp.step()
        if s % 60 == 59 or s == steps - 1:
            got, want = host.state(len(lamp.blobs)), ref_state(lamp)
            diff = max(abs(got[k] - want[k]) for k in want)
            exact += diff == 0
            worst = max(worst, diff)
            if diff > 1e-5:
                k = max(want, key=lambda k: abs(got[k] - want[k]))
                bad.append(f"trace step {s + 1}: {k} forth {got[k]!r} reference {want[k]!r}")
                break
    return worst, exact, lamp


def check_frames(host: Lamp, bad):
    """The accumulator: frames of 1/30 s run one step each, a 0.2 s frame runs four and drops the rest."""
    lamp = M.warmed()
    host.load_state(lamp)
    host.put(L.ACC, 0)
    acc = F(0)
    for delta in [M.DT] * 5 + [F(0.2), F(0.01), F(0.03), M.DT * F(2)]:
        host.put(host.ids["DELTA_TIME"], delta)
        res, _w, _d = host.run("ll-frame")
        balanced(res, "frame", bad)
        acc = lamp.frame(acc, delta)
        got, want = host.state(len(lamp.blobs)), ref_state(lamp)
        diff = max(abs(got[k] - want[k]) for k in want)
        if diff > 1e-5 or abs(host.read(L.ACC) - float(acc)) > 1e-7:
            bad.append(f"frame of {float(delta)} s: state differs by {diff}, accumulator {host.read(L.ACC)} vs {float(acc)}")
            return


def wax_of(lava: int, water: int):
    keep, mix = F(1 - L.WAX_WATER_MIX), F(L.WAX_WATER_MIX)
    lv, wt = L.rgb(L.LAVA[lava][1]), L.rgb(L.WATER[water][1])
    return tuple(F(lv[c]) * keep + F(wt[c]) * mix for c in range(3))


def check_pose(host: Lamp, lamp: M.Lamp, bad, wax):
    host.load_state(lamp)
    for k in range(3):
        host.put(L.WAX_RGB + k, wax[k])
    res, writes, deforms = host.run("ll-pose")
    balanced(res, "pose", bad)
    want = M.pose(lamp, wax)
    ix, ids = host.ix, host.ids
    worst = 0.0
    shown = 0

    def same(a, b, what, tol=1e-5):
        nonlocal worst
        d = abs(float(a) - float(b))
        worst = max(worst, d)
        if d > tol:
            bad.append(f"pose {what}: forth {float(a)!r} reference {float(b)!r}")

    for i, w in enumerate(want["blobs"]):
        same(host.read(L.VIS_BLOB0 + i), 0 if w is None else 1, f"Blob{i} visible")
        if w is None:
            continue
        shown += 1
        X, Z, sc, block = w
        same(writes[(ix[f"Blob{i}"], ids["X_POS"])], X, f"Blob{i} X")
        same(writes[(ix[f"Blob{i}"], ids["Z_POS"])], Z, f"Blob{i} Z")
        same(writes[(ix[f"Blob{i}"], ids["X_SCALE"])], sc, f"Blob{i} scale")
        for c, v in enumerate(block):
            same(host.read(L.BLOCK_BLOB0 + 10 * i + c), v, f"Blob{i} cell {c}")
        if (L.BLOCK_BLOB0 + 10 * i, 10, 7, ix[f"Blob{i}"]) not in deforms:
            bad.append(f"pose: no deform-block for Blob{i}")
    merges = 0
    for k, m in enumerate(want["merged"]):
        same(host.read(L.VIS_MERGED0 + k), 0 if m is None else 1, f"Merged{k} visible")
        if m is None:
            continue
        merges += 1
        X, Z, sc, roll, block = m
        a = ix[f"Merged{k}"]
        same(writes[(a, ids["X_POS"])], X, f"Merged{k} X")
        same(writes[(a, ids["Z_POS"])], Z, f"Merged{k} Z")
        same(writes[(a, ids["X_SCALE"])], sc, f"Merged{k} scale")
        same(writes[(a, ids["ROTATION_B"])], roll, f"Merged{k} roll")
        for c, v in enumerate(block):
            same(host.read(L.BLOCK_MERGED0 + 10 * k + c), v, f"Merged{k} cell {c}")
    for c, v in enumerate(want["pool"]):
        same(host.read(L.BLOCK_POOL + c), v, f"Pool cell {c}")
    return worst, shown, merges


def check_settings(host: Lamp, bad):
    host.put(L.BLOB0 + 9, 1)          # skip ll-start
    host.put(L.SET_INIT, 0)
    tints = [(L.BLOCK_TINT0 + 10 * k, 10, 7, host.ix[n]) for k, n in enumerate(L.TINTED)]
    cases = [(None, L.DEFAULT_LAVA, L.DEFAULT_WATER)]
    cases += [({"Lava color": lava, "Water color": water}, lava, water) for lava in range(8) for water in range(8)
              if (lava, water) != (L.DEFAULT_LAVA, L.DEFAULT_WATER)]
    for values, lava, water in cases:
        host.settings(values)
        res, _w, deforms = host.run("ll-settings")
        balanced(res, f"settings {values}", bad)
        if [d for d in deforms if d in tints] != tints:
            bad.append(f"settings {values}: the tint actors were not all re-sent: {deforms}")
        wax = wax_of(lava, water)
        for c in range(3):
            if abs(host.read(L.WAX_RGB + c) - float(wax[c])) > 1e-6:
                bad.append(f"settings {values}: wax channel {c} {host.read(L.WAX_RGB + c)} vs {float(wax[c])}")
        liquid = L.rgb(L.WATER[water][1])
        for c in range(3):
            if abs(host.read(L.BLOCK_TINT0 + 6 + c) - liquid[c]) > 1e-6:
                bad.append(f"settings {values}: liquid channel {c}")
        for k in range(len(L.TINTED)):               # every tint cell a colour the deformer can take
            for c in range(10):
                v = host.read(L.BLOCK_TINT0 + 10 * k + c)
                if not (math.isfinite(v) and 0 <= v <= 1.5):
                    bad.append(f"settings {values}: {L.TINTED[k]} cell {c} = {v}")
        res, _w, deforms = host.run("ll-settings")       # unchanged: nothing re-sent
        if deforms:
            bad.append(f"settings {values}: unchanged settings re-sent {deforms}")
    return len(cases)


def check_time(host: Lamp, bad):
    def digits_shown():
        out = []
        for p in range(4):
            on = [v for v in range(10) if host.read(L.VIS_DIGIT0 + 10 * p + v) == 1]
            out.append(on)
        return out, host.read(L.VIS_COLON), host.read(L.VIS_DASH)

    cases = [(9876, 9, 59, 0, ([[0], [9], [5], [9]], 1, 0)), (9876, 10, 0, 0, ([[1], [0], [0], [0]], 1, 0)),
             (9876, 23, 59, 0, ([[2], [3], [5], [9]], 1, 0)), (9877, 0, 0, 0, ([[0], [0], [0], [0]], 1, 0)),
             (5, 0, 0, 0, ([[], [], [], []], 0, 1)), (9876, 21, 47, 1, ([[], [], [], []], 0, 0))]
    for day, h, m, off, want in cases:
        host.put(host.ids["WALL_DAY"], day)
        host.put(host.ids["WALL_HOUR"], h)
        host.put(host.ids["WALL_MINUTE"], m)
        host.put(L.SET_TIME, off)
        res, _w, _d = host.run("ll-time")
        balanced(res, f"time {h}:{m}", bad)
        got = digits_shown()
        if got != want:
            bad.append(f"time day {day} {h:02d}:{m:02d} off {off}: shown {got}, want {want}")


def main() -> int:
    bad: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lava-forth-") as t:
        tmp = Path(t)
        mm.CONSTANTS[:] = CONSTANTS
        mm.HOST = HOST
        ix, fields = forth.default_indices(), forth.default_fields()

        class Gen:                                   # mm.build writes forth.definitions(forth.default_indices())
            @staticmethod
            def default_indices():
                return ix

            @staticmethod
            def definitions(_ix):
                return forth.definitions(ix, fields)
        src, mm.forth = mm.forth, Gen
        try:
            ids, _ = mm.build(tmp)
        finally:
            mm.forth = src
        with open(tmp / "bootstrap.fth", "a") as f:
            # the engine registers these after its bootstrap (scripting_zforth.cc Init)
            f.write(": property@ 178 sys ; : deform-block 182 sys ; : lava-pairs 184 sys ;\n: r@ ' lit , 0 , ' pickr , ; immediate\n")
        host = Lamp(tmp, ids, ix, fields)
        if "--palette" not in sys.argv:
            worst, exact, lamp = check_trace(host, bad)
            print(f"trace: 1800 steps, worst difference {worst:.3g} ({exact} of 30 checkpoints exact)")
            check_frames(host, bad)
            pose_worst, shown, merges = 0.0, 0, 0
            probe = M.warmed()
            for s in range(40):
                for _ in range(45):
                    probe.step()
                w, sh, mg = check_pose(host, probe, bad, wax_of(L.DEFAULT_LAVA, L.DEFAULT_WATER))
                pose_worst, shown, merges = max(pose_worst, w), shown + sh, merges + mg
            print(f"pose: 40 frames, {shown} blob poses, {merges} merged poses, worst difference {pose_worst:.3g}")
            check_time(host, bad)
        n = check_settings(host, bad)
        print(f"settings: {n} colour pairings applied (all 64), each tint actor re-sent once")
        host.close()
    for b in bad[:30]:
        print("FAIL", b)
    print("PASS" if not bad else f"FAIL: {len(bad)} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
