#!/usr/bin/env python3
"""Continuous presented-frame capture for a fixed aquarium trace, with raw receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--serial', default='')
ap.add_argument('--apk', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--runs', type=int, default=3)
ap.add_argument('--resume', action='store_true')
ap.add_argument('--warmup', type=float, default=30)
ap.add_argument('--scenario', choices=['all','swarm'], default='all')
args = ap.parse_args()
ADB = os.environ.get('ADB', str(Path.home()/'android-sdk-local/platform-tools/adb'))
A = [ADB] + (['-s', args.serial] if args.serial else [])
PKG = 'org.worldfoundry.wf_game.aquarium'
OUT = Path(args.out); OUT.mkdir(parents=True, exist_ok=True)

def adb(*words, binary=False):
    p = subprocess.run(A+list(words), capture_output=True, timeout=20, check=True)
    return p.stdout if binary else p.stdout.decode(errors='replace')

def sh(command):
    return adb('shell', command)

def require_foreground():
    activity=sh('dumpsys activity activities')
    resumed=[line for line in activity.splitlines() if 'topResumedActivity=' in line or 'mResumedActivity:' in line]
    if not any(PKG+'/' in line for line in resumed):
        raise RuntimeError('Aquarium left the foreground; exclude this interrupted run: '+repr(resumed))

def pct(values, p):
    s=sorted(values)
    return s[min(len(s)-1, int((len(s)-1)*p))] if s else None

receipt = {'apk':str(Path(args.apk).resolve()), 'apk_sha256':hashlib.sha256(Path(args.apk).read_bytes()).hexdigest(),
           'protocol':f'{args.warmup} s warmup; '+('60 s fixed trace (five 12 s segments)' if args.scenario=='all' else '12 s swarm-only diagnostic')+f'; {args.runs} run(s); SurfaceFlinger sampled every 0.75 s',
           'serial':args.serial, 'device':sh('getprop ro.product.model; getprop ro.build.version.release; wm size'),
           'revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2))
print(adb('install','-r',args.apk).strip(), flush=True)
results=[]
for run in range(1,args.runs+1):
    work=OUT/f'run-{run}'; work.mkdir(exist_ok=True)
    if args.resume and (work/'summary.json').exists():
        results.append(json.loads((work/'summary.json').read_text())); continue
    adb('logcat','-c')
    sh('input keyevent KEYCODE_WAKEUP')
    sh(f'am force-stop {PKG}')
    sh(f'am start -n {PKG}/android.app.NativeActivity')
    time.sleep(9)
    sh('input keyevent KEYCODE_BACK')  # hides the controller panel on its first opening
    require_foreground()
    (work/'launch.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
    print(f'run {run}: warming {args.warmup}s',flush=True)
    time.sleep(args.warmup)
    require_foreground()
    layers=sh('dumpsys SurfaceFlinger --list').splitlines()
    candidates=[s for s in layers if PKG in s and ('SurfaceView' in s or s.startswith(PKG+'/'))]
    if not candidates: raise RuntimeError('No aquarium SurfaceView layer: '+repr(layers))
    layer=candidates[-1]
    # Layer names are generated locally; shell-quote to keep SurfaceFlinger arguments literal.
    import shlex
    sh('dumpsys SurfaceFlinger --latency-clear '+shlex.quote(layer))
    stop=threading.Event(); samples=[]
    def collect():
        while not stop.is_set():
            started=time.monotonic()
            try: raw=sh('dumpsys SurfaceFlinger --latency '+shlex.quote(layer))
            except Exception as e: raw='ERROR '+str(e)
            samples.append({'host_seconds':started-t0,'raw':raw})
            stop.wait(max(0, .75-(time.monotonic()-started)))
    t0=time.monotonic(); thread=threading.Thread(target=collect); thread.start()
    segments=[]
    trace=[('swarm',None),('school-right','KEYCODE_DPAD_RIGHT'),('dart','KEYCODE_DPAD_CENTER'),
           ('turn-left','KEYCODE_DPAD_LEFT'),('close-up-right','KEYCODE_DPAD_RIGHT')]
    if args.scenario=='swarm': trace=trace[:1]
    for name,key in trace:
        start=time.monotonic()-t0
        deadline=time.monotonic()+12
        if key == 'KEYCODE_DPAD_CENTER': sh('input keyevent --longpress '+key)
        while time.monotonic()<deadline:
            if key and key != 'KEYCODE_DPAD_CENTER': sh('input keyevent --longpress '+key)
            else: time.sleep(min(.25,max(0,deadline-time.monotonic())))
        segments.append({'name':name,'start':start,'end':time.monotonic()-t0})
        require_foreground()
        (work/f'{name}.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
        print(f'run {run}: captured {name}',flush=True)
    stop.set(); thread.join()
    (work/'samples.json').write_text(json.dumps(samples))
    (work/'segments.json').write_text(json.dumps(segments,indent=2))
    (work/'meminfo.txt').write_text(sh('dumpsys meminfo '+PKG))
    (work/'thermal.txt').write_text(sh('dumpsys thermalservice'))
    pid=sh('pidof '+PKG).strip().split()[0]
    (work/'logcat.txt').write_text(adb('logcat','-d','-v','threadtime','--pid='+pid))
    engine_log=sh(f'cat /sdcard/Android/data/{PKG}/files/wf.log')
    (work/'wf.log').write_text(engine_log.rsplit('=== wf_game android_main',1)[-1])
    presents=set(); refresh=None
    for sample in samples:
        rows=sample['raw'].splitlines()
        if rows and rows[0].isdigit(): refresh=int(rows[0])/1e6
        for row in rows[1:]:
            cells=row.split()
            if len(cells)!=3 or not all(v.isdigit() for v in cells): continue
            actual=int(cells[1])
            if 0<actual<9223372036854775807: presents.add(actual)
    ordered=sorted(presents)
    intervals=[(b-a)/1e6 for a,b in zip(ordered,ordered[1:])]
    if len(intervals)<100: raise RuntimeError('Insufficient real present timestamps')
    # First poll can include previous warmup timestamps. The cleared ring plus this
    # explicit host-window trim bounds the retained present timeline to the capture duration.
    end=ordered[-1]; limit=(time.monotonic()-t0)*1e9
    ordered=[p for p in ordered if p>=end-limit]
    intervals=[(b-a)/1e6 for a,b in zip(ordered,ordered[1:])]
    report={'run':run,'layer':layer,'frames':len(intervals),'refresh_ms':refresh,
            'p50_ms':pct(intervals,.5),'p90_ms':pct(intervals,.9),'p95_ms':pct(intervals,.95),'p99_ms':pct(intervals,.99),
            'worst_ms':max(intervals),'fps':1000/statistics.mean(intervals),
            'missed_refresh_percent':100*sum(v>refresh*1.5 for v in intervals)/len(intervals)}
    (work/'presents-ns.json').write_text(json.dumps(ordered))
    (work/'summary.json').write_text(json.dumps(report,indent=2))
    results.append(report); print(json.dumps(report),flush=True)
summary={'receipt':receipt,'runs':results,'median':{k:statistics.median(r[k] for r in results) for k in results[0] if isinstance(results[0][k],(int,float))}}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary['median']),flush=True)
