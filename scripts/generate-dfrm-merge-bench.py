#!/usr/bin/env python3
"""Write equivalent DFRM meshes for the reef's 15-versus-1 device bench.

The caller must create the level and animate all 15 crowns identically. The
meshes alone do not measure actor, draw or upload cost.
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wftools/wf_blender'))
sys.path.insert(0, str(ROOT / 'wflevels/aquarium_tanks'))
import dfrm_chunk as dc
import dfrm_ref as ref


def make(count):
    chains, positions, bindings, faces = [], [], [], []
    for c in range(count):
        x, y, z = float(c % 5), 0.0, float(c // 5) * .75
        chains.append([{'head': (x, y, z + i * .1), 'tail': (x, y, z + (i + 1) * .1),
                        'z_axis': (1, 0, 0), 'limits': (60, 60, 60, 60)} for i in range(2)])
        for i in range(12):
            a, b = 2 * math.pi * i / 12, 2 * math.pi * (i + 1) / 12
            start = len(positions)
            positions.extend([(x, y, z + .2), (x + .2 * math.cos(a), y + .2 * math.sin(a), z + .35),
                              (x + .2 * math.cos(b), y + .2 * math.sin(b), z + .35)])
            bindings.extend([(dc.ON_SAMPLE, 2 * c + 1, 1.0)] * 3)
            faces.append((start, start + 1, start + 2))
    payload = dc.build_chunk_curves(chains, positions, bindings, knots=(0, 1))
    return positions, faces, payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('out', type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for count, name in ((1, 'crown-single.iff'), (15, 'crowns-merged.iff')):
        positions, faces, payload = make(count)
        (args.out / name).write_bytes(ref.modl(positions, faces, payload))
    (args.out / 'manifest.json').write_text(json.dumps({
        'single': {'instances': 15, 'curves_per_instance': 1, 'triangles_per_instance': 12},
        'merged': {'instances': 1, 'curves_per_instance': 15, 'triangles_per_instance': 180},
        'positions': [[i % 5, 0, (i // 5) * .75] for i in range(15)],
        'note': 'Mesh fixtures only; device level, animation and measurement are still required.'
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
