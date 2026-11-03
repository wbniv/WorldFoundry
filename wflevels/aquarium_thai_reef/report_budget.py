#!/usr/bin/env python3
"""Report *generated blockout* geometry; cooked IFF counts still need a gate."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=ROOT, help='repository with aquarium_tanks/mesh.py')
parser.add_argument('--json', action='store_true')
args = parser.parse_args()
sys.path.insert(0, str(args.repo/'wflevels'/'aquarium_tanks'))
from mesh import Mesh
from config import STATIC_GROUPS_MAX, STATIC_TRIANGLES_MAX
from reef.geometry import build_groups, triangles

groups=build_groups(Mesh)
counts={name:triangles(mesh) for name,mesh in groups.items()}
total=sum(counts.values())
ok=len(counts)<=STATIC_GROUPS_MAX and total<=STATIC_TRIANGLES_MAX
if args.json:
    print(json.dumps({'kind':'generated-blockout', 'groups':counts, 'total':total,
                      'group_limit':STATIC_GROUPS_MAX,'triangle_limit':STATIC_TRIANGLES_MAX,
                      'ok':ok}, sort_keys=True, indent=2))
else:
    for name,n in counts.items():
        print(f'{name:18} {n:6} triangles')
    print(f'Total {total}/{STATIC_TRIANGLES_MAX} triangles; {len(counts)}/{STATIC_GROUPS_MAX} groups')
    print('Blockout only: cooked IFF, collision and runtime budgets remain unverified.')
raise SystemExit(0 if ok else 1)
