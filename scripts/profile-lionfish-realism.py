#!/usr/bin/env python3
"""Prepare frozen 0/3-prey APKs or summarize managed Chromecast evidence.

Device work is submitted separately with task chromecast:submit RECIPE=... .
Baseline preparation needs its own checkout and the exact archived baseline APK.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def run(args, cwd=None):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)

def prepare(a):
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    tools={k:ROOT/f'wftools/{k}-rs/target/release/{k}' for k in ('iffcomp','levcomp','textile','cdpack')}
    builds=[('optimized',ROOT,a.apk.resolve(),512)]
    if a.baseline_root and a.baseline_apk:
        builds.insert(0,('baseline',a.baseline_root.resolve(),a.baseline_apk.resolve(),256))
    restore=out/'final.apk';shutil.copyfile(a.apk,restore)
    variants=[]
    for label,checkout,apk,size in builds:
        for count in (0,3):
            tag=f'{label}-{count}';dest=out/tag/'level'
            shutil.copytree(checkout/'wflevels/aquarium_lionfish',dest,dirs_exist_ok=True)
            lev=dest/'aquarium_lionfish.lev'
            lev.write_text(lev.read_text().replace(': gf-initial 0 ;',f': gf-initial {count} ;').replace(': gf-autoeat 1 ;',': gf-autoeat 0 ;'))
            run([tools['iffcomp'],'-binary','-o=aquarium_lionfish.lev.bin','aquarium_lionfish.lev'],dest)
            run([tools['levcomp'],'aquarium_lionfish.lev.bin',ROOT/'wfsource/source/oas/objects.lc','aquarium_lionfish.lvl',ROOT/'wfsource/source/oas','--mesh-dir','.','--iff-txt','aquarium_lionfish.iff.txt','--textile-ini','aquarium_lionfish.ini'],dest)
            run([tools['textile'],'-ini=aquarium_lionfish.ini','-Tlinux','-transparent=0,0,0',f'-pagex={size}',f'-pagey={size}',f'-permpagex={size}',f'-permpagey={size}','-palx=256','-paly=8','-alignx=w','-aligny=h','-flipyout','-powerof2size'],dest)
            run([tools['iffcomp'],'-binary','-o=../aquarium_lionfish.iff','aquarium_lionfish.iff.txt'],dest)
            run([tools['iffcomp'],'-binary','-o=../aquarium_lionfish-standalone.iff','aquarium_lionfish-standalone.iff.txt'],dest)
            manifest=out/(tag+'.manifest')
            lines=['title WF Aquarium','prompt Choose a tank']
            for line in (ROOT/'wflevels/aquarium-menu.manifest').read_text().splitlines():
                if line.startswith('level '):
                    filename,title=line[6:].split(' | ')
                    path=dest.parent/'aquarium_lionfish-standalone.iff' if filename=='aquarium_lionfish-standalone.iff' else ROOT/'wflevels'/filename
                    lines.append(f'level {path} | {title}')
            manifest.write_text('\n'.join(lines)+'\n')
            cd=out/(tag+'.iff');run([tools['cdpack'],ROOT/'wfsource/source/game/shell-menu.fth','--manifest',manifest,'-o',cd])
            for cpu in (False,True):
                name=tag+('-cpu' if cpu else '');unsigned=out/(name+'-unsigned.apk');aligned=out/(name+'-aligned.apk');signed=out/(name+'.apk')
                with zipfile.ZipFile(apk) as src,zipfile.ZipFile(unsigned,'w') as dst:
                    for info in src.infolist():
                        if info.filename=='assets/wf_args.txt' or (info.filename.startswith('META-INF/') and (info.filename.endswith(('.SF','.RSA','.DSA')) or info.filename=='META-INF/MANIFEST.MF')):continue
                        dst.writestr(info,cd.read_bytes() if info.filename=='assets/cd.iff' else src.read(info.filename))
                    flags=(checkout/'android/app/src/aquarium/assets/wf_args.txt').read_text() if size==512 else ''
                    flags+='--frame-profile\n' if cpu else ''
                    if flags:dst.writestr('assets/wf_args.txt',flags)
                run([a.build_tools/'zipalign','-f','-p','4',unsigned,aligned])
                run([a.build_tools/'apksigner','sign','--ks',a.keystore,'--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',signed,aligned])
                run([a.build_tools/'apksigner','verify',signed])
                variants.append({'label':name,'apk':str(signed),'runs':1 if cpu else 3,'warmup':5 if cpu else 15})
    recipe={'workflow':'variant-benchmark','app':'aquarium','scene':'lionfish','apk':str(restore),'restore_apk':str(restore),'variants':variants,'trace':'idle','duration':a.duration}
    (out/'recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    (out/'hashes.json').write_text(json.dumps({v['label']:hashlib.sha256(Path(v['apk']).read_bytes()).hexdigest() for v in variants},indent=2)+'\n')
    print('Submit with task chromecast:submit DEVICE=all RECIPE='+str(out/'recipe.json'))

def summarize(a):
    result=[]
    for evidence in a.evidence:
        for job in sorted(evidence.glob('chromecast*/J-*')):
            for variant in sorted(job.iterdir()):
                if not variant.is_dir() or variant.name.endswith('-cpu'):continue
                runs=[json.loads(p.read_text()) for p in sorted(variant.glob('run-*/summary.json'))]
                if not runs:continue
                cpu=job/(variant.name+'-cpu')/'run-1/wf.log'
                # Logs can contain earlier launches. Use only the final complete
                # five-second profile window; never average stale scenes/processes.
                session=cpu.read_text().rsplit('=== wf_game android_main',1)[-1] if cpu.exists() else ''
                window=session.rsplit('frame-window:',1)[-1] if 'frame-window:' in session else ''
                counters={name:float(value) for name,value in re.findall(r'frame-count: ([\w-]+) frames=\d+ mean=([\d.]+)',window)}
                means={name:float(value) for name,value in re.findall(r'frame-profile: ([\w-]+) frames=\d+ mean=([\d.]+)',window)}
                pss=[]
                for path in sorted(variant.glob('run-*/meminfo.txt')):
                    found=re.search(r'TOTAL PSS:\s*(\d+)',path.read_text())
                    if found:pss.append(int(found.group(1)))
                item={'device':job.parent.name,'variant':variant.name,'job':job.name,'runs':runs,'fps_median':statistics.median(s['fps'] for s in runs),'pss_kib_runs':pss,'pss_kib_median':statistics.median(pss) if pss else None,'cpu_last_window_mean_ms':means,'counters_last_window':counters,'evidence':str(variant)}
                result.append(item)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(a.out)

p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
x=sub.add_parser('prepare');x.add_argument('--apk',type=Path,required=True);x.add_argument('--out',type=Path,required=True);x.add_argument('--baseline-root',type=Path);x.add_argument('--baseline-apk',type=Path);x.add_argument('--duration',type=int,default=30);x.add_argument('--build-tools',type=Path,default=Path.home()/'android-sdk-local/build-tools/34.0.0');x.add_argument('--keystore',type=Path,default=Path.home()/'.android/debug.keystore');x.set_defaults(func=prepare)
x=sub.add_parser('summarize');x.add_argument('evidence',type=Path,nargs='+');x.add_argument('--out',type=Path,required=True);x.set_defaults(func=summarize)
a=p.parse_args();a.func(a)
