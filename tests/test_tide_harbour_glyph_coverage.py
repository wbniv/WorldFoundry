#!/usr/bin/env python3
"""Tide Harbour: every character the panel draws from the Thai font is in that font.

A character the font lacks comes out as its missing-glyph box. Noto Sans Thai has no full stop, so the unit labels
once read "ม" plus a hollow box (seen on cast1, 2026-11-21); the stops are now drawn as squares
(blender_create_tide_harbour.py `stop`). The font is Blender's; the test is skipped where it is not installed
(the Blender container has it, the linux-test image does not).
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "wflevels" / "tide_harbour" / "blender_create_tide_harbour.py"
FONT = Path("/usr/lib/blender/datafiles/fonts/NotoSansThai-VariableFont_wdth,wght.woff2")
CREDIT_FONT = Path("/usr/lib/blender/datafiles/fonts/DejaVuSansMono.woff2")     # not Blender's default Inter: its M came out filled


def glyph_texts() -> list:
    """The strings the script turns into outlines: the Thai digits and the `texts` list in panel_glyphs."""
    src = SCRIPT.read_text(encoding="utf-8")
    digits = re.search(r"^THAI_DIGITS\s*=\s*(.+)$", src, re.M)
    texts = re.search(r"texts = list\(THAI_DIGITS\) \+ (\[.*?\])\n", src)
    assert digits and texts, "the glyph lists moved: update this test"
    return list(ast.literal_eval(digits.group(1).split("#")[0].strip())) + ast.literal_eval(texts.group(1))


class GlyphCoverage(unittest.TestCase):
    def test_the_map_credit_is_drawn(self):
        """The river map is OpenStreetMap data (ODbL): the panel must carry the credit wherever the map is shown."""
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("CREDIT = '© OpenStreetMap contributors'", src)
        self.assertIn("shapes[CREDIT]", src)
        self.assertIn("put(body, CREDIT,", src)
        self.assertIn("CREDIT_FONT = Path('/usr/lib/blender/datafiles/fonts/DejaVuSansMono.woff2')", src)
        self.assertNotIn("outlines('pc', [CREDIT], None)", src, "the default font (Inter) draws a filled M: use CREDIT_FONT")

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

    def test_the_credit_is_in_its_font(self):
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest("fontTools is not installed")
        if not CREDIT_FONT.is_file():
            self.skipTest(f"{CREDIT_FONT} is not installed")
        credit = re.search(r"^CREDIT = '(.+)'", SCRIPT.read_text(encoding="utf-8"), re.M).group(1)
        cmap = TTFont(str(CREDIT_FONT)).getBestCmap()
        for ch in credit:
            self.assertIn(ord(ch), cmap, f"U+{ord(ch):04X} is not in {CREDIT_FONT.name}")


if __name__ == "__main__":
    unittest.main()
