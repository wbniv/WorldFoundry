"""Regression guard for the clownfish biomechanics poster.

Plan: docs/plans/2026-09-30-clownfish-biomechanics-poster.md (Verification steps 2-9)
Data sheet: docs/reference/clownfish-biomechanics-poster/data.py
Generator:  docs/reference/clownfish-biomechanics-poster/make_poster.py

What it pins:
  * every quantity has a status and a source; a `verified` row's source was opened; no URL
    is invented (each one already appears in the repo's docs);
  * every chip agrees with the label in the code's own comment (verified / unverified / ours);
    the check has teeth: a doctored chip is reported;
  * every "ours" value equals the constant it is read from (aquarium_constants.py,
    clownfish.py), recomputed here without going through data.py;
  * the poster's table equals the data sheet, row by row;
  * what the diagrams DRAW matches the formulas: panel B's line slopes and operating point,
    panel C's mean speed, panel D's end points, panel G's overshoot figures;
  * type is at least 8 pt at A3, text contrast is at least 4.5 : 1, numbers keep a
    non-breaking space before their unit, the page fits, the HTML has no external reference;
  * the PDF (built here when Chrome and poppler are present) is one A3 page with embedded fonts
    and one live link per source URL and no other link.

    python3 -m pytest tests/test_poster_clownfish_biomechanics.py -v
"""

from __future__ import annotations

import importlib.util
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
POSTER_DIR = REPO / 'docs' / 'reference' / 'clownfish-biomechanics-poster'
AQ = REPO / 'wflevels' / 'aquarium'
sys.path.insert(0, str(POSTER_DIR))

import data as D  # noqa: E402
import make_poster as M  # noqa: E402

HAVE_PDF_TOOLS = bool(shutil.which('google-chrome') and shutil.which('pdftoppm') and shutil.which('pdfinfo'))
NBSP = ' '


# ── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope='module')
def k():
    return D.constants()


@pytest.fixture(scope='module')
def resolved(k):
    return D.resolve(k)


@pytest.fixture(scope='module')
def built(tmp_path_factory, k, resolved):
    """A fresh build in a temp dir: HTML always, PDF and PNG when Chrome and poppler exist."""
    out = tmp_path_factory.mktemp('poster')
    M.main(['--out-dir', str(out)] + ([] if HAVE_PDF_TOOLS else ['--html-only']))
    return out


@pytest.fixture(scope='module')
def html_text(built):
    return (built / 'poster.html').read_text(encoding='utf-8')


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def code():
    """Independent read of the game's code (a second import, not data.py's)."""
    return (_load('_t_aquarium_constants', AQ / 'aquarium_constants.py'), _load('_t_clownfish', AQ / 'clownfish.py'))


# ── the data sheet ───────────────────────────────────────────────────────────
def test_every_row_has_a_status_and_a_source(resolved):
    assert len(resolved) >= 40
    for r in resolved:
        assert r['status'] in D.STATUSES, r['id']
        assert r['sources'], f"{r['id']}: no source"
        for s in r['sources']:
            assert s == D.GAME or s in D.SOURCES, f"{r['id']}: unknown source {s}"


def test_verified_rows_rest_on_opened_sources_with_a_url(resolved):
    for r in resolved:
        if r['status'] == 'verified':
            for s in r['sources']:
                assert D.SOURCES[s]['opened'], f"{r['id']}: {s} was not opened"
                assert D.SOURCES[s]['url'], f"{r['id']}: verified row without a source URL ({s})"


def test_the_checked_status_of_each_source():
    """2026-10-06 source audit; unsupported amplitude/wavelength became authored choices."""
    opened = {k for k, v in D.SOURCES.items() if v['opened']}
    assert opened == {'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'}
    assert 'S9' not in D.SOURCES
    assert 'cetacean' not in ' '.join(v['cite'].lower() for v in D.SOURCES.values())   # Rohr & Fish is not a source


