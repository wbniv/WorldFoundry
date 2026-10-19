#!/usr/bin/env python3
"""Freeze matched urchin APKs; change only CD assets and runtime arguments."""
import argparse
from copy import copy
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from plant_settings_catalog import configure_cd,require_catalog_runtime,reject_removed_arguments

ROOT = Path(__file__).resolve().parents[1]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--cd', type=Path, default=ROOT/'wflevels/aquarium-menu-cd.iff')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--ordinary', action='store_true', help='Preserve normal runtime arguments; omit benchmark variants/recipe')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    args = '';cd=a.cd.read_bytes();plant_catalog=None
    tools = Path('/home/will/android-sdk-local/build-tools/34.0.0')
    receipts = []
    with zipfile.ZipFile(a.base) as source:
        require_catalog_runtime(source)
        args = source.read('assets/wf_args.txt').decode() if 'assets/wf_args.txt' in source.namelist() else ''
        reject_removed_arguments(args)
        if not a.ordinary:cd,plant_catalog=configure_cd(cd,dict(seed=713,water='saltwater',age=150,speed=0))
        native = {n:sha(source.read(n)) for n in source.namelist() if n.startswith('lib/')}
        for cpu in ((False,) if a.ordinary else (False, True)):
            label = 'cpu' if cpu else 'release'
            unsigned, aligned, apk = [a.out/(label+suffix) for suffix in ('-unsigned.apk','-aligned.apk','.apk')]
            runtime_args = args + ('--frame-profile\n' if cpu else '')
            with zipfile.ZipFile(unsigned, 'w') as dst:
                for item in source.infolist():
                    if item.filename.startswith('META-INF/') or item.filename in ('assets/cd.iff','assets/wf_args.txt'):
                        continue
                    dst.writestr(copy(item), source.read(item.filename))
                dst.writestr('assets/cd.iff', cd, compress_type=zipfile.ZIP_DEFLATED)
                dst.writestr('assets/wf_args.txt', runtime_args)
            subprocess.run([str(tools/'zipalign'),'-f','-p','4',str(unsigned),str(aligned)],check=True)
            subprocess.run([str(tools/'apksigner'),'sign','--ks',str(Path.home()/'.android/debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--out',str(apk),str(aligned)],check=True)
            with zipfile.ZipFile(apk) as signed:
                assert all(sha(signed.read(n)) == h for n,h in native.items())
            unsigned.unlink()
            aligned.unlink()
            receipts.append(dict(label=label,apk=str(apk.resolve()),apk_sha256=sha(apk.read_bytes()),cd_sha256=sha(cd),plant_catalog=plant_catalog,args=runtime_args,native=native))
    (a.out/'identities.json').write_text(json.dumps(receipts,indent=2)+'\n')
    if a.ordinary:
        print(a.out/'release.apk')
        return
    recipe=dict(workflow='variant-benchmark',device='chromecast-test-01',app='aquarium',scene='planted-tank',apk=receipts[0]['apk'],restore_apk=receipts[0]['apk'],trace='plants',duration=60,warmup=15,runs=3,variants=[dict(label=r['label'],apk=r['apk'],runs=1 if r['label']=='cpu' else 3,warmup=15) for r in receipts])
    (a.out/'recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    print(a.out/'recipe.json')

if __name__ == '__main__':
    main()
