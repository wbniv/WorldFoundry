#!/usr/bin/env python3
"""Build the geometry-only style scenes for the GL-vs-Metal check (reef plan step 14).

Each is a reduced copy of a reef level: the shell (sand and back walls) and the
three hero rocks, under the reef's own Camera, lights and fog. It has no fish,
fins, antennae, coral tips or other sub-pixel silhouettes, so a strict per-channel
comparison tests the S1 absorption (style_geom_realistic, from aquarium_thai_reef)
and S3 band (style_geom_anime, from aquarium_thai_reef_anime) math rather than
rasterizer coverage. The Director only selects the wide camera; the Player is kept
for level startup but drawn nowhere. Run in the level-build container
(WF_CONTAINER_IMAGE=blender) with --build.
"""
import argparse
import re
import runpy
import subprocess
from pathlib import Path

from level_asset_links import link_source_assets

ROOT = Path(__file__).resolve().parents[1]
grid = runpy.run_path(str(ROOT / 'scripts/build-seahorse-grid-level.py'))
NAME, KEEP, replace_script = grid['NAME'], grid['KEEP'], grid['replace_script']
GEOMETRY = ('reef_shell', 'reef_left', 'reef_arch', 'reef_right')
VISIBILITY = re.compile(r"(\{ 'I32' \{ 'NAME' \"Visibility Mailbox\" \} \{ 'DATA' )\d+l( \} \{ 'STR' )\"\d+\"")
SCENES = {'style_geom_realistic': 'aquarium_thai_reef', 'style_geom_anime': 'aquarium_thai_reef_anime'}


def visible(block, value):
    block, count = VISIBILITY.subn(lambda m: f'{m[1]}{value}l{m[2]}"{value}"', block, count=1)
    if count != 1:
        raise ValueError('object has no Visibility Mailbox field')
    return block


def generate(name, source_name, build):
    source_dir = ROOT / 'wflevels' / source_name
    source = (source_dir / f'{source_name}.lev').read_text()
    end = source.rfind('\n}')
    head, *chunks = source[:end].split("\t{ 'OBJ'")
    blocks = {NAME.search(chunk).group(1): chunk for chunk in chunks}
    wanted = (KEEP | set(GEOMETRY)) & blocks.keys()
    if not set(GEOMETRY) <= wanted or not {'Camera', 'Director', 'Player', 'cs_wide'} <= wanted:
        raise ValueError(f'{source_name}: missing objects {(KEEP | set(GEOMETRY)) - blocks.keys()}')
    ordered = [n for n in blocks if n in wanted]
    output = {n: blocks[n] for n in ordered}
    # The rocks normally show through the layout's module cells (200-202); here they
    # are always visible at their authored (Fixed) placements.
    for rock in GEOMETRY[1:]:
        output[rock] = visible(output[rock], 1)
    output['Player'] = visible(replace_script(output['Player'], '0 INDEXOF_INPUT write-mailbox\n'), 0)
    indices = {n: i + 1 for i, n in enumerate(ordered)}
    output['Director'] = replace_script(output['Director'], f"{indices['cs_wide']} INDEXOF_CAMSHOT write-mailbox\n")
    target = ROOT / 'wflevels' / name
    target.mkdir(exist_ok=True)
    link_source_assets(source_dir, target)
    (target / f'{name}.lev').write_text(head + "\t{ 'OBJ'" + "\t{ 'OBJ'".join(output[n] for n in ordered) + source[end:])
    wrapper = (source_dir / f'{source_name}-standalone.iff.txt').read_text()
    (target / f'{name}-standalone.iff.txt').write_text(wrapper.replace(f'../{source_name}.iff', f'../{name}.iff'))
    if build:
        subprocess.run(['bash', 'wftools/wf_blender/build_level_binary.sh', name], cwd=ROOT, check=True)
    print(name, 'objects:', ', '.join(ordered))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--build', action='store_true', help='also compile both levels with the Rust tools')
    args = ap.parse_args()
    for name, source_name in SCENES.items():
        generate(name, source_name, args.build)


if __name__ == '__main__':
    main()
