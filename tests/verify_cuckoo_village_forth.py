#!/usr/bin/env python3
"""Run the generated Cuckoo Village director in the real zForth VM and compare its date logic with timeline.py.

No engine, no display: the VM from engine/vendor is compiled with a host that provides the mailbox words (the harness of
tests/verify_minute_machine_forth.py, as tests/verify_tide_harbour_forth.py uses it). Each case sets WALL_DAY and the
clock, runs one frame (cv-tick) and reads the candle visibility cell:

  - Christmas candles (plan docs/plans/2026-11-21-cuckoo-village.md): always visible from 1 December through 6 January
    of the local date, across the year boundary and through leap years, whatever the switch says; visible the rest of
    the year only while the "Candles all year" setting is On.

    python3 tests/verify_cuckoo_village_forth.py        # also run by tests/test_cuckoo_village_forth.py
"""
from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import level_modules  # noqa: E402

tl, forth = level_modules.load("cuckoo_village", "timeline", "forth")
import verify_minute_machine_forth as mm  # noqa: E402  (its VM host and bootstrap builder)

# The host also answers property@ ( actor field -- value valid ), syscall 178 as scripting_zforth.cc registers it, from a
# table the test fills with 'P actor field value' ('Q' empties it: every read is then invalid and the default applies).
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
        .replace('eval("mm-tick")', 'eval("cv-tick")'))
assert HOST.count("cv-tick") == 1 and "line[0] == 'R'" in HOST and "(int)id == 178" in HOST and "line[0] == 'P'" in HOST, "the host patch did not apply"

CONSTANTS = ["X_POS", "Y_POS", "Z_POS", "ROTATION_A", "ROTATION_B", "ROTATION_C", "X_SCALE", "Y_SCALE", "Z_SCALE",
             "FACE_COLOR_TOP", "WALL_HOUR", "WALL_MINUTE", "WALL_SECOND", "WALL_DAY"]
NAMES = ["tower_figure_1", "tower_figure_2", "tower_figure_3", "tower_figure_4", "tower_bird", "hour_hand", "minute_hand",
         "cs_wide", "LookAt", "CuckooVillageSettings"]
FIELDS = {label: 129 + i for i, label in enumerate(tl.SETTINGS_DEFAULTS)}


class Shim:
    """What mm.build asks of a level's forth module: indices, and the definitions without the trailing per-frame call."""
    @staticmethod
    def default_indices():
        return {name: 100 + j for j, name in enumerate(NAMES)}

    @staticmethod
    def definitions(ix):
        lines = forth.director_script(ix, FIELDS).rstrip("\n").split("\n")
        assert lines[-1] == "cv-tick", lines[-1]
        return "\n".join(lines[:-1]) + "\n"


def build(tmp: Path):
    mm.CONSTANTS[:] = CONSTANTS
    mm.HOST = HOST
    src_forth, mm.forth = mm.forth, Shim
    try:
        ids, ix = mm.build(tmp)
    finally:
        mm.forth = src_forth
    with open(tmp / "bootstrap.fth", "a") as f:          # the engine registers property@ beside its other words
        f.write(": property@ 178 sys ;\n")
    return ids, ix


class Host(mm.Host):
    def __init__(self, tmp, ids, ix):
        super().__init__(tmp, ids)
        self.ix = ix

    def frame_at(self, day: int, sod: float, candles=None, lights=None):
        """One frame at local day `day` and second-of-day `sod`; candles: the Candles all year field (None: unanswered, so its default Off)."""
        self.proc.stdin.write("Q\n")
        if candles is not None:
            self.proc.stdin.write(f"P {self.ix['CuckooVillageSettings']} {FIELDS['Candles all year']} {candles}\n")
        if lights is not None:
            self.proc.stdin.write(f"P {self.ix['CuckooVillageSettings']} {FIELDS['Window lights']} {lights}\n")
        h, m = int(sod // 3600) % 24, int(sod // 60) % 60
        for name, v in (("WALL_DAY", day), ("WALL_HOUR", h), ("WALL_MINUTE", m), ("WALL_SECOND", sod % 60.0)):
            self.proc.stdin.write(f"M {self.ids[name]} {v!r}\n")
        self.proc.stdin.write("T\n")
        self.proc.stdin.flush()
        head = self.proc.stdout.readline().split()
        if not head or head[0] != "RESULT":
            raise RuntimeError(f"host: {head}")
        while self.proc.stdout.readline().split()[0] != "END":
            pass

    def read(self, cell: int) -> float:
        self.proc.stdin.write(f"R {cell}\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline().split()
        assert line[0] == "V" and int(line[1]) == cell, line
        return float(line[2])


def day_of(y, m, d):
    return (dt.date(y, m, d) - tl.DAY0).days


def season_days():
    """The days worth checking: the edges of the season in every year the 1461-day cycle covers, and the year ends."""
    out = []
    for year in range(2000, 2100):
        for month, day in ((11, 30), (12, 1), (12, 2), (12, 31), (1, 1), (1, 5), (1, 6), (1, 7), (2, 28), (3, 1), (6, 15)):
            out.append((dt.date(year, month, day) - tl.DAY0).days)
    return sorted(set(out))


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ids, ix = build(tmp)
        host = Host(tmp, ids, ix)
        try:
            days = season_days()
            for day in days:
                for sod in (0.0, 43200.0, 86399.0):             # midnight, noon, the last second
                    for candles, switch in ((None, 0), (1, 1), (0, 0)):
                        host.frame_at(day, sod, candles)
                        got = host.read(tl.CANDLE_CELL)
                        want = float(tl.christmas_season(day) or bool(switch))
                        if got != want:
                            failures += 1
                            if failures <= 10:
                                print(f"FAIL {tl.date_of(day)} {sod:7.0f} s switch={candles}: cell {tl.CANDLE_CELL} = {got}, want {want}")
            print(f"{len(days)} days x 3 times x 3 settings = {len(days) * 9} frames, {failures} failures")
            # the flames: each tree's cell is the candles' state times the window glow of house (tree mod 13), so they burn at
            # night and dusk only, on the windows' stagger, and the Window lights setting dims them
            flame_failures = 0
            for day in (day_of(2026, 12, 25), day_of(2026, 7, 4)):
                for sod in (12 * 3600.0, 17.5 * 3600 + 600.0, 19 * 3600.0, 23 * 3600.0, 3 * 3600.0, 5.5 * 3600 + 900.0):
                    for candles, lights in ((None, None), (1, 1), (1, 0), (0, 1)):
                        host.frame_at(day, sod, candles, lights)
                        on = tl.christmas_season(day) or bool(candles)
                        glow = tl.window_states(sod, {"Window lights": 1 if lights is None else lights})
                        for i in range(tl.TREES):
                            want = float(on and glow[i % tl.HOUSES])
                            got = host.read(tl.FLAME_CELL0 + i)
                            if got != want:
                                flame_failures += 1
                                if flame_failures <= 10:
                                    print(f"FAIL flame {i} {tl.date_of(day)} {sod:7.0f} s switch={candles} lights={lights}: {got}, want {want}")
            print(f"flames: {flame_failures} failures")
            failures += flame_failures
        finally:
            host.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
