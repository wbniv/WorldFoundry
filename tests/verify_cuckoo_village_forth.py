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
NAMES = ["tower_figure_1", "tower_figure_2", "tower_figure_3", "tower_figure_4", "tower_figure_b1", "tower_figure_b2", "tower_figure_b3", "tower_figure_b4", "tower_bird", "hour_hand", "minute_hand",
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

    def frame_at(self, day: int, sod: float, candles=None, lights=None, flowers=None, bavaria=None):
        """One frame at local day `day` and second-of-day `sod`; candles: the Candles all year field (None: unanswered, so its default Off);
        bavaria: the Bavaria mode field likewise. Returns the director's actor-mailbox writes, {(actor index, mailbox id): value}."""
        self.proc.stdin.write("Q\n")
        if candles is not None:
            self.proc.stdin.write(f"P {self.ix['CuckooVillageSettings']} {FIELDS['Candles all year']} {candles}\n")
        if lights is not None:
            self.proc.stdin.write(f"P {self.ix['CuckooVillageSettings']} {FIELDS['Window lights']} {lights}\n")
        if flowers is not None:
            self.proc.stdin.write(f"P {self.ix['CuckooVillageSettings']} {FIELDS['Detailed flowers']} {flowers}\n")
        if bavaria is not None:
            self.proc.stdin.write(f"P {self.ix['CuckooVillageSettings']} {FIELDS['Bavaria mode']} {bavaria}\n")
        h, m = int(sod // 3600) % 24, int(sod // 60) % 60
        for name, v in (("WALL_DAY", day), ("WALL_HOUR", h), ("WALL_MINUTE", m), ("WALL_SECOND", sod % 60.0)):
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
                return writes
            writes[(int(line[1]), int(line[2]))] = float(line[3])

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
            # the flicker (plan docs/plans/2026-11-22-cuckoo-village-candle-flicker.md): for each of the 24 groups exactly one of its two cells is the group's
            # lit state (the candles' state times the window glow of house tree mod 13, so they burn at night and dusk only, on the windows' stagger, and Window
            # lights puts them out), and which one is timeline.flame_shape at that second. Seconds within 1e-3 of a zero crossing of the drive are skipped:
            # the VM's float32 and the model's float64 may fall either side of it.
            flame_failures = flame_checked = 0
            for day, sod0, candles, lights in ((day_of(2026, 12, 25), 23 * 3600.0, None, None), (day_of(2026, 7, 4), 23 * 3600.0, 1, 1),
                                               (day_of(2026, 7, 4), 23 * 3600.0, None, None), (day_of(2026, 12, 25), 12 * 3600.0, None, None),
                                               (day_of(2026, 12, 25), 23 * 3600.0, 1, 0), (day_of(2026, 12, 25), 17.5 * 3600 + 600.0, None, None),
                                               (day_of(2026, 12, 25), 5.5 * 3600 + 900.0, None, None), (day_of(2026, 7, 4), 3 * 3600.0, 0, 1)):
                for k in range(0, 600, 3):
                    sod = sod0 + 17 * 60.0 + k * 0.1
                    host.frame_at(day, sod, candles, lights)
                    on = tl.christmas_season(day) or bool(candles)
                    glow = tl.window_states(sod, {"Window lights": 1 if lights is None else lights})
                    for gi in range(tl.FLICKER_GROUPS):
                        x = tl.flame_drive(sod % 60.0, gi)
                        if abs(x) < 1e-3:
                            continue
                        lit = float(on and glow[(gi // 2) % tl.HOUSES])
                        want = (lit, 0.0) if x > 0 else (0.0, lit)
                        got = (host.read(tl.FLICKER_CELL0 + 2 * gi), host.read(tl.FLICKER_CELL0 + 2 * gi + 1))
                        flame_checked += 1
                        if got != want:
                            flame_failures += 1
                            if flame_failures <= 10:
                                print(f"FAIL flame group {gi} {tl.date_of(day)} {sod:9.2f} s switch={candles} lights={lights}: {got}, want {want}")
            print(f"flames: {flame_failures} failures in {flame_checked} cells")
            failures += flame_failures
            # the window boxes: exactly one of the two actors shows. Detailed flowers On (or unanswered: the default is On) shows the
            # flowers and hides the blocks, Off the reverse, whatever the date or the time, and the other cells are untouched.
            flower_failures = 0
            for day in (day_of(2026, 12, 25), day_of(2026, 7, 4), day_of(2000, 1, 1), day_of(2099, 12, 31)):
                for sod in (0.0, 12 * 3600.0, 17.5 * 3600 + 600.0, 23 * 3600.0 + 3599.0):
                    for flowers, want_on in ((None, 1.0), (1, 1.0), (0, 0.0)):
                        host.frame_at(day, sod, flowers=flowers)
                        got = (host.read(tl.FLOWERS_CELL), host.read(tl.BLOCKS_CELL))
                        if got != (want_on, 1.0 - want_on):
                            flower_failures += 1
                            if flower_failures <= 10:
                                print(f"FAIL flowers {tl.date_of(day)} {sod:7.0f} s field={flowers}: cells {got}, want {(want_on, 1.0 - want_on)}")
            print(f"flowers: {flower_failures} failures")
            failures += flower_failures
            # Bavaria mode: the hands and the four figures, every pose, against the reference, with the field Off, On and unanswered
            pose_failures = 0
            channels = {name: ("X_POS", "Y_POS", "Z_POS", "ROTATION_A", "ROTATION_C") for name in
                        (*tl.FIG_NAMES, *tl.FIG_B_NAMES)}      # the channels the director writes
            channels.update({"hour_hand": ("ROTATION_B",), "minute_hand": ("ROTATION_B",)})
            slot = {"X_POS": 0, "Y_POS": 1, "Z_POS": 2, "ROTATION_A": 3, "ROTATION_B": 4, "ROTATION_C": 5}      # the order of a pose tuple
            frames = 0
            for bavaria in (None, 0, 1):
                setting = {**tl.SETTINGS_DEFAULTS, "Bavaria mode": 1 if bavaria else 0}
                for sod in (10 * 3600 + 8 * 60 + 22.0, 12 * 3600 + 0.5, 12 * 3600 + 2.5, 12 * 3600 + 4.0, 12 * 3600 + 9.0, 12 * 3600 + 14.0,
                            12 * 3600 + 19.0, 12 * 3600 + 22.0, 12 * 3600 + 30.0, 15 * 3600 + 15 * 60 + 3.0, 23 * 3600 + 59 * 60 + 59.0):
                    writes = host.frame_at(day_of(2026, 11, 22), sod, bavaria=bavaria)
                    want_poses = tl.all_poses(sod, setting)
                    frames += 1
                    for cell, want_cell in ((tl.BAVARIA_CELL, float(bool(bavaria))), (tl.CLASSIC_CELL, float(not bavaria))):
                        if host.read(cell) != want_cell:                   # the Bavarian parts show with the mode On, the Classic parts it replaces with it Off
                            pose_failures += 1
                            print(f"FAIL visibility cell {cell} Bavaria={bavaria}: {host.read(cell)}, want {want_cell}")
                    for name, chans in channels.items():
                        for ch in chans:
                            got = writes[(ix[name], host.ids[ch])]
                            want = want_poses[name][slot[ch]]
                            if abs(got - want) > 2e-4:
                                pose_failures += 1
                                if pose_failures <= 10:
                                    print(f"FAIL pose {name} {ch} Bavaria={bavaria} {sod:8.1f} s: {got}, want {want}")
            print(f"poses: {frames} frames x {len(channels)} actors, {pose_failures} failures")
            failures += pose_failures
        finally:
            host.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
