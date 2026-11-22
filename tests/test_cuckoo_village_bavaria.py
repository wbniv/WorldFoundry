"""Bavaria mode's behaviour in the Cuckoo Village reference timeline and its generated Forth (wflevels/cuckoo_village).

Plan docs/plans/2026-11-21-cuckoo-village.md, "Bavaria mode": the clock runs backwards (the dial sweeps counter-clockwise) and the
hourly parade travels the other way round its route; every event keeps its moment. Pure Python; the director against the real VM
is tests/verify_cuckoo_village_forth.py (run by test_cuckoo_village_forth.py).
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
import forth            # noqa: E402
import timeline as tl   # noqa: E402

BAV = {**tl.SETTINGS_DEFAULTS, "Bavaria mode": 1}
TAU = math.tau


def at(h, m, s):
    return h * 3600.0 + m * 60 + s


def test_bavaria_mode_is_off_by_default_and_the_default_poses_are_the_classic_ones():
    assert tl.SETTINGS_DEFAULTS["Bavaria mode"] == 0 and tl.bavaria_sign() == 1.0 and tl.bavaria_sign(BAV) == -1.0
    for sod in (at(10, 8, 22), at(12, 0, 8), at(15, 15, 3), at(23, 59, 59)):
        assert tl.all_poses(sod) == tl.all_poses(sod, {**tl.SETTINGS_DEFAULTS, "Bavaria mode": 0})


def test_the_hands_take_the_negated_angle_and_show_the_same_time():
    """Plan: at 10:08 the minute hand points just past one on the left of twelve (-48 degrees), the hour hand just past ten on
    the right of twelve (-304 degrees, that is +56)."""
    c, b = tl.all_poses(at(10, 8, 0)), tl.all_poses(at(10, 8, 0), BAV)
    assert math.isclose(b["minute_hand"][4], -c["minute_hand"][4]) and math.isclose(b["hour_hand"][4], -c["hour_hand"][4])
    assert math.isclose(b["minute_hand"][4] * 360, -48.0, abs_tol=1e-9)
    assert math.isclose((b["hour_hand"][4] * 360) % 360, 56.0, abs_tol=1e-9)
    # on a dial whose numerals run anti-clockwise (n at -30n degrees) the hour hand is past 10 (at +60) toward 11 (at +30)
    assert 30.0 < (b["hour_hand"][4] * 360) % 360 < 60.0
    # the other channels of the hands, and everything that is not the dial or the parade, are untouched
    for k in ("minute_hand", "hour_hand"):
        assert c[k][:4] == b[k][:4] and c[k][5:] == b[k][5:]
    for k in ("tower_bird", "cs_wide", "LookAt"):
        assert c[k] == b[k]
    assert tl.window_states(at(23, 0, 0)) == tl.window_states(at(23, 0, 0), BAV)


def angle_on_oval(x, y):
    return math.atan2((y - tl.LOOP_CY) / tl.LOOP_B, (x - tl.LOOP_CX) / tl.LOOP_A)


def test_the_parade_goes_the_other_way_round_the_same_route():
    for i in range(4):
        moves = []
        for sign in (1.0, -1.0):
            x0, y0, *_ = tl.figure(i, 10.0, sign)
            x1, y1, *_ = tl.figure(i, 10.2, sign)
            d = (angle_on_oval(x1, y1) - angle_on_oval(x0, y0) + math.pi) % TAU - math.pi
            moves.append(d)
        assert moves[0] * moves[1] < 0, f"figure {i + 1}: the two modes must travel opposite ways round the oval ({moves})"
        assert math.isclose(abs(moves[0]), abs(moves[1]), rel_tol=0.2), (i, moves)       # the same speed


def test_every_figure_leaves_its_own_alcove_and_comes_back_to_it_in_both_modes():
    for sign in (1.0, -1.0):
        for i in range(4):
            for tm in (0.0, 24.0, 100.0, 899.0):                      # outside the parade (figure 4 steps out from 0 s, the others from 2 s)
                x, y, z, a, c = tl.figure(i, tm, sign)
                assert (x, y) == (tl.FIG_X[i], tl.FIG_HOME_Y) and a == 0.0 and c == 0.0 and z == tl.FIG_Z0
            # the route is closed: the loop is two laps in 18 s, so one lap (9 s) later a figure that is fully on the route is in
            # the same place (it has not yet started to leave, and has finished arriving)
            for t in (6.0, 8.0, 10.0):
                (xa, ya, *_), (xb, yb, *_) = tl.figure(i, t, sign), tl.figure(i, t + tl.PARADE_LOOP_SECONDS / 2, sign)
                assert math.hypot(xa - xb, ya - yb) < 1e-6, (i, sign, t)


def test_the_schedule_is_the_same_in_both_modes():
    """Same start, same duration, same entry and exit blending: a figure's blend weight depends on the time only, so before the loop
    begins (progress 0) both modes put every figure at the same place; the solo turns are not part of the parade and are not reversed."""
    for i in range(4):
        for tm in (0.2, 1.0, 2.0, 2.9):
            assert tl.figure(i, tm, 1.0)[:4] == tl.figure(i, tm, -1.0)[:4]
    for i in range(3):
        for s in (0.5, 3.0, 7.0):
            tm = tl.SOLO_AT[i] + s
            assert tl.figure(i, tm, 1.0) == tl.figure(i, tm, -1.0)
    assert tl.all_poses(at(12, 0, 5))[tl.BIRD_NAME] == tl.all_poses(at(12, 0, 5), BAV)[tl.BIRD_NAME]


def test_the_heading_follows_the_direction_of_travel():
    """A figure faces where it is going: reversing the progress reverses the velocity, so the heading is the one for the reversed direction."""
    for i in range(4):
        for tm in (8.0, 12.0, 16.0):
            for sign in (1.0, -1.0):
                x0, y0, *_ = tl.figure(i, tm - 0.01, sign)
                x1, y1, *_ = tl.figure(i, tm + 0.01, sign)
                c = tl.figure(i, tm, sign)[4]
                vx, vy = x1 - x0, y1 - y0
                assert math.isclose(math.atan2(vx, -vy) / TAU % 1.0, c % 1.0, abs_tol=0.01), (i, tm, sign)


def test_the_director_reads_the_field_once_as_a_sign_and_uses_it_for_the_hands_and_the_parade():
    script = forth.director_script({n: 60 + k for k, n in enumerate(["tower_figure_1", "tower_figure_2", "tower_figure_3", "tower_figure_4",
                                                                      "tower_figure_b1", "tower_figure_b2", "tower_figure_b3", "tower_figure_b4", "tower_bird", "hour_hand", "minute_hand", "cs_wide", "LookAt", "CuckooVillageSettings"])})
    assert ": cv-sgn cv-s-bavaria-mode if -1 else 1 then ;" in script
    assert script.index(": cv-s-bavaria-mode") < script.index(": cv-sgn") < script.index(": cv-fig")
    assert script.count("cv-sgn") == 6, "the sign is used in the parade's progress and velocity (3 times) and in each hand (2 times), plus its definition"


def test_the_bavarian_twins_are_posed_exactly_like_the_classic_figures_and_the_modes_have_their_own_cells():
    for sod in (at(12, 0, 9), at(15, 30, 4)):
        for setting in (None, BAV):
            poses = tl.all_poses(sod, setting)
            for classic, twin in zip(tl.FIG_NAMES, tl.FIG_B_NAMES):
                assert poses[classic] == poses[twin]
    assert tl.BAVARIA_CELL != tl.CLASSIC_CELL and 214 < tl.BAVARIA_CELL and tl.CLASSIC_CELL < 600     # clear of the candles' and flames' cells and the scratch cells
    script = forth.director_script({n: 60 + k for k, n in enumerate([*tl.FIG_NAMES, *tl.FIG_B_NAMES, "tower_bird", "hour_hand", "minute_hand", "cs_wide", "LookAt", "CuckooVillageSettings"])})
    assert f"cv-s-bavaria-mode if 1 else 0 then {tl.BAVARIA_CELL} cv!" in script and f"cv-s-bavaria-mode if 0 else 1 then {tl.CLASSIC_CELL} cv!" in script
    assert script.index(": cv-vis") < script.index(": cv-tick")
