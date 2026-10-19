from pathlib import Path
import hashlib,json,subprocess,zipfile
root=Path(__file__).resolve().parents[3];work=Path('/tmp/planted-tank-variants');sdk=Path.home()/'android-sdk-local/build-tools/34.0.0'
base=work/'normal-release.apk'
def package(name):
 manifest=work/(name+'.manifest')
 entries=[]
 for line in (root/'wflevels/aquarium-menu.manifest').read_text().splitlines():
  if line.startswith('level '):
   level,title=line[6:].split(' | ');p=work/(name+'-standalone.iff') if level=='aquarium_plants-standalone.iff' else work/level
   entries.append(f'level {p} | {title}')
 manifest.write_text('title WF Aquarium\nprompt Choose a tank\n'+'\n'.join(entries)+'\n')
 cd=work/(name+'-menu.iff');subprocess.run([str(root/'wftools/cdpack-rs/target/release/cdpack'),str(root/'wfsource/source/game/shell-menu.fth'),'--manifest',str(manifest),'-o',str(cd)],check=True,stdout=subprocess.DEVNULL)
 for cpu in (False,True):
  tag=name+('-cpu' if cpu else '');unsigned=work/(tag+'-unsigned.apk');aligned=work/(tag+'-aligned.apk');target=work/(tag+'.apk')
  with zipfile.ZipFile(base) as src,zipfile.ZipFile(unsigned,'w') as dst:
   for info in src.infolist():
    if info.filename.startswith('META-INF/') or info.filename in ('assets/cd.iff','assets/wf_args.txt'):continue
    dst.writestr(info,src.read(info.filename))
   dst.write(cd,'assets/cd.iff',compress_type=zipfile.ZIP_DEFLATED)
   if cpu:dst.writestr('assets/wf_args.txt','--frame-profile\n')
  subprocess.run([str(sdk/'zipalign'),'-f','-p','4',str(unsigned),str(aligned)],check=True)
  subprocess.run([str(sdk/'apksigner'),'sign','--ks',str(Path.home()/'.android/debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--out',str(target),str(aligned)],check=True)
  subprocess.run([str(sdk/'apksigner'),'verify',str(target)],check=True)
  print(target,hashlib.sha256(target.read_bytes()).hexdigest(),flush=True)
if __name__=='__main__':
 import sys
 for name in sys.argv[1:]:package(name)
