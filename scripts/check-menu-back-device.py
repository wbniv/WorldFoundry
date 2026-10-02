#!/usr/bin/env python3
"""Verify short Back: selected level -> selector -> exit, plus animated Betta and resume."""
import argparse,hashlib,json,re,subprocess,time,zipfile
from pathlib import Path
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--serial',required=True);ap.add_argument('--verify-installed',action='store_true');ap.add_argument('--pairing-only',action='store_true');a=ap.parse_args()
ADB='/home/will/android-sdk-local/platform-tools/adb'
OUT=ROOT/'docs/plans/2026-10-02-betta-poster-and-flowing-fins/device/pairing-back-2026-10-03';OUT.mkdir(parents=True,exist_ok=True)
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
    with zipfile.ZipFile(apk) as bundle:
        has_phone_panel='assets/layout.json' in bundle.namelist()
    # Cold startup: dismiss a panel only when the flavor provides one.
    if has_phone_panel:
        shot(flavor+'-pairing-above-selector')
        key(4);time.sleep(2)
        assert pid(pkg)==initial,'Dismissing pairing from selector exited the app'
        overlay_log=adb('logcat','-d','--pid='+initial,'-v','brief').decode(errors='replace')
        assert 'Back: hides the phone panel' in overlay_log
        assert 'Back on selector: leaving the app' not in overlay_log
        assert 'Back in level: returning to selector' not in overlay_log
        shot(flavor+'-selector-after-dismiss')
        report[flavor+'_pairing_back_reveals_selector']='PASS'
    else:
        report[flavor+'_pairing_panel']='Not provided by this flavor'
        shot(flavor+'-selector-without-panel')
    for _ in range(2 if flavor=='aquarium' else 0):key(20)
    key(23);time.sleep(3)
    entry_log=adb('logcat','-d','--pid='+initial,'-v','brief').decode(errors='replace')
    assert 'level-menu: level '+str(2 if flavor=='aquarium' else 0)+' starts' in entry_log,'Initial selection was not delivered: '+entry_log[-3000:]
    key(4);time.sleep(2)
    assert pid(pkg)==initial,'Back from a level finished the app'
    cat=adb('logcat','-d','--pid='+initial,'-v','brief').decode(errors='replace')
    assert 'Back in level: returning to selector' in cat and 'level-menu: back to the menu' in cat
    shot(flavor+'-returned-selector')
    order=([2] if flavor=='aquarium' else [0]) if a.pairing_only else ([2,4,6,5,0,1,3] if flavor=='aquarium' else [0,1,2,3])
    cursor=2 if flavor=='aquarium' else 0
    for index in order:
        for _ in range(abs(index-cursor)):key(20 if index>cursor else 19)
        key(23);time.sleep(2)
        if flavor=='aquarium' and index==2 and not a.pairing_only:
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
    if a.pairing_only and has_phone_panel:
        # A panel can also be above an already selected level. First Back must
        # hide it without returning; only the next Back returns to the selector.
        launch(pkg);level_pid=pid(pkg);assert level_pid
        for _ in range(2 if flavor=='aquarium' else 0):key(20)
        key(23);time.sleep(3)
        key(4);time.sleep(2)
        level_log=adb('logcat','-d','--pid='+level_pid,'-v','brief').decode(errors='replace')
        assert 'Back: hides the phone panel' in level_log and 'level-menu: level '+str(2 if flavor=='aquarium' else 0)+' starts' in level_log
        assert 'Back in level: returning to selector' not in level_log and pid(pkg)==level_pid
        shot(flavor+'-level-after-panel-dismiss')
        key(4);time.sleep(2)
        level_log=adb('logcat','-d','--pid='+level_pid,'-v','brief').decode(errors='replace')
        assert 'Back in level: returning to selector' in level_log and pid(pkg)==level_pid
        key(4);time.sleep(3);assert pid(pkg)!=level_pid
        report[flavor+'_pairing_back_preserves_level']='PASS'
    installed=adb('shell','pm','path',pkg).decode().strip().removeprefix('package:')
    actual=adb('shell','sha256sum',installed).decode().split()[0]
    assert actual==hashlib.sha256(apk.read_bytes()).hexdigest()
    report[flavor]={'status':'PASS','short_back_returns':order,'selector_back_exits':True,'apk_sha256':actual}
# Leave the upgraded Betta ready for normal play.
launch('org.worldfoundry.wf_game.aquarium')
key(4);time.sleep(1)
for _ in range(2):key(20)
key(23);time.sleep(2);shot('betta-final')
report.update(status='PASS',serial=a.serial,pairing_focused=a.pairing_only,note='Actual release apps, Android Back down/up injection; no long press. Aquarium Back first hides the pairing panel and preserves the selector; SMB supplies no phone panel. With it hidden, the tested Aquarium and SMB selections return to their selector; selector Back exits.')
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
