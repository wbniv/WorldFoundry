"""Check the cooked clock through a live 10:59 to 11:00 transition."""
import json, os, subprocess, sys, time
from pathlib import Path

root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
idx=json.loads((root/'wflevels/corolla_gauge/actor-map.json').read_text())['indices']
out=root/'build-docker/corolla-gauge-captures';out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK='10:59:52@1',WF_REST_PORT='0')
with (out/'rollover.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/corolla_gauge-standalone.iff'),'--debug-port','17793',
        '--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',
        '--vram-width=2048','--vram-height=2048','--vram-slot-width=2048','--vram-slot-height=1024'],
        env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17793,timeout=60);key=(idx['MinutePetal'],3013);c.watch(*key)
        samples=[]
        for i in range(24):
            time.sleep(.5)
            if key in c.mailbox_values:samples.append(c.mailbox_values[key]*360)
            if i in (2,22):
                c.send({'op':'screenshot','filename':str(out/('rollover-before.png' if i==2 else 'rollover-after.png'))})
                assert c.wait_for(lambda msg:msg.get('op')=='screenshot_done',timeout=30)
        assert any(x>58 for x in samples) and any(x<1 for x in samples),samples
        assert p.poll() is None,'engine exited during rollover'
        print('PASS 10:59 to 11:00 petal rollover',round(max(samples),2),round(min(samples),2),flush=True)
        c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
