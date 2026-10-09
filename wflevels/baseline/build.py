#!/usr/bin/env python3
"""Export/build/package baseline with the existing tools and frozen native code."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'build'

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(*args, **kwargs):
    OUT.mkdir(exist_ok=True)
    with (OUT/'build.log').open('a') as log:
        log.write('\nCOMMAND '+repr([str(a) for a in args])+'\n');log.flush()
        result=subprocess.run([str(a) for a in args],stdout=log,stderr=subprocess.STDOUT,**kwargs)
    if result.returncode:
        print((OUT/'build.log').read_text()[-6000:])
        raise RuntimeError('Build command failed; see '+str(OUT/'build.log'))

def export(blend):
    run('blender','--background','--python-exit-code','1','--python',HERE/'generate.py','--','--export',blend)

def build(preset,blend=None):
    from prepare_assets import prepare
    from settings_fixture import create
    prepare();create()
    if blend is None:
        blend=HERE/'baseline.blend' if preset=='default' else OUT/(preset+'.blend')
        if preset!='default':
            run('blender','--background','--python-exit-code','1','--python',HERE/'generate.py','--','--output',blend,'--preset',preset,'--overwrite')
    export(blend)
    run('bash',ROOT/'wftools/wf_blender/build_level_binary.sh','baseline',cwd=ROOT)
    spec=importlib.util.spec_from_file_location('baseline_catalog',ROOT/'scripts/build-object-properties.py')
    cooker=importlib.util.module_from_spec(spec);spec.loader.exec_module(cooker)
    for name in ['settings','settings-gallery']:
        run(ROOT/'wftools/oas2oad-rs/target/release/oas2oad','--types='+str(ROOT/'wfsource/source/oas/types3ds.s'),'--prep='+str(ROOT/'wftools/prep/prep'),'-o',HERE/(name+'.oad'),HERE/(name+'.oas'))
    name='settings-gallery' if preset=='settings-gallery' else 'settings'
    bindings=json.loads((HERE/(name+'-bindings.json')).read_text())
    ids=json.loads((HERE/'actor-map.json').read_text())['indices']
    catalogs=[cooker.catalog(HERE/(name+'.oad'),dict(bindings,owner=owner),ids[owner]) for owner in ['SampleSettings','SampleSettings2']]
    payload=b'RP01'+struct.pack('<I',2)+b''.join(c[8:] for c in catalogs)
    level=ROOT/'wflevels/baseline-standalone.iff'
    level.write_bytes(cooker.attach(level.read_bytes(),payload))
    (OUT/'settings.rprp').write_bytes(payload)
    snapshot=OUT/(preset+'-standalone.iff');shutil.copyfile(level,snapshot)
    run(ROOT/'wftools/cdpack-rs/target/release/cdpack',ROOT/'wfsource/source/game/shell.fth',snapshot,'-o',OUT/'cd.iff')
    receipt=dict(preset=preset,blend=str(blend),blendSha256=digest(blend),configSha256=digest(HERE/'baseline.json'),standalone=str(snapshot),levelSha256=digest(snapshot),cdSha256=digest(OUT/'cd.iff'),levelBuildChangesEngine=False,desktopExecutableSha256=digest(ROOT/'engine/wf_game'),toolHashes={str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'wftools/iffcomp-rs/target/release/iffcomp',ROOT/'wftools/levcomp-rs/target/release/levcomp',ROOT/'wftools/textile-rs/target/release/textile',ROOT/'wftools/oas2oad-rs/target/release/oas2oad',ROOT/'wftools/wf_attr_edit/target/release/catalog']})
    receipt['runtimeOptions']={str(p.relative_to(ROOT)):digest(p) for p in [HERE/'runtime_options_fixture.py',HERE/'runtime-options.json',HERE/(name+'.oas'),HERE/(name+'.oad'),HERE/(name+'-bindings.json'),OUT/'settings.rprp']}
    (OUT/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Built:',snapshot,'sha256',receipt['levelSha256'])
    return receipt

def package(runtime,refresh=False):
    candidates=[Path(v) for v in [os.environ.get('ANDROID_HOME'),os.environ.get('ANDROID_SDK_ROOT')] if v]
    candidates.append(Path.home()/'android-sdk-local')
    sdk=next((p for p in candidates if (p/'build-tools/34.0.0/aapt').is_file() and (p/'platforms/android-34/android.jar').is_file()),None)
    if sdk is None:raise RuntimeError('Android SDK with build-tools 34.0.0 and platform android-34 required')
    tools=sdk/'build-tools/34.0.0'
    frozen=OUT/'runtime.apk'
    if frozen.exists() and digest(frozen)!=digest(runtime):
        if not refresh:raise RuntimeError('Different native runtime: use --refresh-runtime after reviewing/testing the new engine')
        shutil.copyfile(frozen,OUT/('runtime-'+digest(frozen)+'.apk'))
        shutil.copyfile(runtime,frozen)
    if not frozen.exists():shutil.copyfile(runtime,frozen)
    apk=OUT/'apk';assets=apk/'assets';res=apk/'res/drawable'
    assets.mkdir(parents=True,exist_ok=True);res.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(OUT/'cd.iff',assets/'cd.iff')
    (assets/'wf_args.txt').write_text('--vram-width=5120\n--vram-height=2048\n--vram-slot-width=1024\n--vram-slot-height=1024\n--vram-perm-width=1024\n--vram-perm-height=1024\n')
    with zipfile.ZipFile(frozen) as z:
        java=any(name.endswith('.dex') for name in z.namelist())
        diagnostic='assets/runtime-diagnostics.json' in z.namelist()
        names=['assets/controller.html']+(['assets/runtime-diagnostics.json'] if diagnostic else [])
        for name in names:(assets/Path(name).name).write_bytes(z.read(name))
        if not diagnostic:(assets/'runtime-diagnostics.json').unlink(missing_ok=True)
    (assets/'layout.json').write_text(json.dumps(dict(app='baseline',title='World Foundry baseline',threshold=.5,stick=dict(up=2048,down=4096,right=8192,left=16384),buttons=[dict(id=n,bit=bit,label=label,x=x,y=.65,size=.8) for n,bit,label,x in [('A',1,'jump',.88),('B',2,'reset',.70),('C',4,'camera',.52)]],hint='Move with the stick. A jumps, B resets, C switches camera.')))
    for name,size in [('icon',(256,256)),('tv_banner',(640,360))]:
        image=Image.new('RGB',size,'#172028');d=ImageDraw.Draw(image)
        x,y=size[0]//2,size[1]//2
        for dx,dy,col in [(80,0,'#ef5350'),(0,-80,'#42a5f5'),(-55,55,'#66bb6a')]:
            d.line((x,y,x+dx,y+dy),fill=col,width=10);d.ellipse((x+dx-8,y+dy-8,x+dx+8,y+dy+8),fill=col)
        d.text((16,size[1]-30),'World Foundry baseline',fill='white');image.save(res/(name+'.png'))
    manifest='''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.worldfoundry.wf_game.baseline" android:versionCode="1" android:versionName="0.1">
<uses-sdk android:minSdkVersion="21" android:targetSdkVersion="34"/><uses-permission android:name="android.permission.INTERNET"/>
<uses-feature android:name="android.hardware.touchscreen" android:required="false"/><uses-feature android:name="android.software.leanback" android:required="false"/>
<application android:label="World Foundry baseline" android:icon="@drawable/icon" android:banner="@drawable/tv_banner" android:isGame="true" android:hasCode="__HAS_CODE__" android:extractNativeLibs="true">
<activity android:name="__ACTIVITY__" android:exported="true" android:screenOrientation="landscape" android:configChanges="orientation|keyboardHidden|screenSize|uiMode" android:launchMode="singleTask"><meta-data android:name="android.app.lib_name" android:value="wf_game"/>
__ALIAS__<intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/><category android:name="android.intent.category.LEANBACK_LAUNCHER"/></intent-filter></activity></application></manifest>'''
    manifest=manifest.replace('__HAS_CODE__','true' if java else 'false').replace('__ACTIVITY__','org.worldfoundry.wf_game.WorldFoundryActivity' if java else 'android.app.NativeActivity')
    if java:manifest=manifest.replace('__ALIAS__','</activity><activity-alias android:name="android.app.NativeActivity" android:targetActivity="org.worldfoundry.wf_game.WorldFoundryActivity" android:exported="true"><meta-data android:name="android.app.lib_name" android:value="wf_game"/>').replace('</intent-filter></activity>','</intent-filter></activity-alias>')
    else:manifest=manifest.replace('__ALIAS__','')
    (apk/'AndroidManifest.xml').write_text(manifest)
    run(tools/'aapt','package','-f','-M',apk/'AndroidManifest.xml','-S',apk/'res','-I',sdk/'platforms/android-34/android.jar','-A',assets,'-F',OUT/'unsigned.apk')
    hashes={}
    with zipfile.ZipFile(frozen) as z,zipfile.ZipFile(OUT/'unsigned.apk','a') as output:
        for name in z.namelist():
            if (name.startswith('lib/') and name.endswith('.so')) or (name.startswith('classes') and name.endswith('.dex')):
                data=z.read(name);hashes[name]=hashlib.sha256(data).hexdigest();output.writestr(name,data,compress_type=zipfile.ZIP_STORED)
    assert any('armeabi-v7a' in n for n in hashes)
    key=OUT/'development-signing.p12'
    if not key.exists():run('keytool','-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','androiddebugkey','-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=World Foundry Baseline Development')
    run(tools/'zipalign','-f','4',OUT/'unsigned.apk',OUT/'aligned.apk')
    run(tools/'apksigner','sign','--ks',key,'--ks-pass','pass:android','--out',OUT/'signed.apk',OUT/'aligned.apk')
    run(tools/'apksigner','verify',OUT/'signed.apk')
    sha=digest(OUT/'signed.apk');result=OUT/('baseline-'+sha[:16]+'.apk');shutil.copyfile(OUT/'signed.apk',result)
    with zipfile.ZipFile(result) as z:
        assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
    receipt=json.loads((OUT/'build-receipt.json').read_text())
    receipt.update(apk=str(result),apkSha256=sha,package='org.worldfoundry.wf_game.baseline',runtimeApkSha256=digest(frozen),runtimeFiles=hashes,diagnostic=diagnostic,javaTextHost=java)
    (OUT/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Frozen APK:',result)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--preset',choices=['default','diagnostics','settings-gallery'],default='default');ap.add_argument('--blend',type=Path);ap.add_argument('--export-only',action='store_true');ap.add_argument('--package-only',action='store_true');ap.add_argument('--runtime',type=Path);ap.add_argument('--refresh-runtime',action='store_true')
    args=ap.parse_args()
    if args.export_only:export(args.blend or HERE/'baseline.blend')
    elif not args.package_only:build(args.preset,args.blend)
    if args.runtime:package(args.runtime,args.refresh_runtime)
