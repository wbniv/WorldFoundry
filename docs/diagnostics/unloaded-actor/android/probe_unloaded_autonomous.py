"""Check the device fixture's actual Forth on desktop before uploading it."""
import argparse
import os
from pathlib import Path
import subprocess
from validate_unloaded_device import validate

p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True)
p.add_argument('--level',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
log=args.out/'wf.log'
with log.open('w') as output:
    proc=subprocess.Popen(['stdbuf','-oL','-eL',str(args.binary.resolve()),'-L'+str(args.level.resolve()),'--windowed'],
        cwd=args.level.parent,stdout=output,stderr=subprocess.STDOUT,
        env={**os.environ,'DISPLAY':':0','WF_REST_PORT':'0'})
    try:
        proc.wait(timeout=12)
        raise AssertionError(f'engine exited early: {proc.returncode}')
    except subprocess.TimeoutExpired:pass
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
print(validate(log,minimum=12))
