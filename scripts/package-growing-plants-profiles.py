#!/usr/bin/env python3
"""Package matched plant snapshots using one native binary, with archived identities."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apk',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
# Keep the current selector and other seven tanks even for the archived baseline.
old_level=a.out/'old-static-plants.iff'
old_level.write_bytes(subprocess.check_output(['git','show','2b515ae8:wflevels/aquarium_plants-standalone.iff'],cwd=ROOT))
manifest=a.out/'old-static.manifest'
lines=[]
for line in (ROOT/'wflevels/aquarium-menu.manifest').read_text().splitlines():
 if line.startswith('level '):
  filename,title=line.removeprefix('level ').split(' | ',1)
  path=old_level.resolve() if filename=='aquarium_plants-standalone.iff' else ROOT/'wflevels'/filename
  line=f'level {path} | {title}'
 lines.append(line)
manifest.write_text('\n'.join(lines)+'\n')
old_cd=a.out/'old-static-menu.iff'
subprocess.run([str(ROOT/'wftools/cdpack-rs/target/release/cdpack'),str(ROOT/'wfsource/source/game/shell-menu.fth'),'--manifest',str(manifest),'-o',str(old_cd)],check=True)
old=old_cd.read_bytes()
with zipfile.ZipFile(a.apk) as frozen:current=frozen.read('assets/cd.iff')
buildtools=Path('/home/will/android-sdk-local/build-tools/34.0.0')
cases=[dict(name='old-static',args='',cd=old)]
for mode in ['freshwater','saltwater']:
 for age,label in [(0,'young'),(30,'spreading'),(150,'mature')]:
  cases.append(dict(name=mode+'-'+label+'-static',args=f'--plant-seed=713\n--plant-water={mode}\n--plant-age={age}\n--plant-speed=0\n--plant-sway=0\n',cd=current))
 cases.append(dict(name=mode+'-mature-sway',args=f'--plant-seed=713\n--plant-water={mode}\n--plant-age=150\n--plant-speed=0\n',cd=current))
 cases.append(dict(name=mode+'-growing',args=f'--plant-seed=713\n--plant-water={mode}\n--plant-age=30\n--plant-speed=0\n',cd=current,growth_speed=3))
for mode in ['freshwater','saltwater']:
 for seed in [0,4294967295]:cases.append(dict(name=f'{mode}-seed-{seed}',args=f'--plant-seed={seed}\n--plant-water={mode}\n--plant-age=150\n--plant-speed=0\n--plant-sway=0\n',cd=current))

# Paired controls share both the native library and the textured level payload.
for mode in ['freshwater','saltwater']:
 for label in ['mature-static','mature-sway']:
  original=next(c for c in cases if c['name']==mode+'-'+label)
  cases.append(dict(original,name=original['name']+'-shaded',args=original['args']+'--plant-texture=0\n'))
receipts=[]
with zipfile.ZipFile(a.apk) as base:
 native={n:hashlib.sha256(base.read(n)).hexdigest() for n in base.namelist() if n.startswith('lib/')}
 for case in cases:
  for cpu in [False,True]:
   name=case['name']+('-cpu' if cpu else '');unsigned=a.out/(name+'-unsigned.apk');aligned=a.out/(name+'-aligned.apk');apk=a.out/(name+'.apk')
   args=case['args']+('--frame-profile\n' if cpu else '')
   with zipfile.ZipFile(unsigned,'w') as dst:
    for item in base.infolist():
     if item.filename.startswith('META-INF/') or item.filename in ['assets/cd.iff','assets/wf_args.txt']:continue
     from copy import copy
     dst.writestr(copy(item),base.read(item.filename))
    dst.writestr('assets/cd.iff',case['cd'],compress_type=zipfile.ZIP_DEFLATED)
    dst.writestr('assets/wf_args.txt',args)
   subprocess.run([str(buildtools/'zipalign'),'-f','-p','4',str(unsigned),str(aligned)],check=True)
   subprocess.run([str(buildtools/'apksigner'),'sign','--ks',str(Path.home()/'.android/debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--out',str(apk),str(aligned)],check=True)
   unsigned.unlink();aligned.unlink()
   with zipfile.ZipFile(apk) as signed:assert all(hashlib.sha256(signed.read(n)).hexdigest()==h for n,h in native.items())
   receipts.append(dict(name=name,apk_sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),cd_sha256=hashlib.sha256(case['cd']).hexdigest(),args=args,growth_speed=case.get('growth_speed'),native=native))
(a.out/'identities.json').write_text(json.dumps(receipts,indent=2)+'\n');print('Packaged',len(receipts),'matched APKs',flush=True)
