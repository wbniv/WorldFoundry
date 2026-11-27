"""The lava lamp A3 poster (docs/reference/lava-lamp-poster/): its claims, its sources, its numbers, its page.

Plan:      docs/plans/2026-11-26-lava-lamp.md (D10, Q7, Q8, Phase P; verification step 10)
Research:  docs/reference/lava-lamp-research.md (written first; the poster prints only what it supports)
Generator: docs/reference/lava-lamp-poster/make_poster.py, export_poster.py, make_qr.py, render_hero.py

What it pins:
  * every printed claim is verified, other source or ours; a verified or other-source claim names a source, an ours
    claim names what computes it; every source's link and every patent's link is already in the research document;
  * the visual-review gate: until the research says "Poster visual review: approved" the build refuses, and only a
    marked review draft builds (the reef poster's gate);
  * the committed poster.html, its SVG drawings and its QR codes are what the generators make now;
  * the model's numbers and the Forth words on the page are the level's: the words are found in the shipped .lev;
  * no status tag is printed (Will, 2026-11-27): a sourced sentence ends in superscript source numbers;
  * the Forth is pretty-printed, each level cell number shown by its lamp.py name; mapping the names back gives the
    shipped script, whitespace aside;
  * type is at least 8 pt, SVG text contrast at least 4.5 : 1, numbers keep a non-breaking space before their unit,
    ISO dates use non-breaking hyphens, no 12-hour clock, nothing external, links are the sources and the patents;
  * the exported layout fits one A3 page and the PDF is one 297 x 420 mm page (skipped until exported).

    scripts/in-linux-container.sh python3 -m pytest tests/test_lava_lamp_poster.py -q
"""
import html as htmllib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
POSTER = ROOT / "docs" / "reference" / "lava-lamp-poster"
RESEARCH = ROOT / "docs" / "reference" / "lava-lamp-research.md"
LEV = ROOT / "wflevels" / "lava_lamp" / "lava_lamp.lev"
HTML = POSTER / "poster.html"
NBSP, NBHY = " ", "‑"

spec = importlib.util.spec_from_file_location("make_poster_lava", POSTER / "make_poster.py")
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)
sys.path.insert(0, str(POSTER))
import make_qr  # noqa: E402

APPROVED = mp.APPROVED_LINE in RESEARCH.read_text(encoding="utf-8")


def claim_problems():
    return [p for p in mp.check_claims() if p != mp.REVIEW_PROBLEM]


def text_nodes(doc):
    out, skip = [], False
    for part in re.split(r"(<[^>]*>)", doc):
        if part.startswith("<"):
            low = part.lower()
            skip = low.startswith(("<style", "<script", "<svg", "<pre")) or (
                skip and not low.startswith(("</style", "</script", "</svg", "</pre")))
        elif not skip:
            out.append(htmllib.unescape(part))
    return out


@pytest.fixture(scope="module")
def built():
    return mp.build(draft=not APPROVED)


@pytest.fixture(scope="module")
def page_text(built):
    return re.sub(r"\s+", " ", " ".join(text_nodes(built[0]))).replace(NBSP, " ").replace(NBHY, "-")


# ── claims, sources, the gate ────────────────────────────────────────────────
def test_every_claim_is_printable_and_traceable():
    assert claim_problems() == []
    for area, c in mp.all_claims():
        assert c["status"] in mp.PRINTABLE, area
        if c["status"] in ("verified", "other-source"):
            assert c["src"], (area, c["text"][:40])
        if c["status"] == "ours":
            assert c.get("by"), (area, c["text"][:40])


def test_every_source_is_cited_and_is_in_the_research():
    research = RESEARCH.read_text(encoding="utf-8")
    assert set(mp.source_order()) == set(mp.SOURCES)
    for key, s in mp.SOURCES.items():
        assert s["url"].startswith("https://"), key
        assert s["url"] in research, key


def test_the_build_refuses_what_it_should(monkeypatch):
    def with_claim(c):
        monkeypatch.setattr(mp, "HEADER_CLAIMS", mp.HEADER_CLAIMS[:1] + [c])
        return claim_problems()
    assert any("cannot be printed" in p for p in with_claim(dict(status="unverified", src=["lava"], text="a claim nobody confirmed")))
    assert any("needs a source" in p for p in with_claim(dict(status="verified", src=[], text="no source")))
    assert any("must name what computes it" in p for p in with_claim(dict(status="ours", src=[], text="no script")))
    assert any("unknown source" in p for p in with_claim(dict(status="verified", src=["nope"], text="bad source")))
    monkeypatch.setitem(mp.SOURCES, "lava", dict(mp.SOURCES["lava"], url="https://example.org/invented"))
    assert any("not in the research document" in p for p in claim_problems())


