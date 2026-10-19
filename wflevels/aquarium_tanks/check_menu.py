#!/usr/bin/env python3
"""Check desktop engine selection and return for the snapshot or canonical menu."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from level_menu_harness import read_menu,read_toc
import argparse
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--installed-bundle', action='store_true', help='Check the canonical seven-tank Android bundle')
a = ap.parse_args()
if a.installed_bundle:
    preview=HERE/'preview-installed'
    preview.mkdir(exist_ok=True)
    import shutil
    shutil.copyfile(ROOT/'wflevels/aquarium-menu-cd.iff', preview/'cd.iff')
else:
    subprocess.run([sys.executable,str(HERE/'build_menu.py')],check=True)
    preview=HERE/'preview'
data=(preview/'cd.iff').read_bytes()
menu=read_menu(data)
titles=(['Clownfish & Tiger Barbs','Blue Shrimp','Calm Betta','Jellyfish','Lionfish','Planted Tank','Asian Arowana'] if a.installed_bundle else ['Original Aquarium','Blue Shrimp','Calm Betta','Jellyfish','Lionfish','Planted Tank'])
assert menu['entries']==list(enumerate(titles))
if a.installed_bundle:
    sources=[dict(level=level,title=title,sha256=hashlib.sha256((ROOT/'wflevels'/(level+'-standalone.iff')).read_bytes()).hexdigest()) for level,title in zip(['aquarium','aquarium_blue_shrimp','aquarium_betta','aquarium_jellyfish','aquarium_lionfish','aquarium_plants','aquarium_arowana'],titles)]
else:
    sources=json.loads((preview/'sources.json').read_text())
toc=read_toc(data)
for (_,off,size),row in zip(toc[1:1+len(sources)],sources):
    assert hashlib.sha256(data[off:off+size]).hexdigest()==row['sha256']
out=ROOT/'docs/plans/2026-10-02-aquarium-three-more-tanks/engine/menu'
if a.installed_bundle: out=out/'integrated-seven'
out.mkdir(parents=True,exist_ok=True)
# Selection memory means each new menu starts on its previous tank.
script='wait:10,down,down,down,down,down,a,wait:100,back,wait:10,up,up,up,a,wait:100,back,wait:10,down,a,wait:100,back,wait:10,down,a,wait:100,back,wait:10,up,up,up,up,a,wait:100,back,wait:10,down,a,wait:100,back,wait:10,down,down,down,down,a,wait:100,quit'
if a.installed_bundle:
    script='wait:10,down,down,down,down,down,down,a,wait:100,back,wait:10,up,a,wait:100,back,wait:10,up,up,up,a,wait:100,back,wait:10,down,a,wait:100,back,wait:10,down,a,wait:100,back,wait:10,up,up,up,up,a,wait:100,back,wait:10,down,a,wait:100,back,wait:10,down,down,down,down,down,a,wait:100,quit'
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs')+':'+os.environ.get('LD_LIBRARY_PATH',''))
env.update(WF_REST_HOST='127.0.0.1',WF_REST_PORT='18924')
log=out/'runtime.log'
with log.open('w') as f:
    proc=subprocess.run([str(ROOT/'engine/wf_game'),'-rate20','--debug-port','17924','--debug-bind','127.0.0.1',f'--menu-input={script}',f'--capture-frame=4={out/"selector.png"}'],
                         cwd=preview,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180,
                         preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
text=log.read_text(errors='replace')
assert proc.returncode==0,('engine menu failed',proc.returncode)
assert not any(x in text for x in ['ASSERTION FAILED','zforth compile error','zforth eval error','ERROR: AddressSanitizer']),text[-3000:]
import re
started=[int(n) for n in re.findall(r'^level-menu: level (\d+) starts$',text,re.M)]
assert started==([6,5,2,3,4,0,1,6] if a.installed_bundle else [5,2,3,4,0,1,5]),started
assert len(re.findall(r'^level-menu: back to the menu$',text,re.M))==(7 if a.installed_bundle else 6)
result={'status':'PASS','started_indices':started,'entries':menu['entries'],'sources':sources,
        'note':('Integrated seven-tank Android bundle exercised in the desktop engine.' if a.installed_bundle else 'Isolated desktop snapshot; active Aquarium app bundle and device left alone.')}
(out/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'.gitignore').write_text('*.log\n')
print(json.dumps(result,indent=2))
