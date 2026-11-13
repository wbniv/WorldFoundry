#!/usr/bin/env python3
"""Create the two matched DFRM device-benchmark levels from the planted shell.

Run in the level-build container. Generated levels are disposable diagnostic
artifacts; the test still needs a diagnostic APK and measured device runs.
"""
import argparse
import json
import re
import runpy
import subprocess
from pathlib import Path

from level_asset_links import link_source_assets

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'wflevels/aquarium_plants'
grid = runpy.run_path(str(ROOT / 'scripts/build-seahorse-grid-level.py'))
mesh = runpy.run_path(str(ROOT / 'scripts/generate-dfrm-merge-bench.py'))
KEEP = grid['KEEP']
NAME = grid['NAME']
place, set_position, replace_script = (grid[n] for n in ('place', 'set_position', 'replace_script'))


def controller(indices, merged):
    """Both variants pose every sample by the same time-dependent flex."""
    lines = [': bm@ read-mailbox ; : bm! write-mailbox ;',
             ': bm-frac begin dup 1 >= if 1 - 0 else 1 then until ;',
             ': bm-angle INDEXOF_TIME bm@ bm-frac .5 - 30 * ;',
             ': bm-check 0 <> if 1 99 bm! then ;',
             ': bm-init 198 bm@ 0 = if']
    # Same initialization work in both variants. The v2 records need scale 1.
    lines.extend(f'  1 {240 + 4*i} bm!' for i in range(15))
    lines += ['  1 198 bm! then ;', ': bm-tick bm-init',
              f'  {indices["cs_wide"]} INDEXOF_CAMSHOT bm!', '  bm-angle']
    if merged:
        targets = [200, 203] + [243 + 4*i for i in range(1, 15)]
        lines.extend(f'  dup {target} bm!' for target in targets[:-1])
        lines += [f'  {targets[-1]} bm!', f'  200 15 {indices["crowns"]} dfrm-pose-curves bm-check']
    else:
        lines += ['  dup 100 bm! 103 bm!']
        lines += [f'  100 {indices[f"crown-{i:02d}"]} dfrm-pose bm-check' for i in range(15)]
    return '\n'.join(lines + [';', 'bm-tick', ''])


def generate_scene(source, merged):
    end = source.rfind('\n}')
    if end < 0:
        raise ValueError('planted level has no closing LVL brace')
    head, *chunks = source[:end].split("\t{ 'OBJ'")
    blocks = {NAME.search(chunk).group(1): chunk for chunk in chunks}
    if not KEEP <= blocks.keys() or 'seahorse-0-body' not in blocks:
        raise ValueError('planted level is missing required template objects')
    ordered = [name for name in blocks if name in KEEP]
    output = [blocks[name] for name in ordered]
    for name in ('Camera', 'cs_wide'):
        output[ordered.index(name)] = set_position(output[ordered.index(name)], 2, -9, .9)
    output[ordered.index('LookAt')] = set_position(output[ordered.index('LookAt')], 2, 0, .9)
    player = ordered.index('Player')
    output[player] = replace_script(output[player], '0 INDEXOF_INPUT write-mailbox\n')
    # The player exists for level startup but contributes no visible geometry.
    output[player] = re.sub(r'(\{ \'NAME\' "Visibility Mailbox" \} \{ \'DATA\' )\d+l( \} \{ \'STR\' )"\d+"',
                            r'\g<1>0l\g<2>"0"', output[player], count=1)
    for i in range(1 if merged else 15):
        name = 'crowns' if merged else f'crown-{i:02d}'
        x, z = (0, 0) if merged else (i % 5, (i // 5) * .75)
        block = place(blocks['seahorse-0-body'], name, x, 0, z, room_local=True)
        model = 'crowns-merged.iff' if merged else 'crown-single.iff'
        block = block.replace('seahorse_f_body.iff', model)
        bounds = '-.25 -.25 0 4.25 .25 1.9' if merged else '-.25 -.25 0 .25 .25 .4'
        vals = ' '.join(f'{float(n):.6f}(1.15.16)' for n in bounds.split())
        block, changed = re.subn(r"(\{ 'BOX3' \{ 'NAME' \"Global Bounding Box\" \} \{ 'DATA' )[^\n]+",
                                 lambda m: m.group(1) + vals + '  //min(x,y,z)-max(x,y,z)', block, count=1)
        if changed != 1:
            raise ValueError('actor bounding box missing')
        output.append(block)
        ordered.append(name)
    indices = {name: i + 1 for i, name in enumerate(ordered)}
    output[ordered.index('Director')] = replace_script(output[ordered.index('Director')], controller(indices, merged))
    return head + "\t{ 'OBJ'" + "\t{ 'OBJ'".join(output) + source[end:], indices


def generate(build, bundle=None):
    source = (SOURCE / 'aquarium_plants.lev').read_text()
    for merged, name in ((False, 'dfrm_bench_single'), (True, 'dfrm_bench_merged')):
        target = ROOT / 'wflevels' / name
        target.mkdir(exist_ok=True)
        link_source_assets(SOURCE, target)
        positions, faces, payload = mesh['make'](15 if merged else 1)
        model = 'crowns-merged.iff' if merged else 'crown-single.iff'
        (target / model).write_bytes(mesh['ref'].modl(positions, faces, payload))
        level, indices = generate_scene(source, merged)
        (target / (name + '.lev')).write_text(level)
        (target / (name + '-standalone.iff.txt')).write_text(
            "{ 'L4'\n { 'ALGN' .align( 2048 ) }\n"
            " { 'RAM' 'OBJD' 1000000l 'PERM' 12000000l 'ROOM' 24000000l 'FLAG' 1l 1l 'SLOT' 1l }\n"
            " { 'ALGN' .align( 2048 ) }\n [ \"../" + name + ".iff\" ]\n}\n")
        (target / 'bench-manifest.json').write_text(json.dumps({'indices': indices, 'triangles': 180,
            'deformed_actors': 1 if merged else 15, 'status_mailbox': 99}, indent=2) + '\n')
        if build:
            subprocess.run(['bash', 'wftools/wf_blender/build_level_binary.sh', name], cwd=ROOT, check=True)
    manifest = ROOT / 'wflevels/dfrm-bench.manifest'
    manifest.write_text('title DFRM Benchmark\nprompt Choose a variant\n'
                        'level dfrm_bench_single-standalone.iff | 15 separate crowns\n'
                        'level dfrm_bench_merged-standalone.iff | 15 merged crowns\n')
    if bundle:
        subprocess.run([str(ROOT / 'wftools/cdpack-rs/target/release/cdpack'),
                        'wfsource/source/game/shell-menu.fth', '--manifest', str(manifest),
                        '-o', str(bundle)], cwd=ROOT, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='also compile both levels with the existing Rust tools')
    parser.add_argument('--bundle', type=Path, help='package both compiled levels into a selector CD')
    args = parser.parse_args()
    generate(args.build, args.bundle)
