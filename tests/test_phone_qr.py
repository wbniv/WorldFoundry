"""The TV's QR code for the phone controller (Phase E3 of docs/plans/2026-09-30-aquarium-chromecast.md).

The overlay encodes the full URL with this launch's PIN (http://<ip>:8765/?k=<pin>) at run time with the vendored
Nayuki encoder (engine/vendor/qrcodegen-3c6d0b3c, MIT) and draws it as black modules on white. Checked here with no
new dependency:

  * tests/qr_decode.py (a small reader written from the standard) is first proved on codes from segno, an
    independent encoder already used by the plan's mockup script;
  * the engine's matrix reads back to the exact URL, and is module-for-module what segno makes for the same level
    and mask (so it is a standard QR code, not just one this reader accepts);
  * the overlay draws exactly that matrix: sampled from the composited 1920x1080 frame, with a white quiet zone of
    4 modules and modules of at least 12 px (it has to scan from a sofa), and still at 1280x720.

    python3 -m pytest tests/test_phone_qr.py -v
"""

from __future__ import annotations

import pytest

from phonepad_harness import Host, build_host, overlay_rects, render_rects
from qr_decode import QrError, decode, ecc_ok, format_info, function_modules

segno = pytest.importorskip("segno")

URLS = ["http://192.168.4.38:8765/?k=800855", "http://10.0.0.2:8765/?k=000001", "http://172.16.254.254:8766/?k=482913",
        "http://255.255.255.255:65535/?k=999999"]


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    return build_host(tmp_path_factory.mktemp("phonepad-qr"))


@pytest.fixture
def host(exe):
    h = Host(exe)                                    # a fresh overlay state for every test
    yield h
    h.close()


def engine_qr(host, text):
    host.command(f"qr {text}")
    n = int(host.expect(r"^QR (\d+)$").group(1))
    assert n > 0, "the engine could not encode " + text
    return [[int(ch) for ch in host.expect(r"^[01]+$").group(0)] for _ in range(n)]


def segno_matrix(text, **kw):
    return [list(row) for row in segno.make_qr(text, mode="byte", boost_error=False, **kw).matrix]


@pytest.mark.parametrize("level", ["L", "M", "Q", "H"])
@pytest.mark.parametrize("text", URLS)
def test_reader_reads_an_independent_encoder(text, level):
    assert decode(segno_matrix(text, error=level)) == text


def test_reader_rejects_a_damaged_format():
    m = segno_matrix(URLS[0], error="M")
    m[8][0] ^= 1
    with pytest.raises(QrError):
        decode(m)


@pytest.mark.parametrize("text", URLS)
def test_engine_qr_reads_back_to_the_url(host, text):
    assert decode(engine_qr(host, text)) == text


@pytest.mark.parametrize("level", ["L", "M", "Q", "H"])
@pytest.mark.parametrize("text", URLS)
def test_reed_solomon_check_holds_for_the_independent_encoder(text, level):
    assert ecc_ok(segno_matrix(text, error=level))


@pytest.mark.parametrize("text", URLS)
def test_engine_qr_is_a_standard_code(host, text):
    """Same function patterns (finders, timing, alignment, format) as segno's code for that version, level and
    mask, and correct Reed-Solomon bytes. (The data modules may differ only in padding: segno writes one extra
    zero byte after the terminator; both are valid.)"""
    m = engine_qr(host, text)
    level, mask = format_info(m)
    assert level == "H", "ECC H: the logo in the middle spends part of the correction budget"
    ver = (len(m) - 17) // 4
    ref = segno_matrix(text, error=level, mask=mask, version=ver)
    func = function_modules(len(m), ver)
    assert all(m[y][x] == ref[y][x] for y in range(len(m)) for x in range(len(m)) if func[y][x])
    assert ecc_ok(m)


def drawn_qr(rects, w, h, n_modules):
    """Sample the QR out of the composited overlay: (matrix without quiet zone, module px, quiet-zone ok)."""
    img = render_rects(rects, w, h)
    white = [r for r in rects if r[4] == (255, 255, 255, 255)]
    assert len(white) == 1, "one white square behind the code"
    x0, y0, x1, y1, _ = white[0]
    assert abs((x1 - x0) - (y1 - y0)) < 0.01
    n = n_modules
    n_total = n + 8
    mod = (x1 - x0) / n_total
    px = img.load()

    def dark(i, j):
        x, y = int(x0 + (i + 0.5) * mod), int(y0 + (j + 0.5) * mod)
        return 1 if sum(px[x, y]) < 3 * 128 else 0

    quiet = all(dark(i, j) == 0 for i in range(n_total) for j in range(n_total)
                if i < 4 or j < 4 or i >= n_total - 4 or j >= n_total - 4)
    return [[dark(4 + c, 4 + r) for c in range(n)] for r in range(n)], mod, quiet


