"""Verify clock angles in the actual PC engine and save a frame."""
import datetime,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
stamp,filename=sys.argv[1:3]
dt=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'))
ids=json.loads((root/'wflevels/mirror_haze/actor-map.json').read_text())['indices']
out=root/'build-docker/mirror-haze-captures'/filename;out.parent.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with out.with_suffix('.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),'-L'+str(root/'wflevels/mirror_haze-standalone.iff'),'--debug-port','17797','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',*sys.argv[3:]],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17797,timeout=60)
        for name in ('Hour','Minute','Second'):
            for suffix in ('Beam','Mirror','Haze'):c.watch(ids[name+suffix],3014)
        time.sleep(8);assert p.poll() is None,'engine exited'
        v=dict(c.mailbox_values);h=(dt.hour%12+dt.minute/60+dt.second/3600)/12;m=(dt.minute+dt.second/60)/60;s=dt.second/60
        for name,phase in (('Hour',h),('Minute',m),('Second',s)):
            for suffix in ('Beam','Mirror','Haze'):
                value=v[(ids[name+suffix],3014)]
                assert abs((value+phase+.5)%1-.5)<.02,(name,suffix,value,phase)
        c.send({'op':'screenshot','filename':str(out)})
        assert c.wait_for(lambda msg:msg.get('op')=='screenshot_done',timeout=30)
        print('PASS',stamp,'hour',h,'minute',m,'seconds',s,flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
