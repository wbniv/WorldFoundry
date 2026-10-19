#!/usr/bin/env python3
"""Snapshot all six tanks into an isolated desktop preview, leaving the app bundle alone."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'preview'
OUT.mkdir(exist_ok=True)
LEVELS=[('aquarium','Original Aquarium'),('aquarium_blue_shrimp','Blue Shrimp'),
        ('aquarium_betta','Calm Betta'),('aquarium_jellyfish','Jellyfish'),('aquarium_lionfish','Lionfish'),('aquarium_plants','Planted Tank')]
entries=[]
for level,title in LEVELS:
    src=ROOT/'wflevels'/(level+'-standalone.iff')
    for attempt in range(5):
        before=src.stat();data=src.read_bytes();after=src.stat()
        if (before.st_mtime_ns,before.st_size)==(after.st_mtime_ns,after.st_size) and data==src.read_bytes():break
        time.sleep(.1)
    else:raise RuntimeError(f'{src} is changing; retry after its build completes')
    (OUT/(level+'.iff')).write_bytes(data)
    entries.append(dict(level=level,title=title,sha256=hashlib.sha256(data).hexdigest()))
manifest=OUT/'menu.manifest'
manifest.write_text('title WF Aquarium\nprompt Choose a tank\n'+''.join(f'level {e["level"]}.iff | {e["title"]}\n' for e in entries))
subprocess.run([str(ROOT/'wftools/cdpack-rs/target/release/cdpack'),str(ROOT/'wfsource/source/game/shell-menu.fth'),
                '--manifest',str(manifest),'-o',str(OUT/'cd.iff')],check=True)
(OUT/'sources.json').write_text(json.dumps(entries,indent=2)+'\n')
print('Six-tank preview:',OUT/'cd.iff')
print('Current aquarium-cd.iff and Android assets were not changed.')
