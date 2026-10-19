#!/usr/bin/env python3
"""Sequential cold-launch selection checks on the connected Chromecast; no shared inputs."""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/plans/2026-10-02-aquarium-three-more-tanks/device/menu-six'
OUT.mkdir(parents=True,exist_ok=True)
ADB=os.environ.get('ADB','/home/will/android-sdk-local/platform-tools/adb')
PKG='org.worldfoundry.wf_game.aquarium'
def adb(*args,binary=False):
    r=subprocess.run([ADB,*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    return r.stdout if binary else r.stdout.decode(errors='replace').strip()
def shot(name):(OUT/(name+'.png')).write_bytes(adb('exec-out','screencap','-p',binary=True))
apk=ROOT/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk'
installed_path=adb('shell','pm','path',PKG).splitlines()[0].removeprefix('package:')
installed=adb('exec-out','cat',installed_path,binary=True)
expected=hashlib.sha256(apk.read_bytes()).hexdigest()
assert hashlib.sha256(installed).hexdigest()==expected,'Installed APK differs from current release'
rows=[]
for index,title in enumerate(['Clownfish & Tiger Barbs','Blue Shrimp','Calm Betta','Jellyfish','Lionfish','Planted Tank']):
    adb('shell','am','force-stop',PKG)
    adb('shell','am','start','-W','-n',PKG+'/android.app.NativeActivity');time.sleep(1.5)
    # Cold TV launches show the phone pairing panel; Back dismisses that panel.
    adb('shell','input','keyevent','KEYCODE_BACK');time.sleep(.4)
    assert adb('shell','pidof',PKG),'Pairing-panel dismissal unexpectedly exited the app'
    if index==0:shot('selector')
    for n in range(index):adb('shell','input','keyevent','KEYCODE_DPAD_DOWN');time.sleep(.12)
    adb('shell','input','keyevent','KEYCODE_DPAD_CENTER');time.sleep(3)
    pid=adb('shell','pidof',PKG);assert pid,('App exited',title)
    shot(f'tank-{index}')
    log=adb('exec-out','cat',f'/sdcard/Android/data/{PKG}/files/wf.log')
    # Android appends wf.log across launches; inspect only this process's run.
    log='wf_game v'+log.rsplit('wf_game v',1)[-1]
    (OUT/f'tank-{index}.log').write_text(log)
    assert not any(s in log for s in ['ASSERTION FAILED','zforth compile error','zforth eval error']),title
    rows.append(dict(index=index,title=title,pid=pid,screenshot=f'tank-{index}.png'))
    print('PASS cold selection:',index,title,flush=True)
# Leave the requested Planted Tank visible, and verify resume of that scene.
adb('shell','input','keyevent','KEYCODE_HOME');time.sleep(1)
adb('shell','am','start','-W','-n',PKG+'/android.app.NativeActivity');time.sleep(2)
assert adb('shell','pidof',PKG)
shot('planted-resumed')
report=dict(status='PASS',apk_sha256=expected,entries=rows,resume='alive and captured',
            note='Sequential ADB cold launches and OK selections; screenshots require visual inspection. Physical remote held Back is not established by this injector. Desktop selection/return verified separately.')
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'.gitignore').write_text('*.log\n')
print(json.dumps(report,indent=2))