def test_no_invented_urls():
    """A URL may only appear if the repo already holds it (plans, code comments, docs)."""
    corpus = ''
    for pattern in ('docs/plans/*.md', 'docs/*.md', 'docs/reference/*.md'):
        for f in REPO.glob(pattern):
            corpus += f.read_text(encoding='utf-8', errors='ignore')
    for f in AQ.glob('*.py'):
        corpus += f.read_text(encoding='utf-8', errors='ignore')
    for key, src in D.SOURCES.items():
        if src['url']:
            assert src['url'] in corpus, f'{key}: {src["url"]} is not in the repo'


def test_chips_agree_with_the_code_comments(resolved):
    assert D.label_problems(resolved) == []


def test_the_label_check_has_teeth(resolved, monkeypatch):
    """A doctored chip must be reported: an unopened source called verified, a code-comment
    `ours` called verified, and a verified label the code never gave."""
    monkeypatch.setitem(D.SOURCES, 'S6', dict(D.SOURCES['S6'], opened=False))
    bad = [dict(r) for r in resolved]
    for r in bad:
        if r['id'] == 'f_cap':
            r['status'] = 'verified'                   # code says ours; source is the game
        if r['id'] == 'a_over_l':
            r['status'] = 'verified'                   # code says ours; source is the game
        if r['id'] == 'const_cycle':
            r['status'] = 'verified'                   # simulate an unopened source
    problems = ' | '.join(D.label_problems(bad))
    assert 'f_cap' in problems and 'a_over_l' in problems and 'const_cycle' in problems


def test_verified_is_never_inherited_from_a_neighbouring_line():
    """A label-less line may inherit `ours`/`unverified` from above, but never `verified`."""
    for r in D.resolve():
        c = r['code']
        if c and c['how'].startswith('inherited'):
            assert 'verified' not in c['labels']


def test_symbols_without_a_code_label_are_chipped_ours(resolved):
    for rid, sym, where in D.unlabelled(resolved):
        row = next(r for r in resolved if r['id'] == rid)
        assert row['status'] == 'ours', f'{rid} ({sym} at {where}) has no label in the code'


# ── "ours" values equal the code ─────────────────────────────────────────────
def _raw(code, symbol):
    C, F = code
    if symbol.startswith('aquarium_constants.'):
        return getattr(C, symbol.split('.', 1)[1].split(' ')[0])
    if symbol.startswith('clownfish.TUNABLES:'):
        name = symbol.split(':', 1)[1]
        return next(v for n, v, _u, _n in F.TUNABLES if n == name)
    raise KeyError(symbol)


def test_ours_values_equal_the_constants_they_are_read_from(resolved, code):
    checked = 0
    for r in resolved:
        if r['symbol'] and r['factor'] is not None:
            want = _raw(code, r['symbol']) * r['factor']
            assert r['value'] == pytest.approx(want, rel=1e-9), r['id']
            checked += 1
    assert checked >= 30


def test_derived_values_recomputed_from_the_module(resolved, code):
    C, F = code
    by = {r['id']: r for r in resolved}
    T = {n: v for n, v, _u, _n in F.TUNABLES}
    dt = float(re.search(r'^DT\s*=\s*([0-9.]+)', (AQ / 'run_aquarium_checks.py').read_text(), re.M).group(1))
    tail_app = T['fish-tail-app']
    assert by['tick']['value'] == pytest.approx(1 / dt)
    f_v = min(T['fish-strouhal'] * C.SWIM_SPEED / tail_app, T['fish-tail-hz-max'])
    assert by['f_cruise']['value'] == pytest.approx(f_v)
    rig = F.RigState()
    rig.speed = C.SWIM_SPEED
    assert by['f_cruise']['value'] == pytest.approx(rig.tail_hz())
    assert by['st_dart']['value'] == pytest.approx(T['fish-tail-hz-max'] * tail_app / C.DART_SPEED)
    assert by['uturn']['value'] == pytest.approx(C.SWIM_SPEED / (2 * math.pi * C.YAW_WMAX))
    assert by['a_over_l']['value'] == pytest.approx(tail_app / C.L_M)
    assert by['a_over_l']['value'] == pytest.approx(0.2, abs=0.005)
    assert C.BURST_SPEED / C.SWIM_SPEED == pytest.approx(1.309)
    assert by['burst_v']['disp'].endswith('(1.309' + NBSP + 'V)')