@pytest.mark.parametrize("w,h,min_px", [(1920, 1080, 12), (1280, 720, 8)])
def test_overlay_draws_exactly_that_code_large_with_a_quiet_zone(host, w, h, min_px):
    url = URLS[0]
    host.command("ov-logo none")                          # the plain code; the logo has its own tests below
    host.command(f"ov-endpoint {url} 192.168.4.38:8765 800855")
    _, rects = overlay_rects(host, w, h, 0)
    clean = engine_qr(host, url)
    matrix, mod, quiet = drawn_qr(rects, w, h, len(clean))
    assert matrix == clean
    assert decode(matrix) == url
    assert quiet, "a white quiet zone of 4 modules"
    assert mod >= min_px and mod == int(mod), f"module {mod} px: whole pixels, large enough to scan"


def test_overlay_without_endpoint_has_no_code(host):
    host.command("ov-endpoint http://192.168.4.38:8765/?k=800855 192.168.4.38:8765 800855")
    host.command("ov-event connected 0")
    _, rects = overlay_rects(host, 1920, 1080, 10_000)
    assert not [r for r in rects if r[4] == (255, 255, 255, 255)]


# ---- the World Foundry logo in the middle (wf_args.txt qr_logo=planet|full|none, default planet) ----------------

import subprocess
from pathlib import Path

from phonepad_harness import REPO
from qr_decode import codewords_per_block_touched

LOGO_SRC = REPO.parent / "worldfoundry.org" / "src" / "assets" / "wflogo.png"
BUDGET = {"planet": 0.10, "full": 0.10}                # target share of the modules under the plate (hard limit 15 %)


def plate(host, n, mode):
    host.command(f"plate {n} {mode}")
    got = host.expect(r"^PLATE (.*)$").group(1)
    if got == "none":
        return None
    x, y, w, h = map(int, got.split())
    return {(c, r) for r in range(y, y + h) for c in range(x, x + w)}


def test_logo_header_is_regenerated_from_the_logo():
    if not LOGO_SRC.exists():
        pytest.skip(f"{LOGO_SRC} not on this machine (the worldfoundry.org checkout next to this repository)")
    r = subprocess.run(["python3", str(REPO / "scripts" / "gen-qr-logo.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("mode", ["planet", "full"])
@pytest.mark.parametrize("n", [25, 29, 33, 37, 41])
def test_plate_never_touches_finder_timing_alignment_or_format(host, n, mode):
    p = plate(host, n, mode)
    assert p, f"a logo for version {(n - 17) // 4}"
    func = function_modules(n, (n - 17) // 4)
    assert not [xy for xy in p if func[xy[1]][xy[0]]]
    assert len(p) / (n * n) <= BUDGET[mode], f"{len(p)} of {n * n} modules"


def test_no_logo_on_version_1_or_where_the_centre_has_an_alignment_pattern(host):
    for n in (21, 45):                                          # version 1 (format bits too close), version 7
        assert plate(host, n, "planet") is None and plate(host, n, "full") is None


@pytest.mark.parametrize("mode", ["planet", "full"])
@pytest.mark.parametrize("text", URLS)
def test_code_with_the_logo_still_reads_back_to_the_url(host, text, mode):
    """Sampled from the composited overlay frame, exactly as drawn: only plate modules differ from the clean code,
    the finder, timing, alignment and format modules are untouched, every block keeps at least a quarter of its
    correction budget for the camera, and Reed-Solomon brings back the exact URL."""
    clean = engine_qr(host, text)
    n = len(clean)
    host.command(f"ov-logo {mode}")
    host.command(f"ov-endpoint {text} host:1 000000")
    _, rects = overlay_rects(host, 1920, 1080, 0)
    drawn, _, quiet = drawn_qr(rects, 1920, 1080, n)
    p = plate(host, n, mode)
    wrong = {(c, r) for r in range(n) for c in range(n) if drawn[r][c] != clean[r][c]}
    assert wrong and wrong <= p, "only the plate differs"
    func = function_modules(n, (n - 17) // 4)
    assert all(drawn[r][c] == clean[r][c] for r in range(n) for c in range(n) if func[r][c])
    assert quiet
    level, _ = format_info(drawn)
    per_block = codewords_per_block_touched(n, level, p)        # worst case: every plate module wrong
    assert all(t <= 0.75 * cap for t, cap in per_block), per_block
    assert not ecc_ok(drawn), "the logo damages the code ..."
    assert decode(drawn, correct=True) == text                   # ... and error correction repairs it


@pytest.mark.parametrize("fill", ["white", "inverted"])
def test_a_plate_of_a_quarter_of_the_code_does_not_read(host, fill):
    """The guard against a logo that grows: a centred plate over 25 % of the modules defeats ECC H."""
    clean = engine_qr(host, URLS[0])
    n = len(clean)
    side = int((0.25 * n * n) ** 0.5) | 1
    lo = (n - side) // 2
    m = [row[:] for row in clean]
    for r in range(lo, lo + side):
        for c in range(lo, lo + side):
            m[r][c] = 0 if fill == "white" else 1 - m[r][c]
    with pytest.raises(QrError):
        decode(m, correct=True)


def test_no_logo_leaves_the_code_plain(host):
    clean = engine_qr(host, URLS[0])
    host.command("ov-logo none")
    host.command(f"ov-endpoint {URLS[0]} host:1 000000")
    _, rects = overlay_rects(host, 1920, 1080, 0)
    assert drawn_qr(rects, 1920, 1080, len(clean))[0] == clean
