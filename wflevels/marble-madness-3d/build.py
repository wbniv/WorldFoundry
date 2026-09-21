#!/usr/bin/env python3
"""Rebuild this standalone bundle; optionally borrow a checkout's built tools."""
import argparse
import subprocess
from pathlib import Path
import generate

def main():
    p=argparse.ArgumentParser();p.add_argument('--tools-root',type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[2];tools=a.tools_root or root;d=generate.HERE;n=generate.NAME
    binaries={name:tools/'wftools'/f'{name}-rs'/'target/release'/name for name in ('iffcomp','levcomp','textile')}
    for path in binaries.values():
        if not path.is_file():p.error(f'Missing tool {path}; run task tools-build or pass --tools-root')
    generate.generate()
    def run(tool,*args):subprocess.run([str(binaries[tool]),*map(str,args)],cwd=d,check=True)
    run('iffcomp','-binary',f'-o={n}.lev.bin',f'{n}.lev')
    run('levcomp',f'{n}.lev.bin',root/'wfsource/source/oas/objects.lc',f'{n}.lvl',root/'wfsource/source/oas','--mesh-dir','.','--iff-txt',f'{n}.iff.txt','--textile-ini',f'{n}.ini')
    run('textile',f'-ini={n}.ini','-Tlinux','-transparent=0,0,0','-pagex=256','-pagey=256','-permpagex=256','-permpagey=256','-palx=256','-paly=8','-alignx=w','-aligny=h','-flipyout','-powerof2size')
    run('iffcomp','-binary',f'-o={n}.iff',f'{n}.iff.txt')
    run('iffcomp','-binary',f'-o={n}-standalone.iff',f'{n}-standalone.iff.txt')
    print('Built:',d/(n+'-standalone.iff'))
if __name__=='__main__':main()