def test_pectoral_range_is_the_verified_one(resolved):
    by = {r['id']: r for r in resolved}
    assert (by['pec_lo']['value'], by['pec_hi']['value']) == (2.4, 4.6)
    assert by['pec_lo']['status'] == by['pec_hi']['status'] == 'verified'
    assert by['pec_alt']['status'] == by['pec_sync']['status'] == by['hale']['status'] == 'other-species'


def test_the_strouhal_window_is_verified_and_the_game_value_is_ours(resolved):
    by = {r['id']: r for r in resolved}
    assert by['st_window']['value'] == (0.2, 0.4) and by['st_window']['status'] == 'verified'
    assert by['st_game']['status'] == 'ours' and 0.2 <= by['st_game']['value'] <= 0.4
    assert by['a_over_l']['status'] == by['wavelength']['status'] == 'ours'
    assert by['const_cycle']['status'] == 'other-species'
    assert by['st_trout']['value'] == (0.19, 0.23)


# ── the table equals the data sheet ──────────────────────────────────────────
def _text(fragment):
    return re.sub(r'<[^>]+>', '', fragment).replace('&amp;', '&')


def test_table_equals_the_data_sheet(html_text, resolved):
    rows = re.findall(r'<tr data-id="([^"]+)" data-status="([^"]+)"><td class="q">(.*?)</td><td class="v">(.*?)</td><td class="c">(.*?)</td></tr>', html_text)
    assert [r[0] for r in rows] == [r['id'] for r in resolved]
    for (rid, status, q, v, c), r in zip(rows, resolved):
        assert status == r['status']
        assert M.polish_text(_text(q)) == M.polish_text(r['quantity']), rid
        assert _text(v) == M.polish_text(r['disp']), rid
        assert D.STATUS_TEXT[r['status']] in _text(c), rid
        for s in r['sources']:
            if s != D.GAME:
                assert s in _text(c), rid


def test_no_row_without_a_chip(html_text):
    n_rows = len(re.findall(r'<tr data-id=', html_text))
    n_chips = len(re.findall(r'<td class="c"><span class="chip ', html_text))
    assert n_rows == n_chips >= 40


# ── the diagrams draw the formulas ───────────────────────────────────────────
def _plot(html_text, pid):
    m = re.search(rf'<g id="{pid}" data-x0="([\d.]+)" data-y0="([\d.]+)" data-w="([\d.]+)" data-h="([\d.]+)" data-xmax="([\d.]+)" data-ymax="([\d.]+)">', html_text)
    assert m, pid
    x0, y0, w, h, xm, ym = map(float, m.groups())
    return (lambda X: (X - x0) / w * xm), (lambda Y: (y0 - Y) / h * ym)


def _points(html_text, tag_id):
    m = re.search(rf'id="{tag_id}" points="([^"]+)"', html_text)
    assert m, tag_id
    return [tuple(map(float, p.split(','))) for p in m.group(1).split()]


