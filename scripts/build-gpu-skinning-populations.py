#!/usr/bin/env python3
"""Generate controlled 1/4/16-body DFRM scenes from reviewed aquarium sources.

Uses the existing compiled level tools; records their hashes. This is a DFRM
population test, not a performance claim about general four-weight LBS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'wflevels/aquarium_plants'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field(block, name, value, kind='STR'):
    pattern = r"(\{ '(?:STR|FILE|I32|FX32)'\s+\{ 'NAME' " + re.escape(json.dumps(name)) + r" \} )(.*?)( \}\s*(?://[^\n]*)?$)"
    replacement = "{ 'STR' " + json.dumps(str(value)) + ' }'
    if kind == 'I32':
        replacement = "{ 'DATA' " + str(value) + "l } " + replacement
    changed, count = re.subn(pattern, lambda m: m[1] + replacement + m[3], block, flags=re.M)
    if count != 1 and not (name in ('Mesh Name', 'Model Type') and count == 2):
        raise ValueError(f'Expected one {name}, got {count}')
    return changed


def vector(block, name, values):
    pattern = r"(\{ '(?:VEC3|EULR)' \{ 'NAME' " + re.escape(json.dumps(name)) + r" \} \{ 'DATA' )[^\n]+"
    changed, count = re.subn(pattern, lambda m: m[1] + ' '.join(f'{v:.12f}(1.15.16)' for v in values), block)
    if count != 1:
        raise ValueError(f'Expected one vector {name}')
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools-root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tools = {name: args.tools_root / f'wftools/{name}-rs/target/release/{name}' for name in ['iffcomp', 'levcomp', 'textile']}
    receipt = dict(source_lev_sha256=sha(SOURCE / 'aquarium_plants.lev'),
                   body_sha256=sha(SOURCE / 'seahorse_f_body.iff'),
                   tools={k: dict(path=str(p), sha256=sha(p)) for k, p in tools.items()},
                   scope='868-vertex, 35-sample DFRM body only; no fins, plants or behavior AI', populations={})
    text = (SOURCE / 'aquarium_plants.lev').read_text()
    blocks = text.split("\t{ 'OBJ'\n")[1:]
    blocks[-1] = blocks[-1].rsplit('}', 1)[0]
    objects = {json.loads(re.search(r"\{ 'NAME' (\"(?:\\.|[^\"\\])*\") \}", b)[1]): "\t{ 'OBJ'\n" + b for b in blocks}
    keep = ['Room', 'SunLight', 'Camera', 'Director', 'LevelObj', 'Matte', 'cs_wide', 'LookAt', 'Player', 'AmbientLight']
    for population in [1, 4, 16]:
        name = f'skin_population_{population}'
        directory = args.out / name
        directory.mkdir(exist_ok=True)
        chosen = [objects[n] for n in keep]
        chosen[3] = field(chosen[3], 'Script', '')
        chosen[8] = field(chosen[8], 'Script', '')
        chosen[8] = field(chosen[8], 'Visibility Mailbox', 0, 'I32')
        chosen[8] = field(chosen[8], 'Mobility', 'Anchored')
        chosen[8] = field(chosen[8], 'Model Type', 'None')
        chosen[8] = field(chosen[8], 'Mesh Name', '')
        # No adjacent room survives this reduced source.
        chosen[0] = field(chosen[0], 'Adjacent Room 1', '')
        # Keep one invisible room asset so the existing cooker emits RM0,
        # rather than its legacy FAKE TOC entry for levels with no room assets.
        chosen.append(field(objects['tank-base'], 'Visibility Mailbox', 0, 'I32'))
        body_indices = []
        for i in range(population):
            b = objects['seahorse-0-body'].replace('{ \'NAME\' "seahorse-0-body" }', '{ \'NAME\' ' + json.dumps(f'rig-{i:02d}') + ' }', 1)
            cols = min(4, population)
            x = (i % cols - (cols - 1) / 2) * 2.3
            z = .8 + (i // cols) * 1.9
            b = vector(b, 'Position', (x, 0, z))
            b = vector(b, 'Orientation', (0, 0, .35 * (i % 3 - 1)))
            b = field(b, 'Visibility Mailbox', 1, 'I32')
            body_indices.append(len(chosen) + 1)
            chosen.append(b)
        # One reusable 40-cell mailbox block; each dfrm-pose samples and owns
        # its actor's complete pose before the next actor reuses the inputs.
        script = '7 INDEXOF_CAMSHOT write-mailbox\n'
        script += '\n'.join(f'0 {1200+k} write-mailbox' for k in range(33)) + '\n'
        script += '1 1225 write-mailbox\n20 1230 write-mailbox\n'
        for i, actor in enumerate(body_indices):
            script += f'{-i*.13:.5f} 1226 write-mailbox 1200 {actor} dfrm-pose drop\n'
        chosen[3] = field(chosen[3], 'Script', script)
        lev = directory / (name + '.lev')
        lev.write_text("{ 'LVL'\n" + ''.join(chosen) + '}\n')
        # Only the referenced mesh and texture are copied, never modified.
        for mesh in ['seahorse_f_body.iff', 'seahorse_atlas.tga', 'tank_base.iff']:
            src = SOURCE / mesh
            if src.exists():
                shutil.copyfile(src, directory / mesh)
        # A copied source texture is resolved by textile using the source name.
        subprocess.run([str(tools['iffcomp']), '-binary', '-o=' + name + '.lev.bin', lev.name], cwd=directory, check=True)
        subprocess.run([str(tools['levcomp']), name + '.lev.bin', str(ROOT / 'wfsource/source/oas/objects.lc'), name + '.lvl',
                        str(ROOT / 'wfsource/source/oas'), '--mesh-dir', '.', '--iff-txt', name + '.iff.txt', '--textile-ini', name + '.ini'], cwd=directory, check=True)
        subprocess.run([str(tools['textile']), '-ini=' + name + '.ini', '-Tlinux', '-transparent=0,0,0',
                        '-pagex=512', '-pagey=512', '-permpagex=1024', '-permpagey=1024', '-palx=256', '-paly=8',
                        '-alignx=w', '-aligny=h', '-flipyout', '-powerof2size'], cwd=directory, check=True)
        subprocess.run([str(tools['iffcomp']), '-binary', '-o=' + name + '.iff', name + '.iff.txt'], cwd=directory, check=True)
        wrapper = directory / (name + '-standalone.iff.txt')
        wrapper.write_text("{ 'L4' { 'ALGN' .align(2048) } { 'RAM' 'OBJD' 1000000l 'PERM' 8000000l 'ROOM' 24000000l 'FLAG' 1l 1l 'SLOT' 1l } { 'ALGN' .align(2048) } [ \"" + name + '.iff" ] }\n')
        standalone = directory / (name + '-standalone.iff')
        subprocess.run([str(tools['iffcomp']), '-binary', '-o=' + standalone.name, wrapper.name], cwd=directory, check=True)
        receipt['populations'][str(population)] = dict(actors=body_indices, lev_sha256=sha(lev), standalone_sha256=sha(standalone), standalone=str(standalone.resolve()))
    (args.out / 'populations.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
