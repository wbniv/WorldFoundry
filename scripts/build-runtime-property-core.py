#!/usr/bin/env python3
"""Build only the shared attribute validator for the engine's current platform."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--target-dir',type=Path,required=True)
    p.add_argument('--target',default='');p.add_argument('--ndk',default='');p.add_argument('--api',default='23')
    a=p.parse_args();env=os.environ.copy();env['CARGO_TARGET_DIR']=str(a.target_dir.resolve())
    # Gradle/NDK configurations can report CMAKE_SYSTEM_VERSION=1; use the
    # Android API level, bounded by Rust's supported Android minimum.
    a.api=str(max(21,int(a.api or '23')))
    if a.ndk and a.target:
        triples={'armv7-linux-androideabi':'armv7a-linux-androideabi','aarch64-linux-android':'aarch64-linux-android','x86_64-linux-android':'x86_64-linux-android','i686-linux-android':'i686-linux-android'}
        linker=Path(a.ndk)/'toolchains/llvm/prebuilt/linux-x86_64/bin'/(triples[a.target]+a.api+'-clang')
        env['CARGO_TARGET_'+a.target.upper().replace('-','_')+'_LINKER']=str(linker)
    cmd=['cargo','build','--release','--lib','--offline','--manifest-path',str(ROOT/'wftools/wf_attr_edit/Cargo.toml')]
    if a.target:cmd+=['--target',a.target]
    subprocess.run(cmd,env=env,check=True)
    src=a.target_dir/Path(a.target)/'release/libwf_attr_edit.a'
    a.out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,a.out)
if __name__=='__main__':main()
