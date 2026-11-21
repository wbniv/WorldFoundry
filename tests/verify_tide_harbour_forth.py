#!/usr/bin/env python3
"""Run the generated Tide Harbour director in the real zForth VM and compare it with timeline.py.

No engine, no display: the VM from engine/vendor is compiled with a host that provides the mailbox
words and the shipped Forth maths. Each case sets WALL_DAY, WALL_HOUR, WALL_MINUTE, WALL_SECOND and
the settings cells, runs one frame (th-tick) and checks:

  - every actor write (position, rotation, scale) against timeline.scene's poses;
  - every colour write (FACE_COLOR_TOP + slot, packed 0xRRGGBB) against its colours, within one step
    per channel (float32 against double rounding at a .5 boundary);
  - the visibility cells 700-706, and the tide cell against the Python sum (within 1 cm, plan
    Verification 10);
  - that the stacks are balanced.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (Verification 1, 10 and 13).

    python3 tests/verify_tide_harbour_forth.py          # also run by tests/test_tide_harbour_forth.py
"""
from __future__ import annotations

import datetime as dt
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))
sys.path.insert(0, str(ROOT / "tests"))
import forth  # noqa: E402
import timeline as tl  # noqa: E402
import verify_minute_machine_forth as mm  # noqa: E402  (its VM host and bootstrap builder)

HOST = mm.HOST.replace('else if (line[0] == \'T\') {', '''else if (line[0] == 'R') { int i; sscanf(line + 2, "%d", &i); printf("V %d %.9g\\n", i, mbx.count(i) ? mbx[i] : 0.0f); fflush(stdout); }
    else if (line[0] == 'T') {''').replace('eval("mm-tick")', 'eval("th-tick")')
assert HOST.count("th-tick") == 1 and "line[0] == 'R'" in HOST

CONSTANTS = ["X_POS", "Y_POS", "Z_POS", "ROTATION_A", "ROTATION_B", "ROTATION_C", "X_SCALE", "Y_SCALE", "Z_SCALE",
             "FACE_COLOR_TOP", "WALL_HOUR", "WALL_MINUTE", "WALL_SECOND", "WALL_DAY"]
FIELDS = [("X_POS", 0), ("Y_POS", 1), ("Z_POS", 2), ("ROTATION_A", 3), ("ROTATION_B", 4), ("ROTATION_C", 5),
          ("X_SCALE", 6), ("Y_SCALE", 7), ("Z_SCALE", 8)]
TIDE_CELL = 600 + forth.CELLS.index("tide")
WRAP = {**{f"cloud_{i}": tl.CLOUD_SPAN for i in range(len(tl.CLOUDS))}, **{f"bird_{i}": tl.BIRD_SPAN for i in range(len(tl.BIRDS))},
        "boat_3": tl.FERRY_SPAN}


def build(tmp: Path):
    mm.CONSTANTS[:] = CONSTANTS
    mm.HOST = HOST
    src_forth, mm.forth = mm.forth, forth                 # mm.build writes forth.definitions(forth.default_indices())
    try:
        ids, ix = mm.build(tmp)
    finally:
        mm.forth = src_forth
    return ids, ix


