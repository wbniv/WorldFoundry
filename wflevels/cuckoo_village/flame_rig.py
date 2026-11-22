#!/usr/bin/env python3
"""Option B of the candle flicker plan: bind each pine's ten flames to ten DFRM curves (docs/plans/2026-11-22-cuckoo-village-candle-flicker.md).

A flame is the diamond of candles.flame(): a foot, a ring a third of the way up and a tip. Each flame becomes one curve of two bones: bone 0 from
the foot to the ring, bone 1 from the ring to the tip. A vertex at the foot stays where it is, the four ring vertices ride the end of bone 0 and the
tip rides the end of bone 1, so a flex bias on the curve leans the flame about its foot and a scale below 1 (about the curve's root) shortens it. The
mesh is authored at its tallest and upright; the director only bends and shrinks it. The ventral axis is +X, the draught.

    flame_rig.py [-h]            bind wflevels/cuckoo_village/candle_flames_NN.iff (written by the Blender build) using flame-bases.json
                                 (the build writes it: per tree, the ten flame feet in candle_bases order); run by build.sh when CANDLE_FLAMES=deform

The pure functions (chains, bindings) are tested without Blender or the engine by tests/test_cuckoo_village_flame_rig.py.
"""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "wftools" / "wf_blender"))
import candles as cd  # noqa: E402

TALL = cd.FLAME_SHAPES[1][0]              # the authored height: the tallest the flame ever stands (the scale cell only shrinks, 0.02 to 1)
LIMITS = (35.0, 35.0, 35.0, 35.0)         # ventral, dorsal, lateral, twist degrees
EPS = 1e-5


def chains(feet):
    """One two-bone chain per flame foot, straight up, ventral axis the draught (+X)."""
    out = []
    for fx, fy, fz in feet:
        ring = fz + TALL / 3.0
        out.append([{"head": (fx, fy, fz), "tail": (fx, fy, ring), "z_axis": (1.0, 0.0, 0.0), "limits": LIMITS},
                    {"head": (fx, fy, ring), "tail": (fx, fy, fz + TALL), "z_axis": (1.0, 0.0, 0.0), "limits": LIMITS}])
    return out


def bindings(vertices, feet, none, on_sample):
    """(kind, sample, weight) per vertex: foot rigid, ring on sample 2n, tip on sample 2n + 1, for the flame n whose foot is nearest below it."""
    out = []
    for v in vertices:
        best = None
        for n, f in enumerate(feet):
            dz = v[2] - f[2]
            d2 = (v[0] - f[0]) ** 2 + (v[1] - f[1]) ** 2
            if -EPS <= dz <= TALL + EPS and d2 <= 0.05 ** 2 and (best is None or d2 < best[0]):
                best = (d2, n, dz)
        if best is None:
            raise ValueError(f"vertex {v} belongs to no flame")
        _, n, dz = best
        if dz < EPS:
            out.append((none, 0, 0))
        elif abs(dz - TALL / 3.0) < 1e-4:
            out.append((on_sample, 2 * n, 1))
        elif abs(dz - TALL) < 1e-4:
            out.append((on_sample, 2 * n + 1, 1))
        else:
            raise ValueError(f"vertex {v} is {dz:.5f} m above its flame's foot: neither foot, ring nor tip")
    return out


def payload(vertices, feet, dfrm):
    return dfrm.build_chunk_curves(chains(feet), vertices, bindings(vertices, feet, dfrm.NONE, dfrm.ON_SAMPLE), knots=(0, 1))


def bind_file(path: Path, feet, dfrm) -> int:
    """Append the DFRM chunk to an exported MODL .iff, as the reef's feather star does. Returns the vertex count."""
    data = path.read_bytes()
    if data[:4] != b"MODL" or struct.unpack_from("<I", data, 4)[0] != len(data) - 8:
        raise ValueError(f"{path}: not a MODL file")
    cursor, vertices = 8, None
    while cursor < len(data):
        tag, size = struct.unpack_from("<4sI", data, cursor)
        end = cursor + 8 + ((size + 3) & ~3)
        if end > len(data) or tag == b"DFRM":
            raise ValueError(f"{path}: malformed or already bound")
        if tag == b"VRTX":
            if vertices is not None or size % 24:
                raise ValueError(f"{path}: unexpected vertices")
            vertices = [tuple(v / 65536 for v in struct.unpack_from("<iii", data, cursor + 20 + i)) for i in range(0, size, 24)]
        cursor = end
    if cursor != len(data) or not vertices:
        raise ValueError(f"{path}: no vertices")
    body = payload(vertices, feet, dfrm)
    chunk = b"DFRM" + struct.pack("<I", len(body)) + body + b"\0" * (-len(body) % 4)
    path.write_bytes(b"MODL" + struct.pack("<I", len(data) - 8 + len(chunk)) + data[8:] + chunk)
    return len(vertices)


def main(argv):
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    import dfrm_chunk as dfrm
    bases = json.loads((HERE / "flame-bases.json").read_text())
    for i, feet in enumerate(bases):
        n = bind_file(HERE / f"candle_flames_{i + 1:02d}.iff", [tuple(f) for f in feet], dfrm)
        print(f"[flame-rig] candle_flames_{i + 1:02d}.iff: {n} vertices, {len(feet)} curves")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