def test_panel_b_slopes_and_operating_point(html_text, k):
    ux, fy = _plot(html_text, 'plot-b')
    a = k.a_over_l
    for st in (0.2, 0.3, 0.4):
        m = re.search(rf'id="b-st-{st}" data-st="{st}" x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"', html_text)
        x1, y1, x2, y2 = map(float, m.groups())
        slope = (fy(y2) - fy(y1)) / (ux(x2) - ux(x1))
        assert slope == pytest.approx(st / a, rel=0.01), st            # f = St·U/A, U in BL/s: slope St / (A/L)
    op = re.search(r'id="b-op" data-u="([\d.]+)" data-f="([\d.]+)" cx="([\d.]+)" cy="([\d.]+)"', html_text)
    u, f, cx, cy = map(float, op.groups())
    assert u == pytest.approx(k.V / k.L, rel=1e-3) and f == pytest.approx(k.rig.tail_hz(), rel=1e-3)
    assert ux(cx) == pytest.approx(u, rel=0.01) and fy(cy) == pytest.approx(f, rel=0.01)
    game = [(ux(x), fy(y)) for x, y in _points(html_text, 'b-game')]
    assert max(f for _u, f in game) == pytest.approx(k.f_cap, rel=1e-3)             # the cap
    u_knee = next(u for u, f in game if f >= k.f_cap - 1e-3)
    assert u_knee == pytest.approx(k.f_cap * k.a_over_l / k.st, abs=0.11)            # where St·U/A reaches the cap
    assert k.f_cap < k.tick_hz / 2                                                   # under the Nyquist line drawn


def test_panel_c_mean_speed_is_the_cruise_speed(html_text, k):
    tx, vy = _plot(html_text, 'plot-c')
    pts = [(tx(x), vy(y)) for x, y in _points(html_text, 'c-speed')]
    cyc = k.C.GAIT_CYCLE
    last = [v for t, v in pts if t > 3 * cyc + 1e-6]           # the final cycle, sampled per tick
    assert len(last) == int(round(cyc / k.dt))
    mean = sum(last) / len(last)
    assert mean == pytest.approx(k.V / k.L, rel=0.01)           # 3.43 BL/s within 1 %
    line = float(re.search(r'id="c-mean" data-bl="([\d.]+)"', html_text).group(1))
    assert line == pytest.approx(k.V / k.L, rel=0.01)
    assert max(v for _t, v in pts) * k.L == pytest.approx(3.87, abs=0.15)             # the burst peak stays near 3.9 m/s
    assert max(v for _t, v in pts) * k.L < k.C.BURST_SPEED


def test_panel_d_end_points(html_text, k):
    ux, fy = _plot(html_text, 'plot-d')
    pts = [(ux(x), fy(y)) for x, y in _points(html_text, 'd-beat')]
    assert pts[0] == pytest.approx((0.0, 2.4), abs=0.02)
    assert pts[1][1] == pytest.approx(4.6, abs=0.02)
    assert pts[1][0] == pytest.approx(k.T['fish-pec-v-hi'] / k.L, abs=0.02)


def _ode_peak(zeta, dt=1e-4, t_end=10.0):
    x = v = 0.0
    peak = 0.0
    for _ in range(int(t_end / dt)):
        v += (1 - x - 2 * zeta * v) * dt
        x += v * dt
        peak = max(peak, x)
    return peak - 1.0


def test_panel_g_overshoot_figures(html_text, k):
    tx, ry = _plot(html_text, 'plot-g')
    curves = re.findall(r'<polyline data-zeta="([\d.]+)" points="([^"]+)"', html_text)
    zetas = sorted(float(z) for z, _ in curves)
    assert zetas == sorted([0.3, 0.6, 1.0, 1.5, k.C.YAW_ZETA, k.C.PITCH_ZETA])
    for z, pts in curves:
        z = float(z)
        drawn = max(ry(float(p.split(',')[1])) for p in pts.split()) - 1.0
        formula = math.exp(-math.pi * z / math.sqrt(1 - z * z)) if z < 1 else 0.0
        assert max(drawn, 0.0) == pytest.approx(formula, abs=0.004), z
        if z in (0.3, 0.6, k.C.YAW_ZETA, k.C.PITCH_ZETA):
            assert _ode_peak(z) == pytest.approx(formula, abs=0.004), z             # the ODE itself agrees
    assert re.search(r'ζ = 0\.3: 37\s%\sovershoot', html_text.replace(NBSP, ' '))