class Host(mm.Host):
    def frame_at(self, day: int, sod: float, options=None, reset_look=True):
        h, m = int(sod // 3600) % 24, int(sod // 60) % 60
        sec = sod % 60.0
        lines = [("WALL_DAY", day), ("WALL_HOUR", h), ("WALL_MINUTE", m), ("WALL_SECOND", sec)]
        for name, v in lines:
            self.proc.stdin.write(f"M {self.ids[name]} {v!r}\n")
        for name, cell in tl.OPTION_CELLS.items():
            self.proc.stdin.write(f"M {cell} {(options or {}).get(name, 0)}\n")
        if reset_look:
            self.proc.stdin.write(f"M {forth.PREVQ} 0\n")      # force the re-colour pass so every colour is checked
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

    def read(self, cell: int) -> float:
        self.proc.stdin.write(f"R {cell}\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline().split()
        assert line[0] == "V" and int(line[1]) == cell, line
        return float(line[2])


def compare(host: Host, ix, ids, cases):
    worst = {"pos": 0.0, "rot": 0.0, "scale": 0.0, "colour": 0, "tide": 0.0}
    bad = []
    colour_box = ids["FACE_COLOR_TOP"]
    for day, sod, options in cases:
        r, dsp, rsp, writes = host.frame_at(day, sod, options)
        label = f"{tl.date_of(day)} {sod:.2f} {options or ''}"
        if r != 0 or dsp != 0 or rsp != 0:
            bad.append(f"{label}: VM result {r}, data stack {dsp}, return stack {rsp}")
            continue
        sc = tl.scene(day, sod, options)
        for name, pose in sc.poses.items():
            for fname, k in FIELDS:
                key = (ix[name], ids[fname])
                if key not in writes:
                    continue                      # placed by the level, not the director
                want, got = pose[k], writes[key]
                if fname.startswith("ROTATION"):
                    d, kind, lim = abs((got - want + .5) % 1.0 - .5), "rot", .5 / 360
                elif fname.endswith("SCALE"):
                    d, kind, lim = abs(got - want), "scale", 1e-3 * max(1.0, abs(want)) + 2e-4
                else:
                    d, kind, lim = abs(got - want), "pos", 1e-3
                    if fname == "X_POS" and name in WRAP:      # a wrap's two ends are the same place, far off screen
                        d = min(d, abs(d - WRAP[name]))
                worst[kind] = max(worst[kind], d)
                if d > lim:
                    bad.append(f"{label} {name}.{fname}: forth {got:.6f} reference {want:.6f}")
        missing = [n for n in sc.poses if not any((ix[n], ids[f]) in writes for f, _ in FIELDS)]
        if missing:
            bad.append(f"{label}: never posed: {missing}")
        near_step = abs(sc.sun.alt_deg - round(sc.sun.alt_deg)) < 1e-3       # float and double may floor apart here
        for (name, slot), rgb in sc.colours.items():
            key = (ix[name], colour_box + slot)
            if key not in writes:
                bad.append(f"{label} {name} slot {slot}: never coloured")
                continue
            v = int(writes[key])
            got = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
            d = max(abs(a - b) for a, b in zip(got, rgb))
            worst["colour"] = max(worst["colour"], d)
            if d > 1 and not near_step:
                bad.append(f"{label} {name} slot {slot}: forth {got} reference {rgb}")
        for cell, want in sc.visible.items():
            got = host.read(cell)
            if got != want:
                bad.append(f"{label} visibility {cell}: forth {got} reference {want}")
        tide = host.read(TIDE_CELL)
        worst["tide"] = max(worst["tide"], abs(tide - sc.tide))
        if abs(tide - sc.tide) > 0.01:
            bad.append(f"{label} tide: forth {tide:.5f} reference {sc.tide:.5f}")
    # without a reset, a frame in the same look step re-colours nothing
    day, sod, _ = cases[0]
    host.frame_at(day, sod)
    _r, _d, _s, writes = host.frame_at(day, sod + 0.5, reset_look=False)
    again = [k for k in writes if colour_box <= k[1] <= colour_box + 2]
    if again and tl.scene(day, sod).q == tl.scene(day, sod + 0.5).q:
        bad.append(f"re-coloured {len(again)} materials with the look unchanged")
    return worst, bad


def cases():
    out = []
    today = tl.wall_day(dt.date(2026, 11, 21))
    # a day in steps that cross dawn, noon, dusk and night; the six moments; the hour and midnight
    for k in range(0, 96, 3):
        out.append((today, k * 900.0 + 7.3, None))
    for spec in ("2026-11-21T06:05:00", "2026-11-21T12:00:00", "2026-11-21T17:40:00", "2026-11-21T18:10:00",
                 "2026-11-21T21:30:00", "2027-03-02T02:45:00", "2026-11-21T10:59:59.95", "2026-11-21T23:59:59.95",
                 "2026-06-21T18:30:12", "2025-12-31T23:59:30", "2026-01-01T00:00:00", "2030-07-04T16:20:05.5"):
        out.append((*tl.parse_when(spec), None))
    # every value of every setting (Verification 13): drift off, Roman, no numerals, no gauge, no boats and birds
    for options in ({"drift": 1}, {"numerals": 1}, {"numerals": 2}, {"gauge": 1}, {"life": 1},
                    {"drift": 1, "numerals": 2, "gauge": 1, "life": 1}):
        out.append((today, 15 * 3600 + 150.0, options))
        out.append((today, 21 * 3600 + 10.0, options))
    return out


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="th-forth-") as t:
        tmp = Path(t)
        ids, ix = build(tmp)
        host = Host(tmp, ids)
        cs = cases()
        worst, bad = compare(host, ix, ids, cs)
        host.close()
    print(f"{len(cs)} frames; worst position {worst['pos']*1000:.4f} mm, rotation {worst['rot']*360:.4f} deg, "
          f"scale {worst['scale']:.6f}, colour {worst['colour']} step(s), tide {worst['tide']*1000:.3f} mm")
    for b in bad[:30]:
        print("FAIL", b)
    print("PASS" if not bad else f"FAIL: {len(bad)} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
