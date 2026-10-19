#!/usr/bin/env python3
"""Build/freeze the thin JavaScript TV launcher with the installed Android SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
from urllib.parse import urlparse
import zipfile

ROOT=Path(__file__).resolve().parent
ECJ_SHA='01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948'
ECJ_URL='https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.39.0/ecj-3.39.0.jar'
def run(*args,env=None):
    subprocess.run([str(a) for a in args],check=True,env=env)
def build():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin',required=True)
    parser.add_argument('--automated-check',action='store_true')
    parser.add_argument('--visual-check',action='store_true',help='Slow six-player state recording inside the owned TV session')
    parser.add_argument('--sdk',default='/home/will/android-sdk-local')
    parser.add_argument('--compiler',default='/tmp/patchwork-ecj.jar')
    args=parser.parse_args()
    origin=args.origin.rstrip('/')
    parsed=urlparse(origin)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        parser.error('--origin must be an HTTP(S) origin without credentials, path or query')
    sdk=Path(args.sdk);tools=sdk/'build-tools/34.0.0';android=sdk/'platforms/android-34/android.jar'
    compiler=Path(args.compiler)
    if not compiler.exists():
        with urllib.request.urlopen(ECJ_URL,timeout=30) as response: compiler.write_bytes(response.read())
    if hashlib.sha256(compiler.read_bytes()).hexdigest()!=ECJ_SHA:
        raise SystemExit('Pinned Eclipse compiler checksum mismatch')
    if args.visual_check: args.automated_check=True
    folder=ROOT/'build'/('visual' if args.visual_check else 'automated' if args.automated_check else 'interactive')
    folder.mkdir(parents=True,exist_ok=True)
    classes=folder/'classes';classes.mkdir(exist_ok=True)
    assets=folder/'assets';assets.mkdir(exist_ok=True)
    config={'origin':origin,'automatedCheck':args.automated_check,'visualCheck':args.visual_check}
    (assets/'connection.json').write_text(json.dumps(config))
    run('java','-jar',compiler,'-1.8','-proc:none','-bootclasspath',android,'-d',classes,*ROOT.glob('src/**/*.java'))
    dex=folder/'dex';dex.mkdir(exist_ok=True)
    run(tools/'d8','--min-api','26','--lib',android,'--output',dex,*classes.glob('**/*.class'))
    unsigned=folder/'unsigned.apk'
    run(tools/'aapt','package','-f','-M',ROOT/'AndroidManifest.xml','-S',ROOT/'res','-I',android,'-A',assets,'-F',unsigned)
    with zipfile.ZipFile(unsigned,'a') as apk: apk.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_STORED)
    aligned=folder/'aligned.apk';run(tools/'zipalign','-f','4',unsigned,aligned)
    key=ROOT/'build'/'development-signing.p12'
    if not key.exists():
        # Public Android development credentials; never use this key for release.
        run('keytool','-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','androiddebugkey','-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=Quilt Night Development')
    signed=folder/'signed.apk'
    run(tools/'apksigner','sign','--ks',key,'--ks-pass','pass:android','--out',signed,aligned)
    run(tools/'apksigner','verify','--verbose',signed)
    digest=hashlib.sha256(signed.read_bytes()).hexdigest()
    frozen=folder/f'quilt-night-{digest[:16]}.apk';shutil.copyfile(signed,frozen)
    receipt={**config,'apk':str(frozen),'sha256':digest,'package':'org.worldfoundry.wf_game.patchwork','activity':'org.worldfoundry.wf_game.patchwork.TvActivity','compilerSha256':ECJ_SHA,'nativeCode':False}
    (folder/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':build()
