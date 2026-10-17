"""Regression guard for the longsnout seahorse biomechanics poster.

Plan:      docs/plans/2026-10-16-saltwater-seahorses.md (Phase 0; Verification steps 1-4)
Research:  docs/reference/seahorse-research.md (written first; the poster prints only from it)
Generator: docs/reference/seahorse-biomechanics-poster/make_poster.py, export_poster.py

What it pins:
  * every printed claim is verified, other species or ours; nothing unverified prints; every
    verified / other-species claim names a source; every game number is chipped ours;
    measured populations and interpolated estimates remain distinct;
  * the legend shows exactly the chips that are used;
  * every source URL is one the research document already holds (no invented links);
  * the committed poster.html and SVG panels are what the generator makes now;
  * type is at least 8 pt, text contrast at least 4.5 : 1, numbers keep a non-breaking space
    before their unit, ISO dates use non-breaking hyphens, the HTML has no external reference;
  * the PDF (built here with Playwright when available) is one A3 page, every font embedded,
    type at least 8 pt, nothing in the outer 5 mm, the page fits, one link per source and no
    other link, and no pending-verification wording;
  * the PNG preview is 300 DPI A3.

    python3 -m pytest tests/test_poster_seahorse_biomechanics.py -v
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
POSTER_DIR = REPO / 'docs' / 'reference' / 'seahorse-biomechanics-poster'
RESEARCH = REPO / 'docs' / 'reference' / 'seahorse-research.md'
PDF_NAME = 'seahorse-biomechanics-a3.pdf'
NBSP = ' '
PENDING = re.compile(r'unverified|not opened|link missing', re.I)
sys.path.insert(0, str(POSTER_DIR))

import make_poster as M  # noqa: E402
import export_poster as E  # noqa: E402

HAVE_PLAYWRIGHT = importlib.util.find_spec('playwright') is not None
HAVE_POPPLER = all(shutil.which(t) for t in ('pdfinfo', 'pdffonts', 'pdftotext', 'pdftoppm'))
needs_pdf = pytest.mark.skipif(not (HAVE_PLAYWRIGHT and HAVE_POPPLER), reason='needs Python Playwright and poppler-utils')


# ── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope='module')
def built():
    return M.build()


@pytest.fixture(scope='module')
def html_text(built):
    return built[0]


@pytest.fixture(scope='module')
def exported(tmp_path_factory, built):
    """A fresh HTML → PDF → PNG export in a temp dir."""
    if not (HAVE_PLAYWRIGHT and HAVE_POPPLER):
        pytest.skip('needs Python Playwright and poppler-utils')
    out = tmp_path_factory.mktemp('seahorse-poster')
    M.main(['--out-dir', str(out)])
    review = E.export(out)
    return out, review


def _text_nodes(doc):
    out, skip = [], False
    for part in re.split(r'(<[^>]*>)', doc):
        if part.startswith('<'):
            low = part.lower()
            skip = low.startswith(('<style', '<script')) or (skip and not low.startswith(('</style', '</script')))
        elif not skip:
            out.append(part)
    return out


# ── claims and sources ───────────────────────────────────────────────────────
def test_every_claim_is_printable_and_sourced():
    assert M.check_claims() == []
    for area, c in M.all_claims():
        assert c['status'] in M.PRINTABLE, (area, c['text'])
        if c['status'] != 'ours':
            assert c['src'], (area, c['text'])


def test_the_claim_check_has_teeth(monkeypatch):
    bad = dict(M.PANELS[5]['claims'][0], status='unverified')
    monkeypatch.setitem(M.PANELS[5], 'claims', [bad] + M.PANELS[5]['claims'][1:])
    assert any('may not print' in p for p in M.check_claims())
    game = dict(M.PANELS[6]['claims'][0], status='verified', src=['porter'])
    monkeypatch.setitem(M.PANELS[6], 'claims', [game])
    assert any('must be chipped ours' in p for p in M.check_claims())


def test_game_costs_match_evidence_and_interpolation_is_labelled(html_text):
    games = [c for _a, c in M.all_claims() if c.get('game')]
    assert len(games) >= 8 and all(c['status'] == 'ours' for c in games)
    data = json.loads((REPO / 'docs/diagnostics/seahorse-close-cast1-20261017/comparison.json').read_text())
    for view, rows in data['views'].items():
        assert set(M.FRAME_MS[view]) == {0, 1, 2, 6}
        for row in rows:
            assert M.FRAME_MS[view][row['pairs']] == row['median_frame_ms']
        assert set(M.INTERPOLATED_FPS[view]) == {3, 4, 5}
        values = [M.FRAME_FPS[view][2], *M.INTERPOLATED_FPS[view].values(), M.FRAME_FPS[view][6]]
        assert all(a > b for a, b in zip(values, values[1:]))
    cost = next(p for p in M.PANELS if p['key'] == 'cost')
    assert any(c.get('chip') == 'measured (ours)' for c in cost['claims'])
    estimates = [c for c in cost['claims'] if c.get('chip') == 'estimate (ours)']
    assert len(estimates) == 1 and 'interpolation' in estimates[0]['text']
    assert '>measured (ours)</span>' in html_text and '>estimate (ours)</span>' in html_text
    visible = ' '.join(_text_nodes(html_text))
    assert not re.search(r'\b74(?:\.0)?\s*ms', visible) and '78.0–80.0' not in visible
    assert M.CPU_DELTA['total'] == pytest.approx(20.6727423142)
    assert M.CPU_DELTA['update'] + M.CPU_DELTA['render'] == pytest.approx(M.CPU_DELTA['total'], abs=.0001)
    assert 'already inside update' in html_text
    assert 'None retains 12 residents and hides 6 posts' in html_text


def test_the_tail_table_is_the_plans():
    assert len(M.RING_LEN) == M.N_RINGS == 35
    assert M.RING_LEN[0] == pytest.approx(3.75) and M.RING_LEN[-1] == pytest.approx(1.67, abs=0.01)
    assert sum(M.RING_LEN) == pytest.approx(90.0, abs=0.1)
    assert M.RING_WID[0] == pytest.approx(9.0) and M.RING_WID[-1] == pytest.approx(1.4)
    assert len(M.KNOTS) * 3 + len(M.WRAP_VALUES) == 25 and M.BLOCK_CELLS == 40
    assert M.limit_total('ventral') == pytest.approx(910) and M.limit_total('dorsal') == pytest.approx(288.75)


def test_implemented_behavior_and_reference_results_are_distinguished(html_text):
    panels = {p['key']: p for p in M.PANELS}
    grip = ' '.join(c['text'] for c in panels['grip']['claims'] if c['status'] == 'ours')
    assert 'closes from the tip' in grip and 'unwinds before swimming' in grip
    pairs = ' '.join(c['text'] for c in panels['pairs']['claims'] if c['status'] == 'ours')
    assert '12 residents, 6 posts' in pairs
    assert 'rotate through visible pairs' in pairs and 'spot reservations' in pairs
    assert 'different coil heights' in pairs
    assert '1,101' in html_text and '693' in html_text
    reference_claims = [c for c in panels['joints']['claims'] if c.get('chip') == 'reference check (ours)']
    assert len(reference_claims) == 1
    claim = reference_claims[0]
    assert claim['status'] == 'ours' and 'not a device measurement' in claim['text']
    evidence = json.loads((REPO / 'docs/plans/2026-10-16-saltwater-seahorses/evidence/phase3/poses.json').read_text())
    assert len(evidence['poses']) == 7 and evidence['frame_flips'] == 0
    assert evidence['max_limit_use'] * 100 == pytest.approx(95.91)
    assert evidence['wrap_centre_error_mm'] <= .258
    assert '95.91%' in claim['text'] and '0.258 mm' in claim['text']


def test_legend_shows_only_the_chips_used(html_text):
    used = {c['status'] for _a, c in M.all_claims()}
    legend = re.search(r'<div class="legend">(.*?)</div>', html_text).group(1)
    shown = set(re.findall(r'<span class="chip ([\w-]+)">', legend))
    assert shown == used
    assert 'unverified' not in shown


def test_every_source_url_is_in_the_research_document():
    research = RESEARCH.read_text(encoding='utf-8')
    for key, src in M.SOURCES.items():
        assert src['url'] in research, f'{key}: {src["url"]} is not in seahorse-research.md'


def test_every_source_is_cited_and_numbered(html_text):
    order = M.source_order()
    assert set(order) == set(M.SOURCES), 'a source is listed but no claim cites it'
    for i, key in enumerate(order, 1):
        assert f'[{i}] <a href="{M.SOURCES[key]["url"]}">' in html_text


def test_hrefs_are_exactly_the_sources(html_text):
    hrefs = re.findall(r'<a href="([^"]+)"', html_text)
    assert sorted(hrefs) == sorted(s['url'] for s in M.SOURCES.values())
    assert all(h.startswith('https://') for h in hrefs)


def test_no_pending_wording_in_the_html(html_text):
    assert not PENDING.search(' '.join(_text_nodes(html_text)))


# ── committed files are current ──────────────────────────────────────────────
def test_committed_html_and_svgs_are_current(built):
    doc, svgs = built
    assert (POSTER_DIR / 'poster.html').read_text(encoding='utf-8') == doc, 'run make_poster.py'
    for name, svg in svgs.items():
        assert (POSTER_DIR / name).read_text(encoding='utf-8') == svg, f'{name}: run make_poster.py'
    assert len(svgs) == 8


def test_committed_layout_review_fits():
    review = json.loads((POSTER_DIR / 'layout-review.json').read_text())
    assert review['page_mm'] == {'width': 297, 'height': 420}
    assert review['overflowing'] is False and review['fit'] == 'ok'
    assert review['min_font_pt'] >= 8.0


# ── type, contrast, writing rules ────────────────────────────────────────────
def test_nothing_under_8pt(html_text):
    sizes = [float(m) * M.PX_TO_PT for m in re.findall(r'font-size="([\d.]+)"', html_text)]
    for m in re.finditer(r'font-size:([\d.]+)(px|pt)', html_text):
        v = float(m.group(1))
        sizes.append(v * M.PX_TO_PT if m.group(2) == 'px' else v)
    assert len(sizes) > 100
    assert min(sizes) >= 8.0 - 1e-9, min(sizes)


def test_svg_is_drawn_at_one_to_one_scale(html_text):
    found = re.findall(r'<svg [^>]*width="(\d+)" height="(\d+)" viewBox="0 0 (\d+) (\d+)"', html_text)
    assert len(found) == 8
    for w, h, vw, vh in found:
        assert (w, h) == (vw, vh)


def test_text_contrast_is_wcag_aa(built):
    pairs = set(M.TEXT_PAIRS) | set(M.HTML_TEXT_PAIRS)
    assert len(pairs) > 10
    bad = [(fg, bg, round(M.contrast(fg, bg), 2)) for fg, bg in pairs if M.contrast(fg, bg) < 4.5]
    assert bad == []


def test_numbers_keep_their_unit(html_text):
    rx = re.compile(rf'\d {M.UNITS}(?![\w/])')
    assert [t for t in _text_nodes(html_text) if rx.search(t)] == []
    assert '5.7' + NBSP + '±' + NBSP + '0.8' + NBSP + 'ms' in html_text


def test_iso_dates_use_non_breaking_hyphens(html_text):
    text = ' '.join(_text_nodes(html_text))
    assert not re.search(r'\d{4}-\d{2}-\d{2}', text)
    assert '2026‑10‑17' in text and '2026‑10‑16' in text


def test_no_12_hour_clock(html_text):
    assert not re.search(r'\b\d{1,2}(:\d{2})?\s?(am|pm|a\.m\.|p\.m\.)\b', ' '.join(_text_nodes(html_text)), re.I)


def test_html_is_self_contained(html_text):
    assert not re.search(r'<link\b|@import|<script[^>]+src=|<img\b|src="https?:|url\((?!#)', html_text)


# ── the PDF and PNG (fresh export) ───────────────────────────────────────────
@needs_pdf
def test_page_fits(exported):
    _out, review = exported
    assert review['overflowing'] is False and review['fit'] == 'ok', review
    assert all(not p['overflowing'] for p in review['panels'])
    assert not review['header_overflowing']
    assert review['orphaned_header_refs'] == []


@needs_pdf
def test_pdf_is_one_a3_page(exported):
    out, _r = exported
    info = subprocess.run(['pdfinfo', str(out / PDF_NAME)], capture_output=True, text=True, check=True).stdout
    assert re.search(r'^Pages:\s+1$', info, re.M)
    w, h = map(float, re.search(r'Page size:\s+([\d.]+) x ([\d.]+) pts', info).groups())
    assert w == pytest.approx(841.89, abs=1.0) and h == pytest.approx(1190.55, abs=1.0)


@needs_pdf
def test_pdf_fonts_are_embedded(exported):
    out, _r = exported
    rows = subprocess.run(['pdffonts', str(out / PDF_NAME)], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
    assert rows
    for row in rows:
        assert row.split()[-5] == 'yes', row


@needs_pdf
def test_pdf_type_is_at_least_8pt(exported):
    from pypdf import PdfReader
    out, _r = exported
    sizes = []

    def visit(text, cm, tm, font_dict, font_size):
        if text.strip():
            sizes.append(font_size * math.hypot(tm[0], tm[1]) * math.hypot(cm[0], cm[1]))

    PdfReader(str(out / PDF_NAME)).pages[0].extract_text(visitor_text=visit)
    assert len(sizes) > 200
    assert min(sizes) >= 8.0 - 0.05, min(sizes)


@needs_pdf
def test_pdf_links_are_the_sources_and_nothing_else(exported):
    from pypdf import PdfReader
    out, _r = exported
    uris = []
    for a in PdfReader(str(out / PDF_NAME)).pages[0].get('/Annots') or []:
        obj = a.get_object()
        if obj.get('/Subtype') == '/Link' and '/A' in obj:
            uris.append(obj['/A'].get('/URI'))
    want = sorted(s['url'] for s in M.SOURCES.values())
    assert sorted(set(uris)) == want
    assert len(uris) >= len(want)


@needs_pdf
def test_pdf_has_no_pending_wording(exported):
    out, _r = exported
    text = subprocess.run(['pdftotext', str(out / PDF_NAME), '-'], capture_output=True, text=True, check=True).stdout
    assert 'Longsnout seahorse' in text
    assert not PENDING.search(text)


@needs_pdf
def test_pdf_page_edges_are_blank(exported, tmp_path):
    from PIL import Image
    out, _r = exported
    dpi, mm = 150, 5
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile', str(out / PDF_NAME), str(tmp_path / 'edge')], check=True)
    img = Image.open(tmp_path / 'edge.png').convert('L')
    w, h = img.size
    e = round(mm / 25.4 * dpi)
    strips = {'left': (0, 0, e, h), 'right': (w - e, 0, w, h), 'top': (0, 0, w, e), 'bottom': (0, h - e, w, h)}
    assert [n for n, box in strips.items() if img.crop(box).getextrema()[0] < 245] == []


@needs_pdf
def test_png_preview_is_300_dpi_a3(exported):
    from PIL import Image
    out, _r = exported
    im = Image.open(out / 'poster.png')
    w, h = im.size
    assert w == 3508 and abs(h - 4961) <= 3          # Chrome rounds 420 mm to 1191.1 pt: 4963 px at 300 DPI
    assert round(im.info['dpi'][0]) == 300


def test_committed_pdf_matches_the_rules():
    """The committed print file itself: one A3 page, embedded fonts, no pending wording."""
    pdf = POSTER_DIR / PDF_NAME
    assert pdf.exists()
    if not HAVE_POPPLER:
        pytest.skip('needs poppler-utils')
    info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True, check=True).stdout
    assert re.search(r'^Pages:\s+1$', info, re.M) and 'A3' in info
    rows = subprocess.run(['pdffonts', str(pdf)], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
    assert rows and all(r.split()[-5] == 'yes' for r in rows)
    text = subprocess.run(['pdftotext', str(pdf), '-'], capture_output=True, text=True, check=True).stdout
    assert not PENDING.search(text)
