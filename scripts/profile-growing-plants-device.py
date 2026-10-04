#!/usr/bin/env python3
"""Run matched plant cases, serialize Chromecast access externally, restore the normal release."""
import argparse,hashlib,json,signal,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--variants-dir',type=Path,required=True);p.add_argument('--restore-apk',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--serial',required=True);p.add_argument('--cases',nargs='+');p.add_argument('--runs',type=int,default=3);p.add_argument('--cpu-runs',type=int,default=1);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
cases=json.loads((a.variants_dir/'identities.json').read_text());selected=[c for c in cases if not c['name'].endswith('-cpu') and (not a.cases or c['name'] in a.cases)]
ADB='/home/will/android-sdk-local/platform-tools/adb';PKG='org.worldfoundry.wf_game.aquarium'
def adb(*args):return subprocess.check_output([ADB,'-s',a.serial,*args],timeout=45)
def stop(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,stop)
try:
 for cpu,runs in [(False,a.runs),(True,a.cpu_runs)]:
  if not runs:continue
  for c in selected:
   label=c['name']+('-cpu' if cpu else '');out=a.out/label
   print('PROFILE',label,flush=True)
   cmd=[sys.executable,str(ROOT/'scripts/profile-growing-plants-trace.py'),'--apk',str(a.variants_dir/(label+'.apk')),'--out',str(out),'--serial',a.serial,'--runs',str(runs),'--warmup','30','--scenario','plants','--menu-index','5','--with-phone','--resume']
   if c['growth_speed'] is not None:cmd+=['--growth-speed',str(c['growth_speed'])]
   subprocess.run(cmd,cwd=ROOT,check=True)
   subprocess.run([sys.executable,str(ROOT/'scripts/analyse-aquarium-profile.py'),str(out)],cwd=ROOT,check=True)
finally:
 print('Restoring normal eight-tank APK',flush=True);adb('install','-r',str(a.restore_apk));installed=adb('shell','pm','path',PKG).decode().strip().removeprefix('package:');actual=adb('shell','sha256sum',installed).decode().split()[0];assert actual==hashlib.sha256(a.restore_apk.read_bytes()).hexdigest()
 adb('shell','am','force-stop',PKG);adb('shell','am','start','-n',PKG+'/android.app.NativeActivity');(a.out/'restored.json').write_text(json.dumps(dict(apk_sha256=actual,normal_menu_release_restored=True,profile_enabled=False),indent=2)+'\n')
