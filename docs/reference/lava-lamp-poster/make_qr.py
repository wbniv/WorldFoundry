#!/usr/bin/env python3
"""Write one QR code per patent on the lava lamp poster: qr/<number>.svg, each encoding the patent's Google Patents page.

    python3 docs/reference/lava-lamp-poster/make_qr.py          # needs segno (pip install segno)

The SVGs are committed, like the hero render, so make_poster.py and the tests run where segno is missing (the
wf-linux-test container). tests/test_lava_lamp_poster.py regenerates them when segno is present and requires the same
bytes. Plan: docs/plans/2026-11-26-lava-lamp.md (Q8, "a QR code per patent").
"""
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QR_DIR = HERE / 'qr'


def patents():
    sys.path.insert(0, str(HERE))
    from patents import PATENTS
    return PATENTS


def qr_svg(url: str) -> str:
    import segno
    buf = io.BytesIO()
    # error level M, two modules of quiet zone; one module per SVG unit, the poster sets the printed size
    segno.make(url, error='m', micro=False, boost_error=False).save(
        buf, kind='svg', xmldecl=False, svgns=True, scale=1, border=2, dark='#1d1420', light='#ffffff', nl=False)
    return buf.getvalue().decode('ascii')


def main():
    QR_DIR.mkdir(exist_ok=True)
    for p in patents():
        out = QR_DIR / f'{p["key"]}.svg'
        out.write_text(qr_svg(p['url']) + '\n', encoding='ascii')
        print(out.relative_to(HERE), p['url'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
