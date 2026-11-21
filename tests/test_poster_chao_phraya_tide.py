"""The Bangkok tide poster (docs/reference/chao-phraya-tide-poster/): its claims, its numbers, its page.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (D11). Needs the Navy's table in the cache
(bash wflevels/tide_harbour/tide_fit/fetch_sources.sh); skipped without it. The PDF and layout tests need the exported files
(python3 docs/reference/chao-phraya-tide-poster/export_poster.py).
"""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
POSTER = ROOT / "docs" / "reference" / "chao-phraya-tide-poster"

spec = importlib.util.spec_from_file_location("make_poster_tide", POSTER / "make_poster.py")
mp = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mp)
except SystemExit as e:                                   # the cache or a fit artifact is missing
    pytest.skip(f"poster inputs missing: {e}", allow_module_level=True)

HTML = POSTER / "poster.html"


def text_of(path):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(style|script)>.*?</\1>", "", path.read_text(encoding="utf-8"), flags=re.S))).replace(" ", " ").replace("‑", "-")


def test_every_claim_is_printable_and_traceable():
    assert mp.check_claims() == []
    kinds = {c["status"] for _, c in mp.all_claims()}
    assert kinds <= set(mp.PRINTABLE)
    for area, c in mp.all_claims():
        if c["status"] in ("verified", "other-source"):
            assert c["src"], (area, c["text"][:40])
        if c["status"] == "ours":
            assert c.get("by"), (area, c["text"][:40])


def test_every_source_is_cited_and_has_a_link():
    cited = set(mp.source_order())
    assert cited == set(mp.SOURCES), (cited ^ set(mp.SOURCES))
    for s in cited:
        assert mp.SOURCES[s]["url"].startswith("https://")


def test_the_build_refuses_what_it_should(monkeypatch):
    bad = dict(status="unverified", src=[], text="a claim nobody confirmed")
    monkeypatch.setattr(mp, "HEADER_CLAIMS", mp.HEADER_CLAIMS + [bad])
    assert any("cannot be printed" in p for p in mp.check_claims())
    monkeypatch.setattr(mp, "HEADER_CLAIMS", mp.HEADER_CLAIMS[:-1] + [dict(status="verified", src=[], text="no source")])
    assert any("needs a source" in p for p in mp.check_claims())
    monkeypatch.setattr(mp, "HEADER_CLAIMS", mp.HEADER_CLAIMS[:-1] + [dict(status="ours", src=[], text="no script")])
    assert any("must name what computes it" in p for p in mp.check_claims())
    monkeypatch.setattr(mp, "HEADER_CLAIMS", mp.HEADER_CLAIMS[:-1] + [dict(status="verified", src=["nope"], text="bad source")])
    assert any("unknown source" in p for p in mp.check_claims())


def test_printed_numbers_are_the_data():
    d = json.loads((ROOT / "wflevels/tide_harbour/tide_constants.json").read_text())
    st = d["table_stats"]["2026"]
    v = d["validation_height_error_at_listed_events"]["fitted_2026_scored_on_2027"]
    tz = json.loads((ROOT / "wflevels/tide_harbour/time_zone_check.json").read_text())
    assert HTML.exists(), "run make_poster.py"
    t = text_of(HTML)
    for needle in (f"{st['min_m']:.2f} m", f"{st['max_m']:.2f} m", f"{st['daily_range_max_m']:.2f} m", f"median error {v['median_cm']:.1f} cm",
                   f"largest {v['max_cm']:.1f} cm", f"{tz['mismatch_at_best_min']:.0f} min", f"{tz['mismatch_at_zero_min']:.0f} min",
                   f"{d['z0_m']:.2f} m"):
        assert needle in t, needle
    k1, o1, m2, s2 = (next(c["amp_m"] for c in d["constituents"] if c["name"] == n) for n in ("K1", "O1", "M2", "S2"))
    assert f"{(k1 + o1) / (m2 + s2):.2f}" in t
    assert f"{st['days_by_event_count']['4']} list two highs" in t


def test_the_spring_neap_period_matches_noaas_speeds():
    # NOAA's table: M2 28.9841042 and S2 30.0000000 degrees an hour. The gap is 1.0158958 degrees an hour.
    expected_days = 360.0 / (30.0 - 28.9841042) / 24.0
    assert abs(mp.SPRING_NEAP_DAYS - expected_days) < 0.01, (mp.SPRING_NEAP_DAYS, expected_days)
    assert f"{mp.SPRING_NEAP_DAYS:.2f}" in text_of(HTML) and mp.SPRING_NEAP_DAYS > 0


def test_every_panel_and_the_legend_are_present():
    html = HTML.read_text(encoding="utf-8")
    for p in mp.PANELS:
        assert f'id="panel-{p["key"]}"' in html
        assert (POSTER / f"{[x['key'] for x in mp.PANELS].index(p['key']) + 1:02d}-{p['key']}.svg").exists()
    for s in mp.used_statuses():
        assert f'<span class="chip {s}">{mp.STATUS_TEXT[s]}</span>' in html


def lum(hexcol):
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def test_drawn_text_is_big_enough_and_readable():
    assert HTML.exists()
    mp.build()                                            # fills TEXT_PAIRS and TEXT_SIZES from the real panels
    assert min(mp.TEXT_SIZES) >= mp.MIN_PX
    for fg, bg in mp.TEXT_PAIRS:
        a, b = sorted((lum(fg), lum(bg)), reverse=True)
        assert (a + 0.05) / (b + 0.05) >= 4.5, (fg, bg)


def test_the_layout_review_is_clean():
    review = POSTER / "layout-review.json"
    if not review.exists():
        pytest.skip("run export_poster.py")
    r = json.loads(review.read_text())
    assert r["page_mm"] == {"width": 297, "height": 420}
    assert not r["overflowing"] and r["fit"] == "ok" and r["orphaned_header_refs"] == []
    assert r["min_font_pt"] >= 8.25
    assert all(not p["overflowing"] for p in r["panels"])


def test_the_pdf_is_one_a3_page():
    pdf = POSTER / "chao-phraya-tide-a3.pdf"
    if not pdf.exists() or not shutil.which("pdfinfo"):
        pytest.skip("run export_poster.py (and have poppler's pdfinfo)")
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    assert re.search(r"^Pages:\s+1$", out, re.M)
    w, h = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", out).groups())
    assert abs(w / 72 * 25.4 - 297) < 1.5 and abs(h / 72 * 25.4 - 420) < 1.5, (w, h)
