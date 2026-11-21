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
sys.path.insert(0, str(ROOT / "tests"))
import level_modules  # noqa: E402

tl, _parts, forth, turns = level_modules.load("tide_harbour", "timeline", "parts", "forth", "turns")
import verify_minute_machine_forth as mm  # noqa: E402  (its VM host and bootstrap builder; it imports Minute Machine's own modules)

# The host also answers property@ ( actor field -- value valid ), syscall 178 as scripting_zforth.cc registers it,
# from a table the test fills with 'P actor field value' ('Q' empties it: every read is then invalid).
HOST = (mm.HOST
        .replace('static std::vector<W> writes;', 'static std::vector<W> writes;\nstatic std::map<std::pair<int,int>, float> props;')
        .replace('  else if ((int)id >= 128 && wf::forthmath::HandleSyscall(c, (int)id - 128)) {}',
                 '''  else if ((int)id == 178) { int f = (int)zf_pop(c); int a = (int)zf_pop(c); auto it = props.find({a, f});
    zf_push(c, it == props.end() ? 0.0f : it->second); zf_push(c, it == props.end() ? 0.0f : 1.0f); }
  else if ((int)id >= 128 && wf::forthmath::HandleSyscall(c, (int)id - 128)) {}''')
        .replace('else if (line[0] == \'T\') {', '''else if (line[0] == 'R') { int i; sscanf(line + 2, "%d", &i); printf("V %d %.9g\\n", i, mbx.count(i) ? mbx[i] : 0.0f); fflush(stdout); }
    else if (line[0] == 'P') { int a, f; float v; sscanf(line + 2, "%d %d %f", &a, &f, &v); props[{a, f}] = v; }
    else if (line[0] == 'Q') { props.clear(); }
    else if (line[0] == 'T') {''')
        .replace('eval("mm-tick")', 'eval("th-tick")'))
assert HOST.count("th-tick") == 1 and "line[0] == 'R'" in HOST and "(int)id == 178" in HOST and "line[0] == 'P'" in HOST

CONSTANTS = ["X_POS", "Y_POS", "Z_POS", "ROTATION_A", "ROTATION_B", "ROTATION_C", "X_SCALE", "Y_SCALE", "Z_SCALE",
             "FACE_COLOR_TOP", "WALL_HOUR", "WALL_MINUTE", "WALL_SECOND", "WALL_DAY"]
FIELDS = [("X_POS", 0), ("Y_POS", 1), ("Z_POS", 2), ("ROTATION_A", 3), ("ROTATION_B", 4), ("ROTATION_C", 5),
          ("X_SCALE", 6), ("Y_SCALE", 7), ("Z_SCALE", 8)]
TIDE_CELL = 600 + forth.CELLS.index("tide")
ANSWERED_CELL = 600 + forth.CELLS.index("sv")          # how many settings fields property@ answered this frame
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
    with open(tmp / "bootstrap.fth", "a") as f:          # the engine registers property@ beside its other words
        f.write(": property@ 178 sys ;\n")
    return ids, ix


