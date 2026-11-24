"""Exercise the live settings through the PC engine's launch overrides."""
import json,os,subprocess,sys,time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
ids=json.loads((root/'wflevels/mirror_haze/actor-map.json').read_text())['indices']
env=dict(os.environ,WF_WALL_CLOCK='2026-11-24T10:08:30+07:00@1',WF_REST_PORT='0')
with (root/'build-docker/mirror-haze-captures/settings.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),'-L'+str(root/'wflevels/mirror_haze-standalone.iff'),'--debug-port','17793','--debug-bind','127.0.0.1','-width=640','-height=360','--no-fps','--property=MirrorHazeSettings.Haze=0','--property=MirrorHazeSettings.Camera drift=1'],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17793,timeout=60); keys=[(ids['HazeProbe'],3009),(ids['cs_wide'],3009),(ids['cs_wide'],3011)]
        for k in keys:c.watch(*k)
        time.sleep(3);a=dict(c.mailbox_values);time.sleep(2);b=dict(c.mailbox_values)
        assert all(k in a and k in b for k in keys),(a,b)
        assert a[keys[0]]==b[keys[0]]==0,(a,b)
        assert abs(a[keys[1]])<.01 and abs(b[keys[1]])<.01,(a,b)
        assert abs(a[keys[2]]-11.5)<.01 and abs(b[keys[2]]-11.5)<.01,(a,b)
        print('PASS: haze off and still-camera settings',flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