def test_the_visual_review_gate():
    research = RESEARCH.read_text(encoding="utf-8")
    assert re.search(r"^Poster visual review: (approved|pending)", research, re.M), "the research must record the review"
    draft_doc, _ = mp.build(draft=True)
    assert 'data-draft="1"' in draft_doc and "REVIEW DRAFT" in draft_doc
    if APPROVED:
        assert 'data-draft="1"' not in HTML.read_text(encoding="utf-8")
    else:
        assert mp.REVIEW_PROBLEM in mp.check_claims()
        with pytest.raises(SystemExit, match="refusing to build"):
            mp.build()


# ── the committed files are the generators' output ───────────────────────────
def test_committed_html_and_drawings_reproduce(built):
    doc, svgs = built
    assert HTML.exists(), "run make_poster.py" + ("" if APPROVED else " --draft")
    assert HTML.read_text(encoding="utf-8") == doc, "poster.html is stale: rerun make_poster.py"
    for name, svg in svgs.items():
        assert (POSTER / name).read_text(encoding="utf-8") == svg + "\n", name


def test_qr_codes_are_the_patent_links():
    for p in mp.PATENTS:
        assert (POSTER / "qr" / f"{p['key']}.svg").exists(), p["key"]
    if importlib.util.find_spec("segno") is None:
        pytest.skip("segno not installed: the committed QR codes are not regenerated here")
    for p in mp.PATENTS:
        assert (POSTER / "qr" / f"{p['key']}.svg").read_text(encoding="ascii") == make_qr.qr_svg(p["url"]) + "\n", p["key"]


def test_patents_are_the_researched_ones(built):
    research = RESEARCH.read_text(encoding="utf-8")
    doc = built[0]
    assert len(mp.PATENTS) == 6
    for p in mp.PATENTS:
        assert p["url"] in research and p["number"] in research, p["number"]
        assert f'href="{p["url"]}"' in doc, p["number"]
        for d in re.findall(r"\d{4}-\d{2}-\d{2}", p["dates"]):
            assert d.replace("-", NBHY) in research, (p["number"], d)


def test_the_hero_is_the_committed_render(built):
    import base64
    png = (POSTER / "hero-cycles.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert base64.b64encode(png).decode("ascii") in built[0]


# ── the level's numbers and Forth ────────────────────────────────────────────
def test_printed_numbers_are_the_model(page_text):
    char = mp.MODEL.character()
    for needle in (f"{mp.MODEL.N_BLOBS} blobs spend {char['pooled'] * 100:.0f} %", f"{char['resting'] * 100:.0f} % resting",
                   f"{char['moving'] * 100:.0f} % moving", f"about {char['cycle']:.0f} s",
                   f"{mp.MODEL.WARM_STEPS * float(mp.MODEL.DT):.0f} s warm-up", f"at most {mp.MODEL.MAX_STEPS}"):
        assert needle in page_text, needle


def test_the_forth_on_the_poster_is_the_shipped_script(built):
    """Pretty-printed, one definition per block: whitespace is the only change from the shipped director (Will,
    2026-11-27); the stack effects and notes sit outside the code."""
    lev = LEV.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(r'<pre class="code" data-word="([^"]+)">(.*?)</pre>', built[0], re.S)
    assert [w for w, _ in blocks] == list(mp.FORTH_WORDS)
    names = mp.mailbox_names()
    number = {v: k for k, v in names.items()}
    used = set()
    for (word, body), shipped in zip(blocks, mp.forth_lines()):
        printed = htmllib.unescape(body)
        assert "<" not in body, word
        toks = printed.split()
        # every name stands before read-mailbox / write-mailbox and maps back to its number
        back = []
        for i, t in enumerate(toks):
            if t in number:
                assert toks[i + 1] in mp.MAILBOX_OPS, (word, t)
                used.add(t)
                back.append(str(number[t]))
            else:
                back.append(t)
        assert " ".join(back) == shipped, word
        assert shipped in lev, word
        assert not re.search(r"\b\d+ (read|write)-mailbox", printed), f"{word}: a raw mailbox number is printed"
        assert len(printed.splitlines()) > 1, f"{word} is not pretty-printed"
        assert max(len(x) for x in printed.splitlines()) <= mp.CODE_COLS, word
    L = mp.LAMP
    for t in used:
        n = number[t]
        if t.startswith("BLOB"):
            i, field = re.fullmatch(r"BLOB(\d+)_(\w+)", t).groups()
            assert n == L.BLOB0 + L.BLOB_STRIDE * int(i) + [f.upper() for f in L.BLOB_FIELDS].index(field), t
        else:
            assert n == getattr(L, t), t
        assert f"{n} read-mailbox" in lev or f"{n} write-mailbox" in lev, t
        pretty = mp.pretty(": t 1 if 2 else 3 then 4 5 write-mailbox ;")
    assert pretty == [": t", "  1 if", "    2", "  else", "    3", "  then", "  4 5 write-mailbox", ";"], pretty


# ── type and text ────────────────────────────────────────────────────────────
def lum(hexcol):
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def test_drawn_text_is_big_enough_and_readable(built):
    assert mp.TEXT_SIZES and min(mp.TEXT_SIZES) >= mp.MIN_PX
    for fg, bg in mp.TEXT_PAIRS:
        a, b = sorted((lum(fg), lum(bg)), reverse=True)
        assert (a + 0.05) / (b + 0.05) >= 4.5, (fg, bg)
    sizes = [float(x) for x in re.findall(r"font(?:-size)?:\s*([\d.]+)px", mp.CSS)]
    assert sizes and min(sizes) >= mp.MIN_PX


def test_numbers_keep_their_unit_and_dates_do_not_break(built):
    text = " ".join(text_nodes(built[0]))
    assert not re.search(rf"\d (?:{mp.UNITS[3:-1]})(?![\w/])", text), re.search(rf".{{20}}\d (?:{mp.UNITS[3:-1]})(?![\w/]).{{10}}", text)
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)
    assert not re.search(r"\b\d{1,2}(:\d{2})?\s?(am|pm|a\.m\.|p\.m\.)", text, re.I)


