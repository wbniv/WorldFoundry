#!/usr/bin/env python3
"""Compare isolated lionfish APK variants, then restore the verified normal release."""
import argparse,hashlib,json,os,re,shlex,shutil,statistics,subprocess,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--serial',required=True);args=ap.parse_args()
ADB='/home/will/android-sdk-local/platform-tools/adb';PKG='org.worldfoundry.wf_game.aquarium'
SDK=Path('/home/will/android-sdk-local/build-tools/34.0.0');TMP=Path('/tmp/lionfish-device-profiles');TMP.mkdir(exist_ok=True)
OUT=ROOT/'docs/plans/2026-10-02-lionfish-goldfish-feeding/profiles/chromecast';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk'
NORMAL=TMP/'verified-release.apk';shutil.copyfile(SOURCE,NORMAL)
levels=['aquarium','aquarium_blue_shrimp','aquarium_betta','aquarium_jellyfish','aquarium_lionfish','aquarium_plants']
titles=['Clownfish & Tiger Barbs','Blue Shrimp','Calm Betta','Jellyfish','Lionfish','Planted Tank']
variants={'baseline':Path('/tmp/lionfish-goldfish-baseline/baseline.iff')}
variants.update({f'active-{n}':Path(f'/tmp/lionfish-goldfish-profiles/active-{n}/aquarium_lionfish-standalone.iff') for n in [0,1,3]})

def adb(*words):return subprocess.check_output([ADB,'-s',args.serial,*words],timeout=60)
def sh(words):return adb('shell',words).decode(errors='replace')
def key(code):adb('shell','input','keyevent',str(code));time.sleep(.2)
def launch():
    adb('shell','am','force-stop',PKG);adb('shell','am','start','-n',PKG+'/android.app.NativeActivity');time.sleep(3)
    key(4)
    for _ in range(4):key(20)
    key(23);time.sleep(2)
def package(label,path):
    work=TMP/label;work.mkdir(exist_ok=True)
    manifest=work/'manifest.txt';manifest.write_text('title WF Aquarium\nprompt Choose a tank\n'+''.join(f'level {path if level=="aquarium_lionfish" else ROOT/"wflevels"/(level+"-standalone.iff")} | {title}\n' for level,title in zip(levels,titles)))
    bundle=work/'cd.iff'
    subprocess.run([str(ROOT/'wftools/cdpack-rs/target/release/cdpack'),str(ROOT/'wfsource/source/game/shell-menu.fth'),'--manifest',str(manifest),'-o',str(bundle)],check=True,stdout=subprocess.DEVNULL)
    for profile in [False,True]:
        tag='cpu' if profile else 'normal';unsigned=work/f'{tag}-unsigned.apk';aligned=work/f'{tag}-aligned.apk';target=work/f'{tag}.apk'
        with zipfile.ZipFile(NORMAL) as src,zipfile.ZipFile(unsigned,'w') as dst:
            for info in src.infolist():
                if info.filename.startswith('META-INF/') and (info.filename.endswith(('.SF','.RSA','.DSA')) or info.filename=='META-INF/MANIFEST.MF'):continue
                dst.writestr(info,bundle.read_bytes() if info.filename=='assets/cd.iff' else src.read(info.filename))
            if profile:dst.writestr('assets/wf_args.txt','--frame-profile\n')
        subprocess.run([str(SDK/'zipalign'),'-f','-p','4',str(unsigned),str(aligned)],check=True)
        subprocess.run([str(SDK/'apksigner'),'sign','--ks','/home/will/.android/debug.keystore','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',str(target),str(aligned)],check=True)
        subprocess.run([str(SDK/'apksigner'),'verify',str(target)],check=True)
    return work

def percentile(vals,p):
    vals=sorted(vals);return vals[int((len(vals)-1)*p)]
