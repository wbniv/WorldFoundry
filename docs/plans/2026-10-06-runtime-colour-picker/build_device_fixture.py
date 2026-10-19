"""Build an isolated authored RGB UI fixture APK; never edit shipped level assets."""
from pathlib import Path
import argparse
import importlib.util
import json
import struct
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[3]
a=argparse.ArgumentParser();a.add_argument('--base-apk',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('properties',ROOT/'scripts/build-object-properties.py');cooker=importlib.util.module_from_spec(spec);spec.loader.exec_module(cooker)
actor=struct.unpack_from('<I',(ROOT/'wflevels/aquarium_plants/settings.rprp').read_bytes(),8)[0]
catalog=cooker.catalog(ROOT/'wfsource/source/oas/actor.oad',{'title':'Colour picker fixture','fields':{'Background Color':{'id':201,'initial':str(0x58878c)}}},actor)
(out/'fixture.rprp').write_bytes(catalog);level=out/'fixture.iff';level.write_bytes(cooker.attach((ROOT/'wflevels/aquarium_plants-standalone.iff').read_bytes(),catalog))
manifest=out/'fixture.manifest';manifest.write_text('title Colour picker fixture\nprompt Test only - RGB has no gameplay consumer\nlevel '+str(level)+' | Colour picker fixture\nlevel '+str(level)+' | Second fixture entry\n')
cd=out/'fixture-cd.iff';subprocess.run([str(ROOT/'wftools/cdpack-rs/target/release/cdpack'),str(ROOT/'wfsource/source/game/shell-menu.fth'),'--manifest',str(manifest),'-o',str(cd)],check=True)
unsigned=out/'unsigned.apk';aligned=out/'aligned.apk';apk=out/'colour-picker-fixture.apk'
with zipfile.ZipFile(args.base_apk) as src,zipfile.ZipFile(unsigned,'w') as dst:
    for entry in src.infolist():
        if entry.filename.startswith('META-INF/') or entry.filename=='assets/cd.iff':continue
        dst.writestr(entry,src.read(entry.filename))
    dst.write(cd,'assets/cd.iff',compress_type=zipfile.ZIP_DEFLATED)
sdk=Path(next(line.split('=',1)[1] for line in (ROOT/'android/local.properties').read_text().splitlines() if line.startswith('sdk.dir=')))
tools=sdk/'build-tools/34.0.0';subprocess.run([str(tools/'zipalign'),'-f','-p','4',str(unsigned),str(aligned)],check=True)
subprocess.run([str(tools/'apksigner'),'sign','--ks',str(Path.home()/'.android/debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--out',str(apk),str(aligned)],check=True)
unsigned.unlink();aligned.unlink()
import hashlib
(out/'receipt.json').write_text(json.dumps({'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'base_sha256':hashlib.sha256(args.base_apk.read_bytes()).hexdigest(),'actor':actor,'field':201,'schema':'actor.oad / Background Color / SHOW_AS_COLOR','gameplay_consumer':False},indent=2)+'\n');print(apk)