# ── type, contrast, writing rules ────────────────────────────────────────────
def test_nothing_under_8pt(html_text):
    sizes = []
    for m in re.finditer(r'font-size="([\d.]+)"', html_text):
        sizes.append(float(m.group(1)) * M.PX_TO_PT)                    # the SVGs draw at 1:1 CSS px
    for m in re.finditer(r'font-size:([\d.]+)(px|pt)', html_text):
        v = float(m.group(1))
        sizes.append(v * M.PX_TO_PT if m.group(2) == 'px' else v)
    assert len(sizes) > 100
    assert min(sizes) >= 8.0 - 1e-9, min(sizes)
    assert all(px >= M.MIN_PX for px in M.TEXT_SIZES)


def test_svg_is_drawn_at_one_to_one_scale(html_text):
    for m in re.finditer(r'<svg [^>]*width="(\d+)" height="(\d+)" viewBox="0 0 (\d+) (\d+)"', html_text):
        assert m.group(1) == m.group(3) and m.group(2) == m.group(4)


def test_text_contrast_is_wcag_aa(html_text):
    pairs = set(M.TEXT_PAIRS) | set(M.HTML_TEXT_PAIRS)
    assert len(pairs) > 15
    bad = [(fg, bg, round(M.contrast(fg, bg), 2)) for fg, bg in pairs if M.contrast(fg, bg) < 4.5]
    assert bad == []


def _text_nodes(html_text):
    out, skip = [], False
    for part in re.split(r'(<[^>]*>)', html_text):
        if part.startswith('<'):
            low = part.lower()
            skip = low.startswith(('<style', '<script')) or (skip and not low.startswith(('</style', '</script')))
        elif not skip:
            out.append(part)
    return out


def test_numbers_keep_their_unit(html_text):
    rx = re.compile(rf'\d {M.UNITS}(?![\w/])')
    offenders = [t for t in _text_nodes(html_text) if rx.search(t)]
    assert offenders == []


def test_iso_dates_use_non_breaking_hyphens(html_text):
    text = ' '.join(_text_nodes(html_text))
    assert not re.search(r'\d{4}-\d{2}-\d{2}', text)
    assert '2026‑09‑30' in text


def test_no_12_hour_clock(html_text):
    assert not re.search(r'\b\d{1,2}(:\d{2})?\s?(am|pm|a\.m\.|p\.m\.)\b', ' '.join(_text_nodes(html_text)), re.I)


def test_html_is_self_contained(html_text):
    assert not re.search(r'<link\b|@import|<script[^>]+src=|<img\b|src="https?:|url\((?!#)', html_text)
    assert not re.search(r'font-family:[^;}]*\bsystem-ui', html_text)


def test_missing_links_are_marked(html_text):
    n_missing = sum(1 for s in D.SOURCES.values() if not s['url'])
    assert n_missing == 0  # all eight remaining references have checked links
    assert html_text.count('class="missing"') == n_missing


def test_hrefs_are_exactly_the_data_sheet_urls(html_text):
    hrefs = re.findall(r'<a href="([^"]+)"', html_text)
    assert sorted(hrefs) == sorted(s['url'] for s in D.SOURCES.values() if s['url'])


def test_page_fits(built):
    if not shutil.which('google-chrome'):
        pytest.skip('no chrome')
    dom = subprocess.run(['google-chrome', '--headless=new', '--no-sandbox', '--disable-gpu', f'--user-data-dir={built / "prof"}',
                          '--dump-dom', (built / 'poster.html').as_uri()], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r'data-fit="(\w+)" data-over="(-?[\d.]+)"', dom)
    assert m, 'the fit script did not run'
    assert m.group(1) == 'ok', f'content overflows the page by {m.group(2)} px'


