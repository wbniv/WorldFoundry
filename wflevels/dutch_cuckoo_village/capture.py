"""Capture actual desktop frames of Tulpenkade at arbitrary device-local times."""
import argparse
import os
import json
from pathlib import Path
import subprocess
from PIL import Image
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('out',type=Path)
parser.add_argument('times',nargs='+',metavar='HH:MM:SS')
parser.add_argument('--still',action='store_true')
parser.add_argument('--port',type=int,default=17971)
args=parser.parse_args()
args.out=args.out.resolve()
args.out.mkdir(parents=True,exist_ok=True)
for i,stamp in enumerate(args.times):
    path=args.out/(stamp.replace(':','-')+('-still' if args.still else '')+'.png')
    port=args.port+i
    env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
    cmd=[str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/dutch_cuckoo_village-standalone.iff'),
         '-rate20','-width=1280','-height=720','--no-fps','--debug-bind','127.0.0.1','--debug-port',str(port)]
    if args.still:
        cmd.append('--property=DutchCuckooVillageSettings.Camera motion=1')
    with path.with_suffix('.log').open('w') as log:
        proc=subprocess.Popen(cmd,cwd=ROOT/'wfsource/source/game',env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            client=BridgeClient(port=port,timeout=45)
            try:
                indices=json.loads((Path(__file__).parent/'actor-map.json').read_text())['indices']
                watches=[(indices[name],axis) for name in ('Camera','cs_wide') for axis in (3009,3010,3011)]
                for idx,axis in watches+[(indices['Player'],1906)]:
                    client.watch(idx,axis)
                def settled(_):
                    values=client.mailbox_values
                    return (values.get((indices['Player'],1906),0)>.5
                            and all(key in values for key in watches)
                            and all(abs(values[indices['Camera'],axis]-values[indices['cs_wide'],axis])<.05
                                    for axis in (3009,3010,3011)))
                if not client.wait_for(settled,timeout=40):
                    raise RuntimeError(f'Camera failed to reach the authored shot at {stamp}')
                if proc.poll() is not None:
                    raise RuntimeError(f'Engine exited; see {log.name}')
                client.send({'op':'screenshot','filename':str(path)})
                if not client.wait_for(lambda m:m.get('op')=='screenshot_done',timeout=20):
                    raise RuntimeError(f'Capture timed out; see {log.name}')
            finally:
                client.close()
        finally:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=15)
    extrema=Image.open(path).convert('RGB').getextrema()
    if max(high-low for low,high in extrema)<30:
        raise RuntimeError(f'Frame at {stamp} has no visible scene: {extrema}')
    print(path,flush=True)
