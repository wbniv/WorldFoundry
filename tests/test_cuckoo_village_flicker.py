"""The Cuckoo Village candle flicker, Option A (plan docs/plans/2026-11-22-cuckoo-village-candle-flicker.md): the model, the geometry,
and (in test_cuckoo_village_forth.py) the director in the real zForth VM."""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "cuckoo_village"))
import candles as cd  # noqa: E402
import timeline as tl  # noqa: E402


def test_there_are_24_groups_and_no_two_share_a_phase():
    assert tl.FLICKER_GROUPS == 2 * tl.TREES == 48
    phases = [round(tl.flicker_phase(i), 6) for i in range(tl.FLICKER_GROUPS)]
    assert len(set(phases)) == tl.FLICKER_GROUPS


def test_the_cells_sit_between_the_flowers_and_the_directors_scratch_cells():
    cells = [tl.FLICKER_CELL0 + k for k in range(2 * tl.FLICKER_GROUPS)]
    assert cells == list(range(700, 796)) and len(set(cells)) == 96
    used = {tl.CANDLE_CELL, tl.FLOWERS_CELL, tl.BLOCKS_CELL, tl.BAVARIA_CELL, tl.CLASSIC_CELL, *range(200, 214), *range(215, 227)}
    assert not used & set(cells) and min(cells) >= 700 and max(cells) < 799


def test_the_pattern_repeats_every_minute_because_the_rates_are_whole_cycles_a_minute():
    assert abs(tl.FLICKER_F1 * 60 - round(tl.FLICKER_F1 * 60)) < 1e-9 and abs(tl.FLICKER_F2 * 60 - round(tl.FLICKER_F2 * 60)) < 1e-9
    for gi in range(tl.FLICKER_GROUPS):
        for t in (0.0, 0.37, 12.5, 59.99):
            assert abs(tl.flame_drive(t, gi) - tl.flame_drive(t + 60.0, gi)) < 1e-9


def test_a_group_changes_shape_about_seven_times_a_second_and_the_groups_are_not_in_step():
    steps = 60 * 600
    flips = 0
    for gi in range(tl.FLICKER_GROUPS):
        prev = tl.flame_shape(0.0, gi // 2, gi % 2)
        for k in range(1, steps):
            s = tl.flame_shape(k / 600.0, gi // 2, gi % 2)
            flips += s != prev
            prev = s
    per_second = flips / tl.FLICKER_GROUPS / 60.0
    assert 7.0 <= per_second <= 8.0, per_second                          # the plan's measured 7.38, mean 136 ms
    # at no sample are all 24 groups in one shape, and across the minute no two groups share a schedule
    same = 0
    for k in range(0, 36000, 7):
        shapes = {tl.flame_shape(k / 600.0, gi // 2, gi % 2) for gi in range(tl.FLICKER_GROUPS)}
        same += len(shapes) == 1
    assert same == 0
    schedules = {tuple(tl.flame_shape(k / 30.0, gi // 2, gi % 2) for k in range(1800)) for gi in range(tl.FLICKER_GROUPS)}
    assert len(schedules) == tl.FLICKER_GROUPS


def test_each_tree_has_four_flame_meshes_of_five_candles_in_eight_triangles_each():
    shapes = cd.tree_flame_shapes(2, (-9.0, 4.0, 0.6), 0.3, 0.9)
    assert sorted(shapes) == [(0, 1), (0, 2), (1, 1), (1, 2)]
    for key, parts in shapes.items():
        assert len(parts) == cd.PER_TREE // cd.PER_TIER == 5, key
        verts, faces = cd.merge(parts)
        assert len(faces) == 5 * 8 and len(verts) == 5 * 6, key
        assert max(i for f in faces for i in f) < len(verts)


def test_both_shapes_share_the_candles_foot_and_differ_as_the_plan_says():
    bases = cd.candle_bases(1, (-4.0, 2.0, 0.5), 0.0, 1.0)
    shapes = cd.tree_flame_shapes(1, (-4.0, 2.0, 0.5), 0.0, 1.0)
    for n, base in enumerate(bases):
        g = n % cd.PER_TIER
        k = n // cd.PER_TIER
        tall, short = shapes[(g, 1)][k], shapes[(g, 2)][k]
        foot = (base[0], base[1], base[2] + cd.STICK_HEIGHT)
        for verts in (tall[0], short[0]):
            assert verts[4] == foot                                         # the foot vertex is the stick's top
        assert abs(tall[0][5][2] - foot[2] - 0.090) < 1e-9 and abs(short[0][5][2] - foot[2] - 0.060) < 1e-9
        assert abs(tall[0][5][0] - foot[0] - 0.014) < 1e-9 and abs(short[0][5][0] - foot[0] + 0.010) < 1e-9


def test_a_zero_lean_flame_is_todays_flame_exactly():
    assert cd.flame((0.1, 0.2, 0.3), cd.FLAME_RADIUS, cd.FLAME_HEIGHT) == cd.flame((0.1, 0.2, 0.3), cd.FLAME_RADIUS, cd.FLAME_HEIGHT, lean=0.0)
    verts, _ = cd.flame((0.0, 0.0, 0.0), 0.022, 0.075)
    assert verts[5] == (0.0, 0.0, 0.075)

