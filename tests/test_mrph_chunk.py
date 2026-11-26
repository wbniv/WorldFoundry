"""The MRPH mesh chunk (morph targets) encodes and decodes losslessly at its own precision, and refuses bad input.

wftools/wf_blender/mrph_chunk.py; the engine side is wfsource/source/renderassets/morph_deform.h. Plan
docs/plans/2026-11-26-lava-lamp.md, E1. The exporter round trip on a real mesh is tests/test_lava_lamp.py -k export.
"""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wftools" / "wf_blender"))
import mrph_chunk  # noqa: E402


def test_round_trip_morph():
    names = ["rise", "squash"]
    pos = [[(0.5, -0.25, 1.0), (0, 0, 0)], [(-1e-5, 2.0, -3.5), (0.125, 0.125, 0.125)]]
    shade = [[(0.25, -0.5, 0), (0, 0, 0)], [(1.0, 0.0, -1.0), (0.5, 0.5, 0.5)]]
    names2, pos2, shade2, n = mrph_chunk.decode(mrph_chunk.encode(names, pos, shade, 2))
    assert (names2, n) == (names, 2)
    for t in range(2):
        for i in range(2):
            assert all(abs(a - b) <= 0.5 / 65536 for a, b in zip(pos[t][i], pos2[t][i]))
            assert all(abs(a - b) <= 0.5 / 4096 for a, b in zip(shade[t][i], shade2[t][i]))


def test_an_empty_chunk_is_a_tint_actor_morph():
    payload = mrph_chunk.encode([], [], [], 5)
    assert payload == struct.pack("<III", 1, 0, 5)
    assert mrph_chunk.decode(payload) == ([], [], [], 5)


def test_bad_input_is_refused_morph():
    with pytest.raises(ValueError):
        mrph_chunk.encode(["a"] * 7, [[(0, 0, 0)]] * 7, [[(0, 0, 0)]] * 7, 1)       # seven targets
    with pytest.raises(ValueError):
        mrph_chunk.encode(["a"], [[(0, 0, 0)]], [[(9.0, 0, 0)]], 1)                  # shade outside i16
    with pytest.raises(ValueError):
        mrph_chunk.target_name("rise")                                               # not morph_<name>
    with pytest.raises(ValueError):
        mrph_chunk.decode(mrph_chunk.encode([], [], [], 2) + b"\0")                  # size mismatch
