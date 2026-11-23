"""Compare real engine frames and motion with Water motion on and off."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from PIL import Image, ImageChops

root = Path('/src')
sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient

mode=sys.argv[1]
assert mode in ('on','off')
out=root/'build-docker/lighthouse-captures'
out.mkdir(parents=True,exist_ok=True)
ids=json.loads((root/'wflevels/lighthouse/actor-map.json').read_text())['indices']
env=dict(os.environ,WF_WALL_CLOCK='10:08:22@0',WF_REST_PORT='0')
args=[str(root/'build-docker/tourbillon/src/engine/wf_game'),
      '-L'+str(root/'wflevels/lighthouse-standalone.iff'),'--debug-port','17798',
      '--debug-bind','127.0.0.1','-width=1024','-height=576','--no-fps',
      '--vram-width=2048','--vram-height=1024','--vram-slot-width=1024','--vram-slot-height=512',
      '--property=LighthouseSettings.Camera drift=1']
if mode=='off': args.append('--property=LighthouseSettings.Water motion=0')

with (out/f'motion-{mode}.log').open('w') as log:
    p=subprocess.Popen(args,env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17798,timeout=60)
        keys=[(ids['Boat'],3011),(ids['Surf0'],3014),(ids['Glint0'],3009)]
        for key in keys: c.watch(*key)
        time.sleep(5)
        frames=[]
        capture_times=[]
        samples=[]
        for i in range(20):
            path=out/f'motion-{mode}-{i:02d}.png'
            c.send({'op':'screenshot','filename':str(path)})
            assert c.wait_for(lambda msg:msg.get('op')=='screenshot_done',timeout=30)
            capture_times.append(time.monotonic())
            with Image.open(path) as img: frames.append(img.convert('RGB'))
            v=dict(c.mailbox_values)
            if all(key in v for key in keys):
                samples.append((v[keys[0]],(v[keys[1]]+.5)%1-.5,v[keys[2]]))
            time.sleep(.25)
        assert p.poll() is None and samples,'engine exited or did not return samples'
        spans=[max(row[i] for row in samples)-min(row[i] for row in samples) for i in range(3)]
        pixels=sum(1 for p in ImageChops.difference(frames[0],frames[-1]).getdata() if p != (0,0,0))
        if mode=='on':
            assert spans[0]>.03 and spans[1]>.005 and spans[2]>.08,(spans,pixels)
            assert pixels>5000,(spans,pixels)
            durations=[max(20,round((b-a)*1000)) for a,b in zip(capture_times,capture_times[1:])]
            durations.append(durations[-1])
            frames[0].save(out/'water-motion.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True)
        else:
            assert all(span<.001 for span in spans),(spans,pixels)
            # Subpixel rendering can change a few isolated edge pixels even
            # with a frozen camera and actors; allow a small image difference.
            assert pixels<1000,(spans,pixels)
        print('PASS water',mode,'boat/surf/glint ranges',spans,'changed pixels',pixels,flush=True)
        c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
