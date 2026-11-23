"""The two window-box actors of the Cuckoo Village level (docs/plans/2026-11-22-cuckoo-village-flowers.md).

cottage_flowers (the petunia and geranium boxes) shows when the Detailed flowers field is On and cottage_flower_blocks
(the blocks that were always there) when it is Off; the director drives one visibility cell for each
(tests/verify_cuckoo_village_forth.py runs the real VM). Here: the built level's source has both actors on those cells,
and, when the build's mesh files are present, the exported materials are as designed.
"""
import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village_assets"))
import flowers as fw  # noqa: E402
import timeline as tl  # noqa: E402

LEV = ROOT / "wflevels/cuckoo_village/cuckoo_village.lev"
BUILD = ROOT / "wflevels/cuckoo_village"


def actor_block(name):
    """The level source of one actor: from its own header line (`{ 'NAME' "x" }` alone on a line) to the next actor's."""
    text = LEV.read_text()
    headers = [m for m in re.finditer(r"^[ \t]*\{ 'NAME' \"[^\"]+\" \}[ \t]*$", text, re.M)]
    for k, m in enumerate(headers):
        if f'"{name}"' in m.group(0):
            return text[m.start():headers[k + 1].start() if k + 1 < len(headers) else len(text)]
    raise AssertionError(f"no actor {name} in the level source")


def test_the_level_has_both_window_box_actors_on_their_visibility_cells():
    for name, cell in (("cottage_flowers", tl.FLOWERS_CELL), ("cottage_flower_blocks", tl.BLOCKS_CELL)):
        block = actor_block(name)
        assert re.search(r"Visibility Mailbox\" \} \{ 'DATA' %dl " % cell, block), (name, cell)
        assert f'"{name}.iff"' in block


def test_the_two_cells_are_distinct_and_clear_of_the_candles_and_flames():
    cells = [tl.CANDLE_CELL, *tl.FLICKER_CELLS, tl.FLOWERS_CELL, tl.BLOCKS_CELL]
    assert len(set(cells)) == len(cells)


def matl(path):
    d = path.read_bytes()
    i = d.index(b"MATL")
    size = struct.unpack("<I", d[i + 4:i + 8])[0]
    assert size % 264 == 0
    out = []
    for k in range(size // 264):
        base = i + 8 + k * 264
        flags, color = struct.unpack("<iI", d[base:base + 8])
        out.append((flags, color, d[base + 8:base + 264].split(b"\0")[0].decode()))
    return out


def test_the_exported_flower_materials_are_flat_colours_with_the_thin_ones_double_sided():
    path = BUILD / "cottage_flowers.iff"
    if not path.exists():
        pytest.skip("build the level first: bash wflevels/cuckoo_village/build.sh (the mesh files are build outputs)")
    slots = matl(path)
    assert len(slots) == len(fw.MATERIALS) == 10
    assert all(tex == "" for _, _, tex in slots)                              # no texture anywhere
    for (flags, color, _), name in zip(slots, fw.MATERIALS):
        assert (flags & 8 != 0) == (name in fw.DOUBLE_SIDED), name            # flag 8 is double-sided
        assert flags & 2 == 0                                                 # flag 2 would mean textured
    assert sum(1 for f, _, _ in slots if f & 8) == 8


def test_the_exported_blocks_keep_the_one_atlas_material_they_always_had():
    path = BUILD / "cottage_flower_blocks.iff"
    if not path.exists():
        pytest.skip("build the level first: bash wflevels/cuckoo_village/build.sh (the mesh files are build outputs)")
    assert matl(path) == [(2, 0xFFFFFF, "village_atlas.tga")]