def test_the_html_is_self_contained_and_links_only_sources(built):
    doc = built[0]
    assert not re.search(r'(?:src|href)="(?!data:|https://)', doc)
    assert not re.search(r'<(script|link|img)[^>]+(src|href)="https?://', doc)
    allowed = {s["url"] for s in mp.SOURCES.values()} | {p["url"] for p in mp.PATENTS}
    hrefs = set(re.findall(r'href="([^"]+)"', doc))
    assert hrefs <= allowed, hrefs - allowed
    assert {s["url"] for s in mp.SOURCES.values()} <= hrefs


def test_no_status_tag_is_printed_and_sources_are_numbered(built):
    """Will (2026-11-27): no printed verified / ours tags. The statuses stay the build gate; on the page a sourced
    sentence ends in its superscript source numbers; the footer is the source list alone."""
    doc = built[0]
    page = " ".join(text_nodes(doc))
    assert 'class="chip' not in doc
    for tag in ("verified", "other source", "ours (measured)", "design (ours)", "schematic (ours)"):
        assert tag not in page.lower().replace(NBSP, " "), tag
    sourced = sum(1 for _, c in mp.all_claims() if c["src"])
    assert doc.count('<sup class="ref">') == sourced
    num = {s: i + 1 for i, s in enumerate(mp.source_order())}
    for _, c in mp.all_claims():
        if c["src"]:
            assert f'{mp.polish(c["text"])}<sup class="ref">{",".join(str(num[s]) for s in c["src"])}</sup>' in doc, c["text"][:40]
    # Will (2026-11-27): the footer is the numbered source list alone; its explanatory and colophon note stays out
    for gone in ("A superscript number is the source", "a sentence without one is ours", "locators: docs/reference",
                 "Drawings original", "our Cycles render. A3"):
        assert gone not in page, gone
    assert re.search(r'<footer id="panel-src"><div class="srcs">.*?</div></footer>', doc, re.S)


# ── the exported page ────────────────────────────────────────────────────────
def test_the_layout_review_is_clean():
    review = POSTER / "layout-review.json"
    if not review.exists():
        pytest.skip("run export_poster.py")
    r = json.loads(review.read_text())
    assert r["page_mm"] == {"width": 297, "height": 420}
    assert not r["overflowing"] and r["fit"] == "ok" and r["orphaned_header_refs"] == []
    assert r["min_font_pt"] >= 8.0
    assert all(not p["overflowing"] for p in r["panels"])


def test_the_pdf_is_one_a3_page():
    import export_poster
    pdfs = [POSTER / n for n in (export_poster.PDF_NAME, export_poster.DRAFT_PDF_NAME) if (POSTER / n).exists()]
    if not pdfs or not shutil.which("pdfinfo"):
        pytest.skip("run export_poster.py (and have poppler's pdfinfo)")
    for pdf in pdfs:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
        assert re.search(r"^Pages:\s+1$", out, re.M), pdf.name
        w, h = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", out).groups())
        assert abs(w / 72 * 25.4 - 297) < 1.5 and abs(h / 72 * 25.4 - 420) < 1.5, (pdf.name, w, h)


def test_the_png_preview_is_300_dpi_a3():
    png = POSTER / "poster.png"
    if not png.exists():
        pytest.skip("run export_poster.py")
    from PIL import Image
    w, h = Image.open(png).size
    assert abs(w - 3508) <= 4 and abs(h - 4961) <= 4, (w, h)
