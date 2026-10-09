#!/usr/bin/env python3
"""Freeze matched atlas-resolution APKs without changing production assets."""
import argparse
from copy import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
from PIL import Image
from plant_settings_catalog import configure_cd,configure_level,require_catalog_runtime,reject_removed_arguments

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--apk', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--sizes', type=int, nargs='+', default=[256,128], choices=[128,256,512])
a = p.parse_args()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=True)
normal = a.out / 'normal.apk'
shutil.copyfile(a.apk, normal)
sha = lambda data: hashlib.sha256(data).hexdigest()
with zipfile.ZipFile(normal) as base:
    require_catalog_runtime(base)
    if 'assets/wf_args.txt' in base.namelist():reject_removed_arguments(base.read('assets/wf_args.txt').decode())
    runtime_args = base.read('assets/wf_args.txt').decode() if 'assets/wf_args.txt' in base.namelist() else ''
    permanent_size = Image.open(ROOT/'wflevels/aquarium_plants/Perm.tga').size
    native = {n: sha(base.read(n)) for n in base.namelist() if n.startswith('lib/')}
    assert base.read('assets/cd.iff') == (ROOT/'wflevels/aquarium-menu-cd.iff').read_bytes()
    identities = []
    pages = []
    for size in a.sizes:
        parent = a.out / str(size)
        level = parent / 'aquarium_plants'
        shutil.copytree(ROOT/'wflevels/aquarium_plants', level, dirs_exist_ok=True)
        atlas = Image.open(level/'leaf-surfaces-atlas.png').convert('RGB')
        if size == 128:
            atlas = atlas.resize((size, size), Image.Resampling.LANCZOS)
        elif size == 512:
            # Repack the original art, rather than enlarging the deployed map.
            source = Image.open(level/'leaf-surfaces-source.png').convert('RGB')
            atlas = Image.new('RGB',(512,512),(120,138,72))
            for tile in range(6):
                col,row=tile%3,tile//3
                region=source.crop((col*source.width//3,row*source.height//2,(col+1)*source.width//3,(row+1)*source.height//2))
                interior=region.resize((144,224),Image.Resampling.LANCZOS)
                x,y=col*160+8,row*240+8
                atlas.paste(interior,(x,y))
                atlas.paste(interior.crop((0,0,1,224)).resize((8,224)),(x-8,y))
                atlas.paste(interior.crop((143,0,144,224)).resize((8,224)),(x+144,y))
                atlas.paste(atlas.crop((x-8,y,x+152,y+1)).resize((160,8)),(x-8,y-8))
                atlas.paste(atlas.crop((x-8,y+223,x+152,y+224)).resize((160,8)),(x-8,y+224))
        atlas.save(level/'leaf-surfaces-atlas.png')
        atlas.save(level/'leaf_surfaces.tga')
        subprocess.run([str(ROOT/'wftools/textile-rs/target/release/textile'),
            '-ini=aquarium_plants.ini', '-Tlinux', '-transparent=0,0,0',
            f'-pagex={size}', f'-pagey={size}', f'-permpagex={permanent_size[0]}', f'-permpagey={permanent_size[1]}',
            '-palx=256', '-paly=8', '-alignx=w', '-aligny=h', '-flipyout', '-powerof2size'], cwd=level, check=True)
        assert Image.open(level/'Room0.tga').size == (size, size)
        for source in (ROOT/'wflevels/aquarium_plants').glob('*.iff'):
            assert source.read_bytes() == (level/source.name).read_bytes(), source
        assert (level/'aquarium_plants.lvl').read_bytes() == (ROOT/'wflevels/aquarium_plants/aquarium_plants.lvl').read_bytes()
        for stem in ('aquarium_plants', 'aquarium_plants-standalone'):
            subprocess.run([str(ROOT/'wftools/iffcomp-rs/target/release/iffcomp'), '-binary',
                f'-o=../{stem}.iff', f'{stem}.iff.txt'], cwd=level, check=True)
        standalone=parent/'aquarium_plants-standalone.iff'
        standalone.write_bytes(configure_level(standalone.read_bytes(),{})[0])
        if size == 256:
            assert (parent/'aquarium_plants-standalone.iff').read_bytes() == (ROOT/'wflevels/aquarium_plants-standalone.iff').read_bytes(), '256 control differs from production'
        manifest = parent/'menu.manifest'
        lines = []
        for line in (ROOT/'wflevels/aquarium-menu.manifest').read_text().splitlines():
            if line.startswith('level '):
                filename, title = line[6:].split(' | ', 1)
                path = parent/filename if filename == 'aquarium_plants-standalone.iff' else ROOT/'wflevels'/filename
                line = f'level {path} | {title}'
            lines.append(line)
        manifest.write_text('\n'.join(lines)+'\n')
        cd = parent/'cd.iff'
        subprocess.run([str(ROOT/'wftools/cdpack-rs/target/release/cdpack'), str(ROOT/'wfsource/source/game/shell-menu.fth'), '--manifest', str(manifest), '-o', str(cd)], check=True)
        pages.append(dict(size=size, packed_page_bytes=(level/'Room0.tga').stat().st_size,
            pixel_payload_bytes=size*size*2, atlas_png_bytes=(level/'leaf-surfaces-atlas.png').stat().st_size,
            room_slot_size=max(256,size), source='original artwork repacked' if size==512 else 'production atlas' if size==256 else 'production atlas downsampled',
            global_vram_height=1024 if size==512 else 512,
            level_sha256=sha((parent/'aquarium_plants-standalone.iff').read_bytes())))
        for water in ('freshwater', 'saltwater'):
            for cpu in (False, True):
                name = f'{water}-{size}'+('-cpu' if cpu else '')
                fixture_cd,plant_catalog=configure_cd(cd.read_bytes(),dict(seed=713,water=water,age=150,speed=0,sway=False))
                args = runtime_args + ('--frame-profile\n' if cpu else '')
                if size == 512:
                    args += '--vram-slot-width=512\n--vram-slot-height=512\n--vram-height=1024\n'
                unsigned, aligned, apk = (a.out/(name+suffix) for suffix in ('-unsigned.apk','-aligned.apk','.apk'))
                with zipfile.ZipFile(unsigned, 'w') as dst:
                    for item in base.infolist():
                        if item.filename.startswith('META-INF/') or item.filename in ('assets/cd.iff','assets/wf_args.txt'): continue
                        dst.writestr(copy(item), base.read(item.filename))
                    dst.writestr('assets/cd.iff', fixture_cd, compress_type=zipfile.ZIP_DEFLATED)
                    dst.writestr('assets/wf_args.txt', args)
                bt = Path('/home/will/android-sdk-local/build-tools/34.0.0')
                subprocess.run([str(bt/'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
                subprocess.run([str(bt/'apksigner'), 'sign', '--ks', str(Path.home()/'.android/debug.keystore'), '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', str(apk), str(aligned)], check=True)
                unsigned.unlink(); aligned.unlink()
                with zipfile.ZipFile(apk) as signed:
                    assert {n:sha(signed.read(n)) for n in native} == native
                identities.append(dict(name=name, apk_sha256=sha(apk.read_bytes()), native=native, args=args,plant_catalog=plant_catalog, cd_sha256=sha(fixture_cd)))
    (a.out/'identities.json').write_text(json.dumps(identities, indent=2)+'\n')
    (a.out/'pages.json').write_text(json.dumps(pages, indent=2)+'\n')
    labels = [v['name'] for v in identities]
    labels.sort(key=lambda n: (n.endswith('-cpu'), n.split('-')[0], '-128' in n))
    recipe = dict(device='chromecast-test-01', workflow='variant-benchmark', app='aquarium', scene='planted-tank', trace='plants', duration=12, warmup=30,
        apk=str(normal), restore_apk=str(normal), variants=[dict(label=n, apk=str(a.out/(n+'.apk')), runs=1 if n.endswith('-cpu') else 3, warmup=30) for n in labels])
    (a.out/'recipe.json').write_text(json.dumps(recipe, indent=2)+'\n')
    print('Frozen normal SHA256:', sha(normal.read_bytes()))
    print('Recipe:', a.out/'recipe.json')
