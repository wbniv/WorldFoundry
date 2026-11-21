"""The Bangkok tide constants (wflevels/tide_harbour/tide_constants.json) against the department's own table.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (Phase 0). Pure Python, no engine and no network. The events below
were read by eye from the Hydrographic Department's published table for station HD, Royal Thai Navy Headquarters,
Bangkok (HD2026.pdf), so they pin the constants to the source and not to our own parser.
"""
import datetime as dt
import json
import math
import statistics
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONSTANTS = ROOT / "wflevels" / "tide_harbour" / "tide_constants.json"
EPOCH = dt.datetime(2026, 1, 1)

# (date, "HHMM", height in metres above the lowest low water) copied from the printed table
PUBLISHED = [
    ((2026, 1, 1), "1330", 3.08),
    ((2026, 1, 2), "0010", 1.40), ((2026, 1, 2), "0847", 3.19),
    ((2026, 1, 3), "0128", 1.28), ((2026, 1, 3), "0922", 3.30),
    ((2026, 1, 8), "0437", 1.12), ((2026, 1, 8), "1132", 3.09), ((2026, 1, 8), "1731", 2.44), ((2026, 1, 8), "2043", 2.73),
    ((2026, 1, 9), "0446", 1.33), ((2026, 1, 9), "1139", 3.02), ((2026, 1, 9), "1804", 2.28), ((2026, 1, 9), "2139", 2.56),
    ((2026, 1, 10), "0439", 1.59), ((2026, 1, 10), "1120", 2.97), ((2026, 1, 10), "1844", 2.14), ((2026, 1, 10), "2243", 2.39),
    ((2026, 2, 1), "0121", 1.21), ((2026, 2, 1), "0907", 3.25),
    ((2026, 3, 1), "0801", 3.12),
]


@pytest.fixture(scope="module")
def doc():
    return json.loads(CONSTANTS.read_text())


def height(doc, when):
    t = (when - EPOCH).total_seconds() / 3600.0
    return doc["z0_m"] + sum(c["amp_m"] * math.cos(2 * math.pi * (c["cycles_per_hour"] * t + c["phase_rev"])) for c in doc["constituents"])


def test_the_file_says_what_it_is(doc):
    assert doc["epoch_local"] == "2026-01-01T00:00:00+07:00"
    assert "UTC+7" in doc["time_zone"] and "lowest low water" in doc["datum"]
    assert doc["n_constituents"] == len(doc["constituents"]) >= 32
    assert doc["sources"]["station"].startswith("HD, Royal Thai Navy Headquarters")


def test_every_constituent_is_consistent(doc):
    names = set()
    for c in doc["constituents"]:
        assert c["name"] not in names
        names.add(c["name"])
        assert math.isclose(c["cycles_per_hour"], c["speed_deg_per_h"] / 360.0, rel_tol=1e-12)
        assert 0.0 <= c["phase_rev"] < 1.0 and c["amp_m"] > 0
    assert {"K1", "O1", "M2", "S2"} <= names                       # the four that define the tide type


def test_the_constants_reproduce_the_printed_table(doc):
    errors = []
    for (y, m, d), hhmm, h in PUBLISHED:
        when = dt.datetime(y, m, d, int(hhmm[:2]), int(hhmm[2:]))
        errors.append(abs(height(doc, when) - h))
    # out-of-sample the median error is about 5 cm and the worst listed event about 22 cm
    assert statistics.median(errors) < 0.08, errors
    assert max(errors) < 0.30, errors


def test_the_curve_stays_inside_the_published_range(doc):
    lo, hi = doc["range_of_listed_extrema_m"]
    t0 = dt.datetime(2026, 6, 1)
    heights = [height(doc, t0 + dt.timedelta(minutes=10 * k)) for k in range(6 * 24 * 30)]
    assert lo - 0.35 < min(heights) and max(heights) < hi + 0.35


def test_it_keeps_its_accuracy_in_the_next_year(doc):
    v = doc["validation_height_error_at_listed_events"]
    assert v["fitted_2026_scored_on_2027"]["median_cm"] < 6.0 and v["fitted_2027_scored_on_2026"]["median_cm"] < 6.0
    assert v["fitted_2026_scored_on_2027"]["p90_cm"] < 14.0
