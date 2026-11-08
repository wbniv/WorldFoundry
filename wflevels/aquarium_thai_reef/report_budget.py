#!/usr/bin/env python3
"""Report the reef's static budgets; --cooked checks the most recent export of both styles.

--cooked reads each style's actor-map.json and cooked level files and checks, per style:
  * the Fixed arrangement: <= STATIC_GROUPS_MAX groups and the style's static-triangle limit;
  * the worst set the Random layout can show at once (plan W5b: 3 heroes with their dressing,
    the 2 largest fillers, every colony clump): <= KIT_VISIBLE_GROUPS_MAX groups and
    KIT_VISIBLE_TRIANGLES_MAX triangles, and its anime outline hulls <= ANIME_HULL_TRIANGLES_MAX;
  * the Room #0 asset slot with every piece loaded <= ROOM_SLOT_BYTES (R0 report section 9):
    room mesh files + per mesh actor 24*V + 20*(F+1) + 88*F + 380 bytes (needs the cooked
    <level>.iff.txt, so run it after wftools/wf_blender/build_level_binary.sh);
  * at most 16 animated actors.
It exits non-zero when any check fails, so build.sh fails the build.
"""
import argparse
import json
import re
import struct
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (ANIME_HULL_TRIANGLES_MAX, ANIME_STATIC_TRIANGLES_MAX, KIT_VISIBLE_GROUPS_MAX,  # noqa: E402
                    KIT_VISIBLE_TRIANGLES_MAX, ROOM_SLOT_BYTES, STATIC_GROUPS_MAX, STATIC_TRIANGLES_MAX)

PER_ACTOR = 380


def _chunks(data, off, end):
    while off + 8 <= end:
        tag = data[off:off + 4]
        size = struct.unpack_from('<I', data, off + 4)[0]
        yield tag, off + 8, size
        off += 8 + size + ((4 - (size & 3)) & 3)


def _mesh_counts(path):
    data = path.read_bytes()
    tag, start, size = next(_chunks(data, 0, len(data)))
    vertices = faces = 0
    for t, _, s in _chunks(data, start, start + size):
        if t == b'VRTX':
            vertices = s // 24
        elif t == b'FACE':
            faces = s // 8
    return vertices, faces


def room_slot_bytes(level_dir):
    """Modelled Room #0 slot use of a cooked level: (bytes, mesh-file bytes, actor count)."""
    level_dir = Path(level_dir)
    name = level_dir.name
    txt = (level_dir / f'{name}.iff.txt').read_text()
    rm0 = re.search(r"\{ 'RM0'(.*?)\n\t\}", txt, re.S).group(1)
    meshes = [f for f in re.findall(r'\[ "([^"]+)" \]', rm0) if f.endswith('.iff')]
    files = sum((level_dir / f).stat().st_size for f in meshes)
    copies = actors = 0
    for block in (level_dir / f'{name}.lev').read_text().split("\t{ 'OBJ'")[1:]:
        m = re.search(r'"Mesh Name" \} \{ \'STR\' "([^"]+)"', block)
        if m and m.group(1) in meshes:
            v, f = _mesh_counts(level_dir / m.group(1))
            copies += 24 * v + 20 * (f + 1) + 88 * f + PER_ACTOR
            actors += 1
    return files + copies, files, actors


def cooked_report(repo, only=None):
    reports = {}
    for level, style, limit in (('aquarium_thai_reef', 'realistic', STATIC_TRIANGLES_MAX),
                                ('aquarium_thai_reef_anime', 'anime', ANIME_STATIC_TRIANGLES_MAX)):
        if only and level != only:
            continue
        folder = repo / 'wflevels' / level
        data = json.loads((folder / 'actor-map.json').read_text())
        fixed, worst = data['kit_budget']['fixed'], data['kit_budget']['worst_visible']
        slot, files, actors = room_slot_bytes(folder)
        row = {'fixed_groups': fixed['groups'], 'fixed_triangles': fixed['triangles'], 'fixed_limit': limit,
               'worst_groups': worst['groups'], 'worst_triangles': worst['triangles'],
               'worst_limit': KIT_VISIBLE_TRIANGLES_MAX[style], 'worst_hull_triangles': worst['hull_triangles'],
               'hull_limit': ANIME_HULL_TRIANGLES_MAX, 'room_slot_bytes': slot, 'room_mesh_file_bytes': files,
               'room_mesh_actors': actors, 'room_slot_limit': ROOM_SLOT_BYTES,
               'animated_actors': len(data['animated_triangles'])}
        row['ok'] = (fixed['groups'] <= STATIC_GROUPS_MAX and fixed['triangles'] <= limit
                     and worst['groups'] <= KIT_VISIBLE_GROUPS_MAX
                     and worst['triangles'] <= KIT_VISIBLE_TRIANGLES_MAX[style]
                     and worst['hull_triangles'] <= ANIME_HULL_TRIANGLES_MAX
                     and slot <= ROOM_SLOT_BYTES and row['animated_actors'] <= 16)
        reports[level] = row
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', type=Path, default=ROOT, help='repository with aquarium_tanks/mesh.py')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--cooked', action='store_true', help='check the most recent export of both styles')
    parser.add_argument('--level', choices=('aquarium_thai_reef', 'aquarium_thai_reef_anime'),
                        help='with --cooked: check only this style (build.sh checks the style it built)')
    args = parser.parse_args()
    if args.cooked:
        reports = cooked_report(args.repo, args.level)
        print(json.dumps(reports, indent=2, sort_keys=True))
        raise SystemExit(0 if all(row['ok'] for row in reports.values()) else 1)
    sys.path.insert(0, str(args.repo / 'wflevels' / 'aquarium_tanks'))
    from mesh import Mesh
    from reef.geometry import build_groups, triangles
    groups = build_groups(Mesh)
    counts = {name: triangles(mesh) for name, mesh in groups.items()}
    total = sum(counts.values())
    ok = len(counts) <= STATIC_GROUPS_MAX and total <= STATIC_TRIANGLES_MAX
    if args.json:
        print(json.dumps({'kind': 'generated-blockout', 'groups': counts, 'total': total,
                          'group_limit': STATIC_GROUPS_MAX, 'triangle_limit': STATIC_TRIANGLES_MAX,
                          'ok': ok}, sort_keys=True, indent=2))
    else:
        for name, n in counts.items():
            print(f'{name:18} {n:6} triangles')
        print(f'Total {total}/{STATIC_TRIANGLES_MAX} triangles; {len(counts)}/{STATIC_GROUPS_MAX} groups')


if __name__ == '__main__':
    main()
