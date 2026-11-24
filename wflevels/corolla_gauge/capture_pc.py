"""Capture and verify the Corolla Gauge petal angle in the running PC engine."""
import datetime,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
stamp,filename=sys.argv[1:3];dt=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'))
ids=json.loads((root/'wflevels/corolla_gauge/actor-map.json').read_text())['indices']
out=root/'build-docker/corolla-gauge-captures'/filename;out.parent.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with out.with_suffix('.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),'-L'+str(root/'wflevels/corolla_gauge-standalone.iff'),'--debug-port','17792','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps','--vram-width=2048','--vram-height=2048','--vram-slot-width=2048','--vram-slot-height=1024',*sys.argv[3:]],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17792,timeout=60);key=(ids['MinutePetal'],3013);pointer=(ids['GaugePointer'],3013);c.watch(*key);c.watch(*pointer)
        stamens=[(ids[f'Stamen{i}'],3009) for i in range(1,4)]
        for stamen in stamens:c.watch(*stamen)
        time.sleep(3);before=[c.mailbox_values[k] for k in stamens]
        time.sleep(3);assert p.poll() is None,'engine exited'
        after=[c.mailbox_values[k] for k in stamens]
        assert all(abs(a-b)>.001 for a,b in zip(before,after)),(before,after)
        print('PASS independent stamen motion',before,after,flush=True)
        actual=c.mailbox_values[key];expect=(dt.minute+dt.second/60)/360
        assert abs(actual-expect)<.001,(actual,expect)
        assert abs(c.mailbox_values[pointer]-actual)<.001,(c.mailbox_values[pointer],actual)
        c.send({'op':'screenshot','filename':str(out)});assert c.wait_for(lambda msg:msg.get('op')=='screenshot_done',timeout=30)
        print('PASS',stamp,'petal',actual*360,'degrees',flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
