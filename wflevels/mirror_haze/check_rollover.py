"""Check real engine hand motion across noon with a sped-up wall clock."""
import json,os,subprocess,sys,time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
ids=json.loads((root/'wflevels/mirror_haze/actor-map.json').read_text())['indices']
env=dict(os.environ,WF_WALL_CLOCK='2026-11-24T11:59:44+07:00@2',WF_REST_PORT='0')
with (root/'build-docker/mirror-haze-captures/rollover.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),'-L'+str(root/'wflevels/mirror_haze-standalone.iff'),'--debug-port','17794','--debug-bind','127.0.0.1','-width=640','-height=360','--no-fps'],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17794,timeout=60);keys=[(ids[n+'Beam'],3014) for n in ('Hour','Minute','Second')]
        for k in keys:c.watch(*k)
        values=[];end=time.monotonic()+12
        while time.monotonic()<end:
            time.sleep(.1)
            if all(k in c.mailbox_values for k in keys):values.append([c.mailbox_values[k] for k in keys])
        assert len(values)>30, len(values)
        for i,name in enumerate(('Hour','Minute','Second')):
            phases=[(-v[i])%1 for v in values]
            assert any(a>.98 and b<.02 for a,b in zip(phases,phases[1:])),(name,phases)
            steps=[(b-a+.5)%1-.5 for a,b in zip(phases,phases[1:])]
            assert all(-.005<x<.02 for x in steps),(name,min(steps),max(steps))
        print('PASS: hour, minute and second beam rotations cross noon continuously',flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
