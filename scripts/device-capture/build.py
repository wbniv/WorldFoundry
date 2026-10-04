#!/usr/bin/env python3
"""Build the fixed UI Automation helper using an SDK and a supplied ECJ compiler."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sdk',type=Path,default=Path('/home/will/android-sdk-local'))
parser.add_argument('--ecj',type=Path,required=True,help='Eclipse ECJ 3.38.0 compiler jar')
args=parser.parse_args()
java=Path(shutil.which('java') or '/usr/bin/java').resolve()
platform=args.sdk/'platforms/android-34/android.jar'
d8=args.sdk/'build-tools/34.0.0/d8'
env=dict(os.environ,JAVA_HOME=str(java.parent.parent))
with tempfile.TemporaryDirectory(prefix='wf-capture-build-') as temporary:
    base=Path(temporary);classes=base/'classes';dex=base/'dex'
    classes.mkdir();dex.mkdir()
    subprocess.run([str(java),'-jar',str(args.ecj),'-8','-bootclasspath',str(platform),
                    '-d',str(classes),str(root/'scripts/device-capture/WfCapture.java')],check=True)
    subprocess.run([str(d8),'--min-api','26','--lib',str(platform),'--output',str(dex),
                    str(classes/'WfCapture.class')],env=env,check=True)
    output=root/'config/device-coordinator/capture-helper.jar'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        entry=zipfile.ZipInfo('classes.dex',(2026,10,4,0,0,0))
        entry.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(entry,(dex/'classes.dex').read_bytes())
print(str(output)+' SHA256 '+hashlib.sha256(output.read_bytes()).hexdigest())
