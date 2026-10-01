"""Regression guard for the swarming work: the Couzin reference model, the Forth core (wflevels/aquarium/school.fth) and the A3 poster.

Plan: docs/plans/2026-10-01-swarming-poster.md and docs/plans/2026-10-01-aquarium-schooling.md.
Code: docs/reference/swarming-poster/ (couzin.py, zf_host.c + zfhost.py, forth_check.py, tank_trial.py, make_swarm_poster.py).

What it pins:
  * the reference model reproduces the paper's qualitative states (a torus has high angular momentum, a highly parallel group has p_group near 1);
  * the Forth core compiles in the engine's own zForth and equals the numpy model to float32 and Bhaskara-sine accuracy, one tick at a time;
  * its invariants: headings stay unit length, nothing becomes NaN, a startle sends the near followers away from the leader;
  * the poster: no text under 8 pt, WCAG AA contrast, every number in the data sheet, no external reference, the page fits.

    python3 -m pytest tests/test_swarming.py -v
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
POSTER_DIR = REPO / "docs" / "reference" / "swarming-poster"
sys.path.insert(0, str(POSTER_DIR))

import couzin  # noqa: E402
import forth_check as fc  # noqa: E402
import swarm_data as D  # noqa: E402
import make_swarm_poster as M  # noqa: E402

HAVE_CC = bool(shutil.which("cc"))
NEEDS_CC = pytest.mark.skipif(not HAVE_CC, reason="needs a C compiler for the zForth host")


# ── the reference model ──────────────────────────────────────────────────────
def test_paper_parameters_are_the_figure_3_values():
    p = couzin.PAPER
    assert (p["N"], p["rr"], p["alpha"], p["theta"], p["s"], p["sigma"]) == (100, 1.0, 270.0, 40.0, 3.0, 0.05)


def test_highly_parallel_group_has_p_near_one():
    _, _, p, m, frag = couzin.run(10.0, 10.0, steps=400, seed=1, N=60, tail=50)
    assert p > 0.95 and m < 0.2 and not frag


def test_a_torus_has_high_angular_momentum_and_low_polarisation():
    _, _, p, m, frag = couzin.run(1.0, 12.0, steps=700, seed=1, tail=100)
    assert m > 0.7 and p < 0.3 and not frag


def test_swarm_has_both_low():
    _, _, p, m, frag = couzin.run(0.0, 15.0, steps=700, seed=1, tail=100)
    assert p < 0.3 and m < 0.4 and not frag


def test_metrics_of_hand_built_groups():
    rng = np.random.default_rng(0)
    pos = rng.normal(size=(50, 3))
    same = np.tile([1.0, 0, 0], (50, 1))
    assert couzin.metrics(pos, same)[0] == pytest.approx(1.0)
    ring = np.array([[math.cos(a), math.sin(a), 0] for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)])
    tang = np.stack([-ring[:, 1], ring[:, 0], np.zeros(40)], 1)
    p, m = couzin.metrics(ring, tang)
    assert p < 1e-6 and m == pytest.approx(1.0)


# ── the Forth core ───────────────────────────────────────────────────────────
@NEEDS_CC
def test_school_fth_compiles_in_the_engines_zforth():
    h = fc.make_host()
    size = fc.load_school(h, 11)
    h.close()
    assert 500 < size < 8000                     # it is a small program; a blow-up or an empty load both fail


@NEEDS_CC
def test_forth_equals_numpy_one_tick_at_a_time():
    errs, _ = fc.compare(n=11, ticks=25)
    assert max(e[0] for e in errs) < 5e-3        # position, body lengths (one tick moves 0.2 BL)
    assert max(e[1] for e in errs) < 5e-3        # heading components (the engine's sine is 0.2 % off)


@NEEDS_CC
@pytest.mark.parametrize("w", [1.0, 6.0])
def test_forth_equals_numpy_with_a_strong_leader(w):
    errs, _ = fc.compare(n=11, ticks=15, w_leader=w, leader_turn=10.0, seed=5)
    assert max(e[0] for e in errs) < 5e-3 and max(e[1] for e in errs) < 5e-3


@NEEDS_CC
def test_forth_keeps_headings_unit_length_and_finite_in_the_tank():
    import tank_trial as tt
    r, h = tt.trial(5, 6, 3, 1, ticks=120, s=2.0, theta=120.0)
    h.close()
    v = np.array(r["vel"])
    assert np.isfinite(v).all() and np.isfinite(np.array(r["pos"])).all()
    assert np.abs(np.linalg.norm(v[1:], axis=1) - 1).max() < 5e-3
    assert r["inside"]


@NEEDS_CC
def test_a_startle_sends_the_near_followers_away_from_the_leader():
    p = dict(couzin.PAPER, sigma=0.0, s=2.0, theta=120.0)
    h = fc.make_host(); fc.load_school(h, 5)
    fc.set_params(h, p, 5.0, 6.0, 3.0)
    # a leader at the origin heading +x, four followers at 2 BL around it, all heading along the circle (tangent, so only the startle moves them out)
    fc.put(h, 0, [0, 0, 0], [1, 0, 0])
    spots = [[2, 0, 0], [0, 2, 0], [-2, 0, 0], [0, -2, 0]]
    for i, sp in enumerate(spots, start=1):
        sp = np.array(sp, float); fc.put(h, i, sp, np.array([-sp[1], sp[0], 0]) / 2)
    assert h.eval("4 sch-startle-all") == "ok"
    assert all(h.read(fc.BASE + i * fc.STRIDE + 12) == pytest.approx(0.5) for i in range(1, 5))
    for _ in range(5):                                              # the 0.5 s startle lasts five ticks
        assert h.eval("sch-tick") == "ok"
    pos, vel = fc.get(h, 5)
    h.close()
    assert (np.linalg.norm(pos[1:], axis=1) > 2.3).all(), "the startled followers did not move away"


@NEEDS_CC
def test_a_follower_cannot_leave_the_box_and_its_heading_is_reflected():
    p = dict(couzin.PAPER, sigma=0.0)
    h = fc.make_host(); fc.load_school(h, 2)
    fc.set_params(h, p, 5.0, 6.0, 1.0, wall=0.0, box=3.0)            # a 6 body length box and no wall zone: only the hard limit acts
    fc.put(h, 0, [-2.9, 0, 0], [1, 0, 0])
    fc.put(h, 1, [2.8, 0, 0], [1, 0, 0])                              # 0.2 from the +x face, swimming straight at it, 0.5 a step
    for _ in range(6):
        assert h.eval("sch-tick") == "ok"
        pos, vel = fc.get(h, 2)
        assert (np.abs(pos[1]) <= 3.0 + 1e-6).all(), pos[1]
    assert vel[1][0] < 0.5, "the heading must have turned away from the wall"
    h.close()


@NEEDS_CC
def test_the_startle_timer_counts_down_and_stops():
    p = dict(couzin.PAPER, sigma=0.0)
    h = fc.make_host(); fc.load_school(h, 3)
    fc.set_params(h, p, 5.0, 6.0, 1.0)
    fc.put(h, 0, [0, 0, 0], [1, 0, 0]); fc.put(h, 1, [2, 0, 0], [1, 0, 0]); fc.put(h, 2, [30, 0, 0], [1, 0, 0])
    assert h.eval("4 sch-startle-all") == "ok"
    t = [h.read(fc.BASE + 14 + 12), h.read(fc.BASE + 28 + 12)]
    assert t == [pytest.approx(0.5), 0.0], "only the follower inside the radius is startled"
    for _ in range(7):
        h.eval("sch-tick")
    assert h.read(fc.BASE + 14 + 12) == pytest.approx(0.0, abs=1e-6)
    h.close()


# ── the data sheet and the poster ────────────────────────────────────────────
@pytest.fixture(scope="module")
def html_text():
    return M.build_html()


def test_every_row_has_a_status_and_a_source():
    rows = D.rows()
    assert len(rows) > 15
    for r in rows:
        assert r["status"] in D.STATUS_TEXT and r["sources"] and all(s in D.SOURCES for s in r["sources"])


def test_verified_rows_rest_on_an_opened_source():
    for r in D.rows():
        if r["status"] == "verified":
            assert all(D.SOURCES[s]["opened"] for s in r["sources"]), r["id"]


def test_the_paper_row_values():
    rows = {r["id"]: r for r in D.rows()}
    assert rows["n"]["value"] == "N = 100" and rows["theta"]["value"] == "40°/s" and rows["reps"]["value"] == "30 per cell"


def test_no_invented_urls():
    """Every URL on the poster already appears in the plans (the research section of the schooling plan)."""
    plans = (REPO / "docs" / "plans" / "2026-10-01-aquarium-schooling.md").read_text()
    for k, s in D.SOURCES.items():
        if s["url"]:
            assert s["url"] in plans, (k, s["url"])


def test_turn_arithmetic_is_the_one_printed():
    d, r = D.paper_turn()
    assert d == pytest.approx(6.75) and r == pytest.approx(3 / math.radians(40))
    d2, r2 = D.game_turn()
    assert d2 == pytest.approx(1.5) and r2 == pytest.approx(2 / math.radians(120))


def test_nothing_under_8pt(html_text):
    sizes = [float(m.group(1)) * 0.75 for m in re.finditer(r'font-size="([\d.]+)"', html_text)]
    sizes += [float(m.group(1)) * (0.75 if m.group(2) == "px" else 1) for m in re.finditer(r"font-size:([\d.]+)(px|pt)", html_text)]
    assert len(sizes) > 100 and min(sizes) >= 8.0 - 1e-9


def test_text_contrast_is_wcag_aa(html_text):
    pairs = set(M.FP.TEXT_PAIRS) | set(M.FP.HTML_TEXT_PAIRS)
    bad = [(fg, bg, round(M.contrast(fg, bg), 2)) for fg, bg in pairs if M.contrast(fg, bg) < 4.5]
    assert bad == []


def test_html_is_self_contained(html_text):
    assert not re.search(r"<link\b|@import|<script[^>]+src=|<img\b|src=\"https?:|url\((?!#)", html_text)


def test_hrefs_are_exactly_the_data_sheet_urls(html_text):
    assert sorted(re.findall(r'<a href="([^"]+)"', html_text)) == sorted(s["url"] for s in D.SOURCES.values() if s["url"])


def test_the_poster_prints_the_in_engine_numbers(html_text):
    e = D.load("measured.json")["engine"]
    t = html_text.replace("\u00a0", " ")
    assert f'{e["before"]["mailbox_us"]:g} → {e["after"]["mailbox_us"]:g} µs' in t
    assert f'{e["after"]["director_ms"][0]:.1f} ms' in t


def test_the_poster_prints_the_measured_numbers(html_text):
    m = D.load("measured.json")
    t = html_text.replace(" ", " ")
    assert f'{m["dictionary_bytes"]:,} B' in t.replace(" ", " ")
    assert f'{m["device"]["ms"]:.1f} ms a step on the Chromecast' in t.replace("\u00a0", " ")


def test_the_poster_says_what_it_does_not_claim(html_text):
    t = html_text.replace(" ", " ")
    assert "Not claimed" in t and "hysteresis" in t
    assert "the school is tuned" in t and "the dart does not startle it yet" in t, "the poster must say the school is in the game but untuned, and the dart is not wired"
    assert "not wired in yet" not in t, "the school IS in the game now: that sentence went stale"


def test_no_12_hour_clock(html_text):
    assert not re.search(r"\b\d{1,2}(:\d{2})?\s?(am|pm|a\.m\.|p\.m\.)\b", html_text, re.I)


def test_page_fits(tmp_path):
    if not shutil.which("google-chrome"):
        pytest.skip("no chrome")
    out = tmp_path / "poster.html"
    out.write_text(M.build_html(), encoding="utf-8")
    dom = subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={tmp_path / 'prof'}",
                          "--dump-dom", out.as_uri()], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r'data-fit="(\w+)" data-over="(-?[\d.]+)"', dom)
    assert m, "the fit script did not run"
    assert m.group(1) == "ok", f"content overflows the page by {m.group(2)} px"


def test_committed_html_is_current(html_text):
    committed = POSTER_DIR / "poster.html"
    assert committed.exists(), "run: task poster-swarming"
    assert committed.read_text(encoding="utf-8") == html_text
