"""Regression guard for the Gulf of Thailand reef poster.

Plan:      docs/plans/2026-11-02-gulf-of-thailand-reef-tank.md (Phase 0; Verification steps 1, 2 and 13)
Research:  docs/reference/thai-reef-research.md (written first; the poster prints only from it)
Generator: docs/reference/gulf-of-thailand-reef-poster/make_poster.py, export_poster.py

What it pins:
  * every printed claim is verified, other region or ours; nothing unverified prints; every
    verified / other-region claim names a source; the build refuses an unverified claim;
  * every species printed is in the research document's Final species list, and no species
    the research dropped or swapped out is printed;
  * the legend shows exactly the chips that are used;
  * every source URL is one the research document already holds (no invented links);
  * the committed poster.html and SVG panels are what the generator makes now;
  * type is at least 8 pt, text contrast at least 4.5 : 1, numbers keep a non-breaking space
    before their unit, ISO dates use non-breaking hyphens, the HTML has no external reference;
  * the PDF (built here with Playwright when available) is one A3 page, every font embedded,
    type at least 8 pt, nothing in the outer 5 mm, the page fits, one link per source and no
    other link, and no pending-verification wording;
  * the PNG preview is 300 DPI A3.

    python3 -m pytest tests/test_poster_gulf_of_thailand_reef.py -v
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
POSTER_DIR = REPO / 'docs' / 'reference' / 'gulf-of-thailand-reef-poster'
RESEARCH = REPO / 'docs' / 'reference' / 'thai-reef-research.md'
PDF_NAME = 'gulf-of-thailand-reef-a3.pdf'
NBSP = ' '
PENDING = re.compile(r'unverified|not opened|link missing|pending|to verify|verify in phase', re.I)
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
    out = tmp_path_factory.mktemp('reef-poster')
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


def _final_species_table():
    """Rows of the research document's "Final species list" table: {printed name: decision}."""
    text = RESEARCH.read_text(encoding='utf-8')
    section = text.split('## Final species list', 1)[1].split('\n## ', 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 4 and cells[0] not in ('#', '') and not set(cells[0]) <= set('-: '):
            rows[cells[2].replace('*', '').strip()] = cells[3].replace('*', '')
    return rows


# ── claims and sources ───────────────────────────────────────────────────────
def test_every_claim_is_printable_and_sourced():
    assert M.check_claims() == []
    for area, c in M.all_claims():
        assert c['status'] in M.PRINTABLE, (area, c['text'])
        if c['status'] != 'ours':
            assert c['src'], (area, c['text'])


def test_the_build_refuses_an_unverified_claim(monkeypatch):
    card = M.CARDS[0]
    bad = dict(card['claims'][0], status='unverified')
    monkeypatch.setitem(card, 'claims', [bad] + card['claims'][1:])
    assert any('may not print' in p for p in M.check_claims())
    with pytest.raises(SystemExit):
        M.build()


def test_a_verified_claim_needs_a_known_source(monkeypatch):
    monkeypatch.setitem(M.HABITAT[0], 'status', 'verified')
    monkeypatch.setitem(M.HABITAT[0], 'src', [])
    assert any('without a source' in p for p in M.check_claims())
    monkeypatch.setitem(M.HABITAT[0], 'src', ['no-such-source'])
    assert any('unknown source' in p for p in M.check_claims())


def test_dropped_taxon_cannot_be_printed(monkeypatch, tmp_path):
    research = tmp_path / 'research.md'
    rows = ['| # | Kind | Species | Decision |']
    for i in range(1, 25):
        rows.append(f'| {i} | Kind | Taxon {i} | yes |')
    rows[1] = '| 1 | Kind | Spirobranchus sp. | dropped |'
    research.write_text('## Final species list\n' + '\n'.join(rows), encoding='utf-8')
    monkeypatch.setattr(M, 'RESEARCH', research)
    assert any('Spirobranchus sp.: not approved' in p for p in M.check_claims())


def test_export_refuses_unverified_research_even_if_old_html_exists(tmp_path):
    (tmp_path / 'poster.html').write_text('<html>stale draft</html>', encoding='utf-8')
    with pytest.raises(SystemExit, match='poster claims incomplete'):
        E.export(tmp_path)
    assert not (tmp_path / PDF_NAME).exists()


def test_final_roster_requires_all_roles_and_sources(monkeypatch, tmp_path):
    research = tmp_path / 'research.md'
    research.write_text('## Final species list\n| 1 | Kind | Taxon | yes |\n', encoding='utf-8')
    monkeypatch.setattr(M, 'RESEARCH', research)
    problems = M.check_claims()
    assert any('must decide all 22 numbered roles' in p for p in problems)
    assert any('roster row 1 has no linked Gulf source' in p for p in problems)


def test_fifteen_cards_seven_move_seven_build_one_guard():
    kinds = [c['kind'] for c in M.CARDS]
    assert len(M.CARDS) == 15
    assert kinds.count('moves') == 7 and kinds.count('builds') == 7 and kinds.count('guards') == 1
    for card in M.CARDS:
        assert [c['role'] for c in card['claims']] == ['gulf', 'eats', 'defends', 'tank'], card['name']
        assert card['claims'][0]['status'] == 'verified', card['name']      # the Gulf record itself
        assert card['claims'][3]['status'] == 'ours', card['name']


def test_seven_habitat_facts_and_two_fishes():
    assert len(M.HABITAT) == 7
    assert [f['key'] for f in M.FISHES] == ['humbug', 'boxfish']
    for fish in M.FISHES:
        gulf = [c for c in fish['claims'] if c.get('role') == 'gulf']
        assert len(gulf) == 1 and gulf[0]['status'] == 'verified', fish['key']


def test_dropped_species_are_absent():
    assert 'Linckia laevigata' not in M.printed_taxa()
    assert 'Polycarpa aurata' not in M.printed_taxa()
    assert not any(c['draw'] in ('star', 'squirt') for c in M.CARDS)
    assert 'Holothuria atra' not in M.printed_taxa()
    assert not any(c['draw'] == 'cuke' for c in M.CARDS)


def test_review_draft_does_not_bypass_claim_validation(monkeypatch):
    html, _ = M.build(draft=True)
    assert 'REVIEW DRAFT' in html and 'not approved for print' in html
    assert 'poster visual review is incomplete' in M.check_claims()
    with pytest.raises(SystemExit, match='poster visual review is incomplete'):
        M.build()
    monkeypatch.setitem(M.CARDS[0]['claims'][1], 'status', 'unverified')
    with pytest.raises(SystemExit, match='unverified'):
        M.build(draft=True)


def test_map_labels_bangkok_as_a_city():
    svg = M.render.habitat_map([('Ko Tao', 99.84, 10.1, 'r')])
    assert 'Bangkok' in svg and 'Ko Tao' in svg
    assert 'fill="#ad4a2e"' in svg  # administrative outline
    assert svg.count('Bangkok') == 1  # label on the main map only


def test_printed_species_are_the_final_list():
    rows = _final_species_table()
    assert rows, 'thai-reef-research.md has no Final species list table'
    swapped_in = {m.group(1).strip() for d in rows.values()
                  for m in [re.match(r'swapped to \*?([^*;(]+)\*?', d, re.I)] if m}
    for taxon in M.printed_taxa():
        if taxon in rows:
            assert rows[taxon].lower().startswith('yes'), (taxon, rows[taxon])
        else:
            assert taxon in swapped_in, f'{taxon} is printed but not in the Final species list'
    dropped = [k for k, d in rows.items() if d.lower().startswith(('dropped', 'swapped'))]
    for taxon in dropped:
        assert taxon not in M.printed_taxa(), f'{taxon} was dropped or swapped out but is printed'


def test_legend_shows_only_the_chips_used(html_text):
    used = {c['status'] for _a, c in M.all_claims()}
    legend = re.search(r'<div class="legend">(.*?)</div>', html_text).group(1)
    shown = set(re.findall(r'<span class="chip ([\w-]+)">', legend))
    assert shown == used
    assert 'unverified' not in shown


def test_every_source_url_is_in_the_research_document():
    research = RESEARCH.read_text(encoding='utf-8')
    for key, src in M.SOURCES.items():
        assert src['url'] in research, f'{key}: {src["url"]} is not in thai-reef-research.md'


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
    assert len(svgs) >= 4


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
    assert len(sizes) > 20
    assert min(sizes) >= 8.0 - 1e-9, min(sizes)


def test_svg_text_is_drawn_at_one_to_one_scale(html_text):
    """Panels that carry text are not scaled, so their font sizes are the printed sizes."""
    found = re.findall(r'<svg [^>]*width="(\d+)" height="(\d+)" viewBox="0 0 (\d+) (\d+)"[^>]*>(.*?)</svg>', html_text, re.S)
    assert found
    for w, h, vw, vh, inner in found:
        if '<text' in inner:
            assert (w, h) == (vw, vh)


def test_text_contrast_is_wcag_aa(built):
    pairs = set(M.TEXT_PAIRS) | set(M.HTML_TEXT_PAIRS)
    assert len(pairs) > 6
    bad = [(fg, bg, round(M.contrast(fg, bg), 2)) for fg, bg in pairs if M.contrast(fg, bg) < 4.5]
    assert bad == []


def test_numbers_keep_their_unit(html_text):
    rx = re.compile(rf'\d {M.UNITS}(?![\w/])')
    assert [t for t in _text_nodes(html_text) if rx.search(t)] == []


def test_iso_dates_use_non_breaking_hyphens(html_text):
    text = ' '.join(_text_nodes(html_text))
    assert not re.search(r'\d{4}-\d{2}-\d{2}', text)
    assert '2026‑11‑02' in text


def test_no_12_hour_clock(html_text):
    assert not re.search(r'\b\d{1,2}(:\d{2})?\s?(am|pm|a\.m\.|p\.m\.)\b', ' '.join(_text_nodes(html_text)), re.I)


def test_html_is_self_contained(html_text):
    assert not re.search(r'<link\b|@import|<script[^>]+src=|src="https?:|url\(["\']?https?:', html_text)
    assert all(s.startswith('data:') for s in re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', html_text))


# ── the PDF and PNG (fresh export) ───────────────────────────────────────────
@needs_pdf
def test_page_fits(exported):
    _out, review = exported
    assert review['overflowing'] is False and review['fit'] == 'ok', review
    assert all(not p['overflowing'] for p in review['panels'])


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
    assert 'Reef of the Gulf of Thailand' in text
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