class Host(mm.Host):
    def set_settings(self, options):
        """The TideHarbourSettings object's fields, as property@ will answer them; None: the object does not answer."""
        self.proc.stdin.write("Q\n")
        if options is not None:
            actor = self.ix[tl.SETTINGS_ACTOR]
            for name, label in tl.FIELD_LABELS.items():
                self.proc.stdin.write(f"P {actor} {self.fields[label]} {options.get(name, 0)}\n")

    def frame_at(self, day: int, sod: float, options=None, reset_look=True, answer=True):
        h, m = int(sod // 3600) % 24, int(sod // 60) % 60
        sec = sod % 60.0
        lines = [("WALL_DAY", day), ("WALL_HOUR", h), ("WALL_MINUTE", m), ("WALL_SECOND", sec)]
        for name, v in lines:
            self.proc.stdin.write(f"M {self.ids[name]} {v!r}\n")
        self.set_settings((options or {}) if answer else None)
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


def prime(host: Host, day: int, sod: float, options=None) -> None:
    """Run frames at this time until the next-turn scan has finished, as the level would have by the time the panel is
    seen: the panel's drums and arrows read its result."""
    for name in ("rdy", "act"):
        host.proc.stdin.write(f"M {scan_cell(name)} 0\n")
    for _ in range(40):
        host.frame_at(day, sod, options, reset_look=False)
        if host.read(scan_cell("rdy")) == 1 and host.read(scan_cell("act")) == 0:
            return
    raise RuntimeError(f"the scan did not finish at {tl.date_of(day)} {sod}")


def compare(host: Host, ix, ids, cases):
    worst = {"pos": 0.0, "rot": 0.0, "scale": 0.0, "colour": 0, "tide": 0.0}
    bad = []
    colour_box = ids["FACE_COLOR_TOP"]
    for day, sod, options in cases:
        prime(host, day, sod, options)
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
        answered = host.read(ANSWERED_CELL)
        if answered != len(tl.FIELD_LABELS):
            bad.append(f"{label}: property@ answered {answered} of {len(tl.FIELD_LABELS)} settings fields")
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


def scan_cell(name: str) -> int:
    return forth.SCAN0 + forth.SCAN_CELLS.index(name)


def scan_cases():
    """Where the next-turn scan is checked: a day in steps, the six moments' neighbours and the awkward ones (midnight
    between turns, a year boundary, a far date)."""
    today = tl.wall_day(dt.date(2026, 11, 21))
    out = [(today, k * 2700.0 + 11.0) for k in range(32)]
    for spec in ("2026-11-21T16:30:00", "2026-11-21T23:50:00", "2026-11-22T00:00:00", "2025-12-31T23:30:00",
                 "2026-01-01T00:00:00", "2027-03-02T02:45:00", "2030-07-04T16:20:05.5", "2026-06-21T18:30:12"):
        out.append(tl.parse_when(spec))
    return out


def check_scan(host: Host, cs):
    """Each case: start a fresh scan, run frames until it settles (counting them), and compare what the panel would
    show with turns.panel_reading: the scan's mark, the next high and low (times within 5 s, heights within 0.5 cm,
    float32 against double) and whether the next turn is a high. Then step the clock, without a reset, to 40 seconds
    either side of the next high and low: the pick must move on by itself when a turn passes, and a new scan must
    start on a ten-minute mark, and each time the reading equals the model's."""
    bad, frames, worst = [], [], {"t": 0.0, "h": 0.0}

    def settle(day, sod, label):
        n = 0
        while True:
            r, dsp, rsp, _w = host.frame_at(day, sod)
            n += 1
            if r != 0 or dsp != 0 or rsp != 0:
                bad.append(f"{label}: VM result {r}, data stack {dsp}, return stack {rsp}")
                return n, None
            if host.read(scan_cell("rdy")) == 1 and host.read(scan_cell("act")) == 0:
                break
            if n > 40:
                bad.append(f"{label}: not finished after {n} frames")
                return n, None
        rd = turns.panel_reading(day, sod)
        got = {k: host.read(scan_cell(k)) for k in ("nht", "nhh", "nlt", "nlh", "rise", "rn", "rsec")}
        if abs(got["rsec"] - rd.mark) > 0.5:
            bad.append(f"{label}: the scan started at {got['rsec']:.0f} s, the model's mark is {rd.mark:.0f} s")
        for (t, h), want in (((got["nht"], got["nhh"]), rd.high), ((got["nlt"], got["nlh"]), rd.low)):
            worst["t"], worst["h"] = max(worst["t"], abs(t - want.t)), max(worst["h"], abs(h - want.h))
            if abs(t - want.t) > 5.0 or abs(h - want.h) > 0.005:
                bad.append(f"{label}: forth {t:.1f} s {h:.4f} m, reference {want.t:.1f} s {want.h:.4f} m")
        if got["rise"] != float(rd.rise):
            bad.append(f"{label}: rising {got['rise']}, reference {rd.rise}")
        if got["rn"] >= turns.KEPT_MAX:
            bad.append(f"{label}: the scan kept {got['rn']:.0f} turns, its room is {turns.KEPT_MAX}")
        return n, rd

    for day, sod in cs:
        for name in ("rdy", "act"):
            host.proc.stdin.write(f"M {scan_cell(name)} 0\n")
        n, rd = settle(day, sod, f"scan {tl.date_of(day)} {sod:.0f}")
        frames.append(n)
        if rd is None:
            continue
        for turn in (rd.high, rd.low):
            for dt_s in (-40.0, 40.0):
                t = rd.mark + turn.t + dt_s
                if t > sod + 1.0 and t < 86400.0:
                    settle(day, t, f"scan {tl.date_of(day)} {t:.0f} (turn at {rd.mark + turn.t:.0f}, started {sod:.0f})")
    return frames, worst["t"], worst["h"], bad


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
    # the river panel: inside a swap of sides (the slide takes 2.6 s from each ten-minute mark), both ways, and across the map's pan
    for sod in (9 * 3600 + 0.4, 9 * 3600 + 1.15, 9 * 3600 + 2.2, 9 * 3600 + 600 + 0.9, 9 * 3600 + 600 + 1.45, 9 * 3600 + 600 + 1.9,
                10 * 3600 + 300.0, 10 * 3600 + 450.0, 10 * 3600 + 900.0, 10 * 3600 + 1350.0):
        out.append((today, sod, None))
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
        host.ix, host.fields = ix, forth.settings_fields()
        cs = cases()
        worst, bad = compare(host, ix, ids, cs)
        scs = scan_cases()
        frames, wt, wh, sbad = check_scan(host, scs)
        bad += sbad
        host.close()
    print(f"{len(cs)} frames; worst position {worst['pos']*1000:.4f} mm, rotation {worst['rot']*360:.4f} deg, "
          f"scale {worst['scale']:.6f}, colour {worst['colour']} step(s), tide {worst['tide']*1000:.3f} mm")
    print(f"{len(scs)} scans, {min(frames)} to {max(frames)} frames each at {forth.SCAN_BURST} samples a frame; worst time "
          f"{wt:.2f} s, worst height {wh * 100:.3f} cm against turns.py")
    for b in bad[:30]:
        print("FAIL", b)
    print("PASS" if not bad else f"FAIL: {len(bad)} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
