"""The UI font bake (scripts/bake-ui-font.py; docs/plans/2026-10-17-settings-editor-font.md).

Run in the Linux test container, which has Pillow with raqm:

    scripts/in-linux-container.sh python3 -m pytest -q -p no:cacheprovider tests/test_ui_font_bake.py

  * the two TTFs are the pinned files;
  * two bakes give the same bytes, and those are the committed wfsource/source/game/ui-font.wfga;
  * the header, variant table and record order are what bitmap_text.cc Catalog::Load expects
    (tests/ui_font_test.cc, the ctest `ui_font`, then loads it with the engine's own reader).
"""

from __future__ import annotations

import hashlib
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BAKE = ROOT / "scripts" / "bake-ui-font.py"
FONTS = ROOT / "wfsource" / "fonts" / "atkinson-hyperlegible-next"
COMMITTED = ROOT / "wfsource" / "source" / "game" / "ui-font.wfga"
PINNED = {"AtkinsonHyperlegibleNext-Regular.ttf": "88ed5c31a71584c7772963b02d04bef1eb7e3d2e9c8b9cb204339b1f82cf432c",
          "AtkinsonHyperlegibleNext-SemiBold.ttf": "8e2fff779f35ac25239656bb0f3b2bd35959a2009e3dd21a12141c3b9030362b"}


def test_fonts_are_the_pinned_files():
    for name, digest in PINNED.items():
        assert hashlib.sha256((FONTS / name).read_bytes()).hexdigest() == digest, name


@pytest.fixture(scope="module")
def bakes(tmp_path_factory):
    pytest.importorskip("PIL")
    out = tmp_path_factory.mktemp("ui-font")
    for name in ("a.wfga", "b.wfga"):
        subprocess.run([sys.executable, str(BAKE), "--out", str(out / name)], check=True, capture_output=True)
    return (out / "a.wfga").read_bytes(), (out / "b.wfga").read_bytes()


def test_bake_is_deterministic_and_committed(bakes):
    a, b = bakes
    assert a == b, "two bakes differ"
    assert a == COMMITTED.read_bytes(), "wfsource/source/game/ui-font.wfga is stale: run scripts/bake-ui-font.py"


def test_layout_is_wfga_v1(bakes):
    data = bakes[0]
    assert data[:4] == b"WFGA"
    version, width, height, variants, glyphs, kerns, texts, labels = struct.unpack_from("<8i", data, 4)
    assert (version, width, height, variants, texts, labels) == (1, 1024, 2048, 7, 0, 0)
    table = [struct.unpack_from("<6i", data, 64 + 24 * i) for i in range(variants)]
    assert [(v[1], v[2]) for v in table] == [(0, 28), (0, 36), (1, 36), (1, 46), (0, 56), (1, 56), (1, 80)]
    base = 64 + 24 * variants
    keys = [struct.unpack_from("<2i", data, base + 36 * i) for i in range(glyphs)]
    assert keys == sorted(keys) and len(set(keys)) == glyphs == 7 * 198
    kbase = base + 36 * glyphs
    pairs = [struct.unpack_from("<3i", data, kbase + 16 * i) for i in range(kerns)]
    assert pairs == sorted(pairs) and len(set(pairs)) == kerns
    assert len(data) == kbase + 16 * kerns + width * height