def test_committed_html_is_current(html_text):
    """poster.html in the repo must be what the generator makes now (stale = a constant changed)."""
    committed = POSTER_DIR / 'poster.html'
    assert committed.exists(), 'run: task poster-clownfish-biomechanics'
    assert committed.read_text(encoding='utf-8') == html_text


# ── the PDF ──────────────────────────────────────────────────────────────────
needs_pdf = pytest.mark.skipif(not HAVE_PDF_TOOLS, reason='needs google-chrome and poppler-utils')


@needs_pdf
def test_pdf_is_one_a3_page(built):
    out = subprocess.run(['pdfinfo', str(built / 'clownfish-biomechanics-a3.pdf')], capture_output=True, text=True, check=True).stdout
    assert re.search(r'^Pages:\s+1$', out, re.M)
    w, h = map(float, re.search(r'Page size:\s+([\d.]+) x ([\d.]+) pts', out).groups())
    assert w == pytest.approx(841.9, abs=1.0) and h == pytest.approx(1190.6, abs=1.0)     # Chrome rounds 420 mm to 1191.1 pt


@needs_pdf
def test_pdf_fonts_are_embedded(built):
    if not shutil.which('pdffonts'):
        pytest.skip('no pdffonts')
    out = subprocess.run(['pdffonts', str(built / 'clownfish-biomechanics-a3.pdf')], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
    assert out
    for line in out:
        cols = line.split()
        emb = cols[-5]                                   # the `emb` column; names may hold no spaces
        assert emb == 'yes', line


@needs_pdf
def test_pdf_links_are_the_sources_and_nothing_else(built):
    from pypdf import PdfReader
    reader = PdfReader(str(built / 'clownfish-biomechanics-a3.pdf'))
    uris = []
    for a in reader.pages[0].get('/Annots') or []:
        obj = a.get_object()
        if obj.get('/Subtype') == '/Link' and '/A' in obj:
            uris.append(obj['/A'].get('/URI'))
    want = sorted(s['url'] for s in D.SOURCES.values() if s['url'])
    assert sorted(set(uris)) == want
    assert len(uris) >= len(want)


@needs_pdf
def test_pdf_type_is_at_least_8pt(built):
    from pypdf import PdfReader
    sizes = []

    def visit(text, cm, tm, font_dict, font_size):
        if text.strip():
            a = math.hypot(tm[0], tm[1]) * math.hypot(cm[0], cm[1])
            sizes.append(font_size * a)

    PdfReader(str(built / 'clownfish-biomechanics-a3.pdf')).pages[0].extract_text(visitor_text=visit)
    assert len(sizes) > 200
    assert min(sizes) >= 8.0 - 0.05, min(sizes)


@needs_pdf
def test_png_preview_exists(built):
    from PIL import Image
    w, h = Image.open(built / 'poster.png').size
    assert (w, h) == (1754, 2482)                          # A3 at 150 dpi


def _edge_strips_are_blank(pdf, workdir, mm=5, dpi=150):
    """Names of the page edges whose outer `mm` strip has anything but white in it, in a render of `pdf`."""
    from PIL import Image
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', str(pdf), str(workdir / 'edge')], check=True)
    img = Image.open(next(workdir.glob('edge*.png'))).convert('L')
    w, h = img.size
    e = round(mm / 25.4 * dpi)
    strips = {'left': (0, 0, e, h), 'right': (w - e, 0, w, h), 'top': (0, 0, w, e), 'bottom': (0, h - e, w, h)}
    return [name for name, box in strips.items() if img.crop(box).getextrema()[0] < 245]


@needs_pdf
def test_pdf_page_edges_are_blank(built, tmp_path):
    """Nothing may be drawn in the outer 5 mm of the page. (A hero fish icon once overflowed the header and left
    a 0.7 mm sliver of its nose at the right edge of the PDF, invisible in the HTML but there in the print.)"""
    assert _edge_strips_are_blank(built / 'clownfish-biomechanics-a3.pdf', tmp_path) == []
