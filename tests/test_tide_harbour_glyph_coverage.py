#!/usr/bin/env python3
"""Tide Harbour: every character the panel draws from the Thai font is in that font.

A character the font lacks comes out as its missing-glyph box. Noto Sans Thai has no full stop, so the unit labels
once read "ม" plus a hollow box (seen on cast1, 2026-11-21); the stops are now drawn as squares
(blender_create_tide_harbour.py `stop`). The font is the repo's static copy; the cmap test is skipped where fontTools is not installed
(fontTools is not in the images).
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "wflevels" / "tide_harbour" / "blender_create_tide_harbour.py"
FONT = ROOT / "wflevels" / "tide_harbour" / "fonts" / "NotoSansThai-Bold.ttf"     # static and bold: no offset embolden, which tears (fonts/README.md)


def glyph_texts() -> list:
    """The strings the script turns into outlines: the Thai digits and the `texts` list in panel_glyphs."""
    src = SCRIPT.read_text(encoding="utf-8")
    digits = re.search(r"^THAI_DIGITS\s*=\s*(.+)$", src, re.M)
    texts = re.search(r"texts = list\(THAI_DIGITS\) \+ (\[.*?\])\n", src)
    assert digits and texts, "the glyph lists moved: update this test"
    return list(ast.literal_eval(digits.group(1).split("#")[0].strip())) + ast.literal_eval(texts.group(1))


class GlyphCoverage(unittest.TestCase):
    def test_the_credit_left_the_panel_and_is_in_the_settings_form(self):
        """The river map is OpenStreetMap data (ODbL). Will, 2026-11-22: "remove the (c) from the panel. you can add it to an about
        box". The attribution moves in one change: no credit plate on the panel, and a read-only About row in the settings form."""
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("CREDIT", src, "the panel must not carry the credit any more")
        oas = (ROOT / "wfsource/source/oas/tideharboursettings.oas").read_text(encoding="utf-8")
        row = [l for l in oas.splitlines() if l.lstrip().startswith("TYPEENTRYINT32(About the map")]
        self.assertEqual(len(row), 1, "the settings form needs exactly one About row")
        self.assertIn('"(c) OpenStreetMap contributors|ODbL: openstreetmap.org/copyright"', row[0],
                      "the form must show the credit and where the licence is")
        self.assertNotIn("SHOW_AS_LIVE", row[0], "the About row is read-only: a live field would be editable")

    def test_thai_text_is_bold_and_not_offset(self):
        """An offset (embolden) curve self-intersects on the thin loops of ๕ ๗ ๘ and Blender's fill tears them: the digits came
        out bitten on cast1 (2026-11-22). Thai text is a static bold font drawn with offset 0."""
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("THAI_FONT = HERE / 'fonts' / 'NotoSansThai-Bold.ttf'", src)
        self.assertIn("curve.offset = 0.0 if (font is not None and Path(font.filepath).name == THAI_FONT.name) else 0.02", src)
        self.assertTrue((ROOT / "wflevels" / "tide_harbour" / "fonts" / "NotoSansThai-Bold.ttf").is_file())
        self.assertTrue((ROOT / "wflevels" / "tide_harbour" / "fonts" / "LICENSE-Noto.txt").is_file())

    def test_the_lists_are_found(self):
        self.assertGreaterEqual(len(glyph_texts()), 15)

    def test_no_full_stop_in_a_font_string(self):
        for t in glyph_texts():
            self.assertNotIn(".", t, f"{t!r}: the font has no full stop; draw it with `stop`")

    def test_every_character_is_in_the_font(self):
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest("fontTools is not installed")
        if not FONT.is_file():
            self.skipTest(f"{FONT} is not installed")
        cmap = TTFont(str(FONT)).getBestCmap()
        for t in glyph_texts():
            for ch in t:
                self.assertIn(ord(ch), cmap, f"{t!r}: U+{ord(ch):04X} is not in the font")


if __name__ == "__main__":
    unittest.main()
