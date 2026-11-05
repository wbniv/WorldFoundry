#!/usr/bin/env python3
"""Report *generated blockout* geometry; cooked IFF counts still need a gate."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
from config import ANIME_HULL_TRIANGLES_MAX, ANIME_STATIC_TRIANGLES_MAX, STATIC_GROUPS_MAX, STATIC_TRIANGLES_MAX
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=ROOT, help='repository with aquarium_tanks/mesh.py')
parser.add_argument('--json', action='store_true')
parser.add_argument('--cooked', action='store_true', help='report the most recent Blender export for both styles')
args = parser.parse_args()
if args.cooked:
    reports = {}
    for level, limit in (('aquarium_thai_reef', STATIC_TRIANGLES_MAX), ('aquarium_thai_reef_anime', ANIME_STATIC_TRIANGLES_MAX)):
        data = json.loads((args.repo/'wflevels'/level/'actor-map.json').read_text())
        animated = data['animated_triangles']
        counts = data['triangles']
        hull = sum(data.get('hull_triangles', {}).values())
        reports[level] = {'static_triangles':sum(counts.values()), 'static_limit':limit,
                          'hull_triangles':hull, 'hull_limit':ANIME_HULL_TRIANGLES_MAX,
                          'static_groups':len(counts), 'animated_actors':len(animated),
                          'animated_triangles':sum(animated.values())}
        reports[level]['ok'] = (sum(counts.values()) <= limit and hull <= ANIME_HULL_TRIANGLES_MAX and len(counts) <= STATIC_GROUPS_MAX
                                 and len(animated) <= 16)
    print(json.dumps(reports, indent=2, sort_keys=True))
    raise SystemExit(0 if all(row['ok'] for row in reports.values()) else 1)
sys.path.insert(0, str(args.repo/'wflevels'/'aquarium_tanks'))
from mesh import Mesh
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
