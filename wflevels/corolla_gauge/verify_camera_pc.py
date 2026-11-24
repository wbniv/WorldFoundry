"""Sample the full slow camera path of the cooked standalone on PC."""
import json, os, subprocess, sys, time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
idx=json.loads((root/'wflevels/corolla_gauge/actor-map.json').read_text())['indices']
out=root/'build-docker/corolla-gauge-captures'/('camera-still' if '--still' in sys.argv else 'camera');out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK='10:45:00@0',WF_REST_PORT='0')
with (out/'engine.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/corolla_gauge-standalone.iff'),'--debug-port','17794',
        '--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',
        '--vram-width=2048','--vram-height=2048','--vram-slot-width=2048','--vram-slot-height=1024',
        *(['--property=CorollaGaugeSettings.Camera drift=1'] if '--still' in sys.argv else [])],
        env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17794,timeout=60);x=(idx['cs_wide'],3009);z=(idx['cs_wide'],3011)
        c.watch(*x);c.watch(*z);samples=[]
        for i in range(2 if '--still' in sys.argv else 15):
            time.sleep(10)
            assert p.poll() is None,'engine exited'
            samples.append((c.mailbox_values[x],c.mailbox_values[z]))
            c.send({'op':'screenshot','filename':str(out/f'camera-{i:02}.png')})
            assert c.wait_for(lambda m:m.get('op')=='screenshot_done',timeout=30)
            print(i,samples[-1],flush=True)
        if '--still' in sys.argv:
            assert all(abs(a)<.001 and abs(b-4.8)<.001 for a,b in samples),samples
            print('PASS still camera',flush=True)
        else:
            assert min(v[0] for v in samples)<-1.5 and max(v[0] for v in samples)>1.5,samples
            assert min(v[1] for v in samples)<4.55 and max(v[1] for v in samples)>5.05,samples
            print('PASS camera sampled over both cycles',flush=True)
        c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
