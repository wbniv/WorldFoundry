import copy, shutil, struct, subprocess, zipfile
from pathlib import Path
root=Path('/home/will/WorldFoundry-wbniv'); work=Path('/tmp/reef-shrimp-full-build'); work.mkdir(exist_ok=True)
tools=root/'wftools'; oad=root/'wfsource/source/oas'; bt=Path('/home/will/android-sdk-local/build-tools/34.0.0')
def run(args,cwd): subprocess.run([str(x) for x in args], cwd=cwd,check=True,stdout=subprocess.DEVNULL)
levels=[]
for name in ('aquarium_thai_reef','aquarium_thai_reef_anime'):
 d=work/name; shutil.copytree(root/'wflevels'/name,d,dirs_exist_ok=True)
 run([tools/'iffcomp-rs/target/release/iffcomp','-binary','-o='+name+'.lev.bin',name+'.lev'],d)
 run([tools/'levcomp-rs/target/release/levcomp',name+'.lev.bin',oad/'objects.lc',name+'.lvl',oad,'--mesh-dir','.', '--iff-txt',name+'.iff.txt','--textile-ini',name+'.ini'],d)
 run([tools/'textile-rs/target/release/textile','-ini='+name+'.ini','-Tlinux','-transparent=0,0,0','-pagex=1024','-pagey=1024','-permpagex=1024','-permpagey=1024','-palx=256','-paly=8','-alignx=w','-aligny=h','-flipyout','-powerof2size'],d)
 run([tools/'iffcomp-rs/target/release/iffcomp','-binary','-o=../'+name+'.iff',name+'.iff.txt'],d)
 out=work/(name+'-standalone.iff'); run([tools/'iffcomp-rs/target/release/iffcomp','-binary','-o='+str(out),name+'-standalone.iff.txt'],d); levels.append(out.read_bytes())
base=Path('/tmp/reef-visual-polish-full.apk')
with zipfile.ZipFile(base) as z: cd=z.read('assets/cd.iff')
assert cd[:4]==b'GAME' and cd[8:12]==b'TOC\0'
n=struct.unpack_from('<I',cd,12)[0]//12; entries=[]
for i in range(n):
 tag,off,size=struct.unpack_from('<4sII',cd,16+i*12); entries.append((tag,cd[off:off+size+(8 if tag==b'SHEL' else 0)]))
assert len(entries)==13 and entries[-2][0]==b'MENU' and entries[-1][0]==b'UIFT'
for i,data in zip((9,10),levels):
 assert entries[i][0]==data[:4]; entries[i]=(entries[i][0],data)
result=bytearray(2048); result[:4]=b'GAME'; result[8:12]=b'TOC\0'; struct.pack_into('<I',result,12,len(entries)*12)
for i,(tag,data) in enumerate(entries):
 off=len(result); struct.pack_into('<4sII',result,16+i*12,tag,off,len(data)-(8 if tag==b'SHEL' else 0)); result.extend(data); result.extend(b'\0'*((-len(result))%2048))
struct.pack_into('<I',result,4,len(result)-8)
# Retain the original sector-zero alignment chunk, changing only the TOC entries.
end=16+12*len(entries); result[end:2048]=cd[end:2048]
unsigned=work/'unsigned.apk'; aligned=work/'aligned.apk'; final=work/'aquarium-shrimp.apk'
with zipfile.ZipFile(base) as src,zipfile.ZipFile(unsigned,'w') as dst:
 for info in src.infolist():
  if not info.filename.startswith('META-INF/'): dst.writestr(copy.copy(info),bytes(result) if info.filename=='assets/cd.iff' else src.read(info.filename))
run([bt/'zipalign','-f','-p','4',unsigned,aligned],work)
run([bt/'apksigner','sign','--ks','/home/will/.android/debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--out',final,aligned],work)
run([bt/'apksigner','verify',final],work)
print(final)
