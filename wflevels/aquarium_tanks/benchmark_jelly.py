#!/usr/bin/env python3
"""Compare frozen level snapshots using one frozen desktop debug engine."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('variant')
ap.add_argument('--work',type=Path,default=Path('/tmp/aquarium-jelly-tuning'))
args=ap.parse_args()
work=args.work;work.mkdir(parents=True,exist_ok=True)
exe=work/'wf_game'
if not exe.exists():
    exe.write_bytes((ROOT/'engine/wf_game').read_bytes());exe.chmod(0o755)
level=work/(args.variant+'.iff')
level.write_bytes((ROOT/'wflevels/aquarium_jellyfish-standalone.iff').read_bytes())
engine_hash=hashlib.sha256(exe.read_bytes()).hexdigest()
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs')+':'+os.environ.get('LD_LIBRARY_PATH',''),
         __GL_SYNC_TO_VBLANK='0',vblank_mode='0',WF_REST_HOST='127.0.0.1',WF_REST_PORT='18925')
runs=[]
for k in range(3):
    elapsed={}
    for frames in ([80,320] if k%2==0 else [320,80]):
        log=work/f'{args.variant}-{k}-{frames}.log'
        started=time.perf_counter()
        with log.open('w') as f:
            subprocess.run([str(exe),'-L'+str(level),'-rate20','--debug-port','17925','--frame-profile',f'--frame-step-smoke={frames}'],
                           cwd=ROOT/'wflevels/aquarium_jellyfish',env=env,stdout=f,stderr=subprocess.STDOUT,
                           check=True,timeout=90,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
        elapsed[frames]=time.perf_counter()-started
        text=log.read_text(errors='replace')
        assert not any(s in text for s in ['zforth compile error','zforth eval error','ASSERTION FAILED']),log
    runs.append({'run':k,'seconds_80':elapsed[80],'seconds_320':elapsed[320],
                 'estimated_ms_per_frame':(elapsed[320]-elapsed[80])*1000/240})
    print(args.variant,runs[-1],flush=True)
result=dict(variant=args.variant,engine_sha256=engine_hash,level_sha256=hashlib.sha256(level.read_bytes()).hexdigest(),
            median_estimated_ms_per_frame=statistics.median(r['estimated_ms_per_frame'] for r in runs),runs=runs,
            note='Three paired 80/320-frame wall-time estimates, same frozen desktop debug engine, fixed 20 Hz simulation, vsync disabled. Not release/device or GPU frame distributions.')
(work/(args.variant+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