def pacing(work,run,layer):
    sh('dumpsys SurfaceFlinger --latency-clear '+shlex.quote(layer));samples=[];start=time.monotonic()
    while time.monotonic()-start<12:
        samples.append({'seconds':time.monotonic()-start,'raw':sh('dumpsys SurfaceFlinger --latency '+shlex.quote(layer))});time.sleep(.65)
    presents=set()
    for sample in samples:
        for row in sample['raw'].splitlines()[1:]:
            cells=row.split()
            if len(cells)==3 and all(v.isdigit() for v in cells):
                n=int(cells[1])
                if 0<n<9223372036854775807:presents.add(n)
    ordered=sorted(presents);assert len(ordered)>100,(len(ordered),samples[-1])
    # Android's --latency-clear preserves previous slots on some builds. Bound the window.
    elapsed=time.monotonic()-start;ordered=[n for n in ordered if n>=ordered[-1]-elapsed*1e9]
    intervals=[(b-a)/1e6 for a,b in zip(ordered,ordered[1:])]
    result={'frames':len(intervals),'FPS':1000/statistics.mean(intervals),'p50_ms':percentile(intervals,.5),'p95_ms':percentile(intervals,.95),'p99_ms':percentile(intervals,.99)}
    (work/f'run-{run}-samples.json').write_text(json.dumps(samples));(work/f'run-{run}-presents.json').write_text(json.dumps(ordered));return result

report={}
try:
    for label,path in variants.items():
        apkdir=package(label,path);work=OUT/label;work.mkdir(exist_ok=True)
        print('Profiling '+label+': 30 s warmup, then three 12 s presented-frame runs',flush=True)
        adb('install','-r',str(apkdir/'normal.apk'));launch();time.sleep(30)
        layers=sh('dumpsys SurfaceFlinger --list').splitlines();layer=[s for s in layers if PKG in s and ('SurfaceView' in s or s.startswith(PKG+'/'))][-1]
        runs=[]
        for run in range(1,4):
            result=pacing(work,run,layer);runs.append(result);print(label,run,json.dumps(result),flush=True)
        memory=sh('dumpsys meminfo '+PKG);(work/'meminfo.txt').write_text(memory)
        (work/'steady.png').write_bytes(adb('exec-out','screencap','-p'))
        # Separate opt-in CPU build; never use this run for presented-frame comparison.
        adb('install','-r',str(apkdir/'cpu.apk'));launch();time.sleep(12)
        log=adb('shell','cat',f'/sdcard/Android/data/{PKG}/files/wf.log').decode(errors='replace').rsplit('=== wf_game android_main',1)[-1]
        (work/'cpu.log').write_text(log)
        assert not any(t in log for t in ['ASSERTION FAILED','zforth compile error','zforth eval error','Fatal signal']),log[-2000:]
        cpu={};counts={}
        for prefix,target in [('frame-profile',cpu),('frame-count',counts)]:
            rows={}
            for name,n,mean in re.findall(prefix+r': ([\w-]+) frames=(\d+) mean=([\d.]+)',log):rows.setdefault(name,[]).append((int(n),float(mean)))
            for name,values in rows.items():
                values=values[-2:];target[name]=sum(n*v for n,v in values)/sum(n for n,v in values)
        assert cpu,'No CPU profile windows'
        pss=re.search(r'TOTAL PSS:\s*(\d+)',memory) or re.search(r'^\s*TOTAL\s+(\d+)',memory,re.M)
        report[label]={'runs':runs,'median':{k:statistics.median(r[k] for r in runs) for k in runs[0]},'CPU_ms':cpu,'counts':counts,
            'PSS_MiB':int(pss.group(1))/1024 if pss else None,'actors':34 if label=='baseline' else 41,
            'level_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'apk_sha256':hashlib.sha256((apkdir/'normal.apk').read_bytes()).hexdigest(),
            'note':'Same release native libraries and six-tank selector. 30 s warmup once per variant; three consecutive 12 s runs, no opt-in profiling. Separate 12 s CPU probe uses final two complete windows. Initial population fixed at 0/1/3, auto-capture disabled only in isolated profile variants; natural pursuit remains active.'}
        (work/'summary.json').write_text(json.dumps(report[label],indent=2)+'\n')
        (OUT/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
finally:
    print('Restoring verified normal release',flush=True)
    adb('install','-r',str(NORMAL));launch()
    installed=adb('shell','pm','path',PKG).decode().strip().removeprefix('package:')
    actual=adb('shell','sha256sum',installed).decode().split()[0]
    assert actual==hashlib.sha256(NORMAL.read_bytes()).hexdigest()
    (OUT/'restored.json').write_text(json.dumps({'apk_sha256':actual,'normal_release_restored':True,'profiling':False,'serial':args.serial},indent=2)+'\n')
(OUT/'.gitignore').write_text('**/*.log\n')
print(json.dumps(report,indent=2),flush=True)
