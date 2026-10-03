#!/usr/bin/env python3
"""Verify the installed species movement build using release logs and timed Android inputs."""
from pathlib import Path
import argparse
import subprocess,json,time,re,hashlib
root=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--serial',required=True)
ap.add_argument('--apk',type=Path,default=root/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk')
ap.add_argument('--out',type=Path,default=root/'docs/plans/2026-10-02-aquarium-movement-and-controls/device')
a=ap.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True)
adbpath='/home/will/android-sdk-local/platform-tools/adb';serial=a.serial;pkg='org.worldfoundry.wf_game.aquarium';logpath=f'/sdcard/Android/data/{pkg}/files/wf.log'
def adb(*args):return subprocess.check_output([adbpath,'-s',serial,*args],timeout=45)
def key(k,ms=120):adb('shell','input','keycombination','-t',str(ms),str(k),'59')
def offset():return int(adb('shell','stat','-c','%s',logpath).decode().strip())
apk=a.apk;actual=adb('shell','pm','path',pkg).decode().strip().removeprefix('package:');actualsha=adb('shell','sha256sum',actual).decode().split()[0];assert actualsha==hashlib.sha256(apk.read_bytes()).hexdigest()
results=[]
for index,kind in [(1,'blue_shrimp'),(2,'betta'),(3,'jellyfish'),(4,'lionfish'),(5,'plants'),(6,'arowana')]:
 adb('shell','am','force-stop',pkg);mark=offset();adb('shell','am','start','-n',pkg+'/android.app.NativeActivity');time.sleep(2.5)
 adb('shell','input','keyevent','4');time.sleep(.3)
 for _ in range(index):key(20);time.sleep(.12)
 key(23);time.sleep(2)
 pid=adb('shell','pidof',pkg).decode().strip();assert pid
 capture=adb('logcat','-d','--pid='+pid,'-v','brief').decode(errors='replace');assert f'level-menu: level {index} starts' in capture
 move=offset()
 if kind=='jellyfish':adb('shell','input','keycombination','-t','3500','22','23')
 else:key(22,3500)
 time.sleep(.6)
 text=adb('shell','tail','-c','+'+str(move+1),logpath).decode(errors='replace')
 rows=[list(map(float,row)) for row in re.findall(r'ball pos: \(([-\d.]+), ([-\d.]+), ([-\d.]+)\)',text)]
 assert len(rows)>=2,(kind,text[-1000:])
 delta=rows[-1][0]-rows[0][0];assert delta>(.015 if kind=='plants' else .04),(kind,rows)
 if kind in ['betta','lionfish','arowana']:key(21,3500);time.sleep(.5)
 if kind=='lionfish':adb('shell','input','keycombination','-t','120','20','23');time.sleep(.4)
 launchlog=adb('shell','tail','-c','+'+str(mark+1),logpath).decode(errors='replace');(out/(kind+'-runtime.log')).write_text(launchlog)
 assert not any(s in launchlog for s in ('zforth compile error','zforth eval error','ASSERTION FAILED','unknown sys'))
 (out/(kind+'.png')).write_bytes(adb('exec-out','screencap','-p'))
 results.append({'kind':kind,'menu_index':index,'position_samples':rows,'right_displacement':delta,'native_runtime_errors':False});print('PASS',kind,delta,flush=True)
(out/'checks.json').write_text(json.dumps({'status':'PASS','apk_sha256':actualsha,'serial':serial,'tests':results,'note':'Chromecast HD release, timed injected Android D-pad/OK events. Physical remote chords and repeat behavior remain manual acceptance.'},indent=2)+'\n')
print('PASS six species on Chromecast',flush=True)
