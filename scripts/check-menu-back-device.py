#!/usr/bin/env python3
"""Verify short Back: selected level -> selector -> exit, plus animated Betta and resume."""
import argparse,hashlib,json,re,subprocess,time
from pathlib import Path
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--serial',required=True);ap.add_argument('--verify-installed',action='store_true');a=ap.parse_args()
ADB='/home/will/android-sdk-local/platform-tools/adb'
OUT=ROOT/'docs/plans/2026-10-02-betta-poster-and-flowing-fins/device';OUT.mkdir(parents=True,exist_ok=True)
def adb(*words):return subprocess.check_output([ADB,'-s',a.serial,*words],timeout=60)
def key(n):
    # Android requires two codes for a timed combination. Shift is unmapped by the game.
    adb('shell','input',*(['keycombination','-t','120',str(n),'59'] if n not in (4,3) else ['keyevent',str(n)]));time.sleep(.3)
def pid(pkg):
    return subprocess.run([ADB,'-s',a.serial,'shell','pidof',pkg],capture_output=True,timeout=20).stdout.decode().strip()
def launch(pkg):adb('shell','am','start','-n',pkg+'/android.app.NativeActivity');time.sleep(4)
def shot(name):(OUT/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
report={}
if a.verify_installed:
    for flavor in ('aquarium','smb'):
        pkg='org.worldfoundry.wf_game.'+flavor
        apk=ROOT/f'android/app/build/outputs/apk/{flavor}/release/worldfoundry-{flavor}-release.apk'
        installed=adb('shell','pm','path',pkg).decode().strip().removeprefix('package:')
        actual=adb('shell','sha256sum',installed).decode().split()[0]
        assert actual==hashlib.sha256(apk.read_bytes()).hexdigest(),flavor
        report[flavor]={'apk_sha256':actual,'installed_matches_release':True}
    shot('betta-final')
    (OUT/'installed.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));raise SystemExit(0)
for flavor in ('aquarium','smb'):
    pkg='org.worldfoundry.wf_game.'+flavor
    apk=ROOT/f'android/app/build/outputs/apk/{flavor}/release/worldfoundry-{flavor}-release.apk'
    adb('install','-r',str(apk));adb('shell','am','force-stop',pkg);launch(pkg)
    initial=pid(pkg);assert initial
    # Aquarium's first short Back also dismisses the controller panel while returning.
    for _ in range(2 if flavor=='aquarium' else 0):key(20)
    key(23);time.sleep(3)
    entry_log=adb('logcat','-d','--pid='+initial,'-v','brief').decode(errors='replace')
    assert 'level-menu: level '+str(2 if flavor=='aquarium' else 0)+' starts' in entry_log,'Initial selection was not delivered: '+entry_log[-3000:]
    key(4);time.sleep(2)
    assert pid(pkg)==initial,'Back from a level finished the app'
    cat=adb('logcat','-d','--pid='+initial,'-v','brief').decode(errors='replace')
    assert 'Back in level: returning to selector' in cat and 'level-menu: back to the menu' in cat
    shot(flavor+'-returned-selector')
    order=[2,4,6,5,0,1,3] if flavor=='aquarium' else [0,1,2,3]
    cursor=2 if flavor=='aquarium' else 0
    for index in order:
        for _ in range(abs(index-cursor)):key(20 if index>cursor else 19)
        key(23);time.sleep(2)
        if flavor=='aquarium' and index==2:
            shot('betta-fins-a');time.sleep(.55);shot('betta-fins-b')
            im1=Image.open(OUT/'betta-fins-a.png').convert('RGB');im2=Image.open(OUT/'betta-fins-b.png').convert('RGB')
            w,h=im1.size;box=(int(w*.35),int(h*.30),int(w*.65),int(h*.65))
            diff=ImageChops.difference(im1.crop(box),im2.crop(box))
            changed=sum(any(rgb) for rgb in diff.getdata());assert changed>500,changed
            report['betta_animated_pixels']=changed
            key(3);time.sleep(1);launch(pkg);assert pid(pkg)==initial
            shot('betta-resumed');report['betta_home_resume']='PASS'
        shot(flavor+f'-level-{index}')
        key(4);time.sleep(2);assert pid(pkg)==initial
        cursor=index
    cat=adb('logcat','-d','--pid='+initial,'-v','brief').decode(errors='replace')
    starts=[int(n) for n in re.findall(r'level-menu: level (\d+) starts',cat)]
    assert starts[-len(order):]==order,(flavor,starts)
    assert cat.count('level-menu: back to the menu')>=len(order)+1
    assert not any(t in cat for t in ['ASSERTION FAILED','zforth compile error','zforth eval error','Fatal signal'])
    key(4);time.sleep(3)
    assert pid(pkg)!=initial,'Back on selector did not finish the activity/process'
    installed=adb('shell','pm','path',pkg).decode().strip().removeprefix('package:')
    actual=adb('shell','sha256sum',installed).decode().split()[0]
    assert actual==hashlib.sha256(apk.read_bytes()).hexdigest()
    report[flavor]={'status':'PASS','short_back_returns':order,'selector_back_exits':True,'apk_sha256':actual}
# Leave the upgraded Betta ready for normal play.
launch('org.worldfoundry.wf_game.aquarium')
for _ in range(2):key(20)
key(23);time.sleep(2)
key(4);time.sleep(2);key(23);time.sleep(2);shot('betta-final')
report.update(status='PASS',serial=a.serial,note='Actual release apps, Android Back down/up injection; no long press. All current Aquarium and SMB selections return to their selector; selector Back exits.')
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
