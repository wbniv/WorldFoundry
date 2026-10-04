"""Local APK preparation for species benchmarks; no device access."""
import argparse
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from .client import Client
from .legacy import device_id, ROOT


def species(name):
    ap=argparse.ArgumentParser(description='Prepare species variants locally, then submit one coordinated benchmark')
    ap.add_argument('--serial',required=True);args=ap.parse_args()
    sdk=Path.home()/'android-sdk-local/build-tools/34.0.0'
    normal=ROOT/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk'
    work=Path(tempfile.mkdtemp(prefix=name+'-coordinated-variants-'))
    frozen=work/'restore.apk';shutil.copyfile(normal,frozen)
    if name=='betta':
        levels={'baseline':Path('/tmp/betta-fins-baseline/baseline.iff'),'static':Path('/tmp/betta-fins-profiles/static/aquarium_betta-standalone.iff'),'animated':ROOT/'wflevels/aquarium_betta-standalone.iff'}
        out=ROOT/'docs/plans/2026-10-02-betta-poster-and-flowing-fins/profiles/chromecast'
    else:
        levels={'baseline':Path('/tmp/lionfish-goldfish-baseline/baseline.iff'),**{f'active-{n}':Path(f'/tmp/lionfish-goldfish-profiles/active-{n}/aquarium_lionfish-standalone.iff') for n in (0,1,3)}}
        out=ROOT/'docs/plans/2026-10-02-lionfish-goldfish-feeding/profiles/chromecast'
    entries=[line.removeprefix('level ').split(' | ') for line in (ROOT/'wflevels/aquarium-menu.manifest').read_text().splitlines() if line.startswith('level ')]
    variants=[]
    for label,level in levels.items():
        if not level.is_file():raise ValueError('Prepare missing variant first: '+str(level))
        manifest=work/(label+'.manifest')
        manifest.write_text('title WF Aquarium\nprompt Choose a tank\n'+''.join(f'level {level if filename=="aquarium_"+name+"-standalone.iff" else ROOT/"wflevels"/filename} | {title}\n' for filename,title in entries))
        cd=work/(label+'.iff')
        subprocess.run([str(ROOT/'wftools/cdpack-rs/target/release/cdpack'),str(ROOT/'wfsource/source/game/shell-menu.fth'),'--manifest',str(manifest),'-o',str(cd)],check=True)
        for cpu in (False,True):
            tag=label+('-cpu' if cpu else '')
            unsigned=work/(tag+'-unsigned.apk');aligned=work/(tag+'-aligned.apk');target=work/(tag+'.apk')
            with zipfile.ZipFile(frozen) as src,zipfile.ZipFile(unsigned,'w') as dst:
                for info in src.infolist():
                    if info.filename=='assets/wf_args.txt' or (info.filename.startswith('META-INF/') and (info.filename.endswith(('.SF','.RSA','.DSA')) or info.filename=='META-INF/MANIFEST.MF')):continue
                    dst.writestr(info,cd.read_bytes() if info.filename=='assets/cd.iff' else src.read(info.filename))
                if cpu:dst.writestr('assets/wf_args.txt','--frame-profile\n')
            subprocess.run([str(sdk/'zipalign'),'-f','-p','4',str(unsigned),str(aligned)],check=True)
            subprocess.run([str(sdk/'apksigner'),'sign','--ks',str(Path.home()/'.android/debug.keystore'),'--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',str(target),str(aligned)],check=True)
            subprocess.run([str(sdk/'apksigner'),'verify',str(target)],check=True)
            variants.append({'label':tag,'apk':str(target),'runs':1 if cpu else 3,'warmup':12 if cpu else 30})
    c=Client();job=c.submit({'workflow':'variant-benchmark','device':device_id(c,args.serial),'app':'aquarium','scene':name,'apk':str(frozen),'restore_apk':str(frozen),'variants':variants,'trace':'idle','duration':12})
    result=c.watch(job['id']);c.evidence(job['id'],out)
    if result==0:
        subprocess.run([__import__('sys').executable,str(ROOT/'scripts/analyse-aquarium-profile.py'),*[str(out/v['label']) for v in variants]],check=True)
    return result
