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
def host(tmp_path_factory):
    h = Host(build_host(tmp_path_factory.mktemp("phonepad-qr")))
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
    assert level in "MQH", "at least ECC M (boosted when it costs no size)"
    ver = (len(m) - 17) // 4
    ref = segno_matrix(text, error=level, mask=mask, version=ver)
    func = function_modules(len(m), ver)
    assert all(m[y][x] == ref[y][x] for y in range(len(m)) for x in range(len(m)) if func[y][x])
    assert ecc_ok(m)


def drawn_qr(rects, w, h):
    """Sample the QR out of the composited overlay: (matrix without quiet zone, module px, quiet-zone ok)."""
    img = render_rects(rects, w, h)
    white = [r for r in rects if r[4] == (255, 255, 255, 255)]
    assert len(white) == 1, "one white square behind the code"
    x0, y0, x1, y1, _ = white[0]
    assert abs((x1 - x0) - (y1 - y0)) < 0.01
    blacks = [r for r in rects if r[4] == (0, 0, 0, 255)]
    mod = min(r[3] - r[1] for r in blacks)                    # every dark run is one module tall
    n_total = round((x1 - x0) / mod)
    n = n_total - 8
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
    host.command(f"ov-endpoint {url} 192.168.4.38:8765 800855")
    _, rects = overlay_rects(host, w, h, 0)
    matrix, mod, quiet = drawn_qr(rects, w, h)
    assert matrix == engine_qr(host, url)
    assert decode(matrix) == url
    assert quiet, "a white quiet zone of 4 modules"
    assert mod >= min_px and mod == int(mod), f"module {mod} px: whole pixels, large enough to scan"


def test_overlay_without_endpoint_has_no_code(host):
    host.command("ov-endpoint http://192.168.4.38:8765/?k=800855 192.168.4.38:8765 800855")
    host.command("ov-event connected 0")
    _, rects = overlay_rects(host, 1920, 1080, 10_000)
    assert not [r for r in rects if r[4] == (255, 255, 255, 255)]
