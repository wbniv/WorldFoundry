"""Check Moon Lantern's real engine positions and capture a fixed-time frame."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root=Path('/src');sys.path[:0]=[str(root/'tests'),str(root/'wflevels/moon_lantern')]
from debug_bridge_client import BridgeClient
import model

stamp,filename=sys.argv[1:3]
date=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'))
assert date.utcoffset() is not None
ids=json.loads((root/'wflevels/moon_lantern/actor-map.json').read_text())['indices']
out=root/'build-docker/moon-lantern-captures'/filename;out.parent.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with out.with_suffix('.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/moon_lantern-standalone.iff'),'--debug-port','17798',
        '--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',*sys.argv[3:]],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17798,timeout=60)
        keys=[(ids['HourShadow'],3014),(ids['MinuteShadow'],3014),
              (ids['Lantern'],3009),(ids['Lantern'],3010),(ids['Moon0'],3009),(ids['Moon0'],3010),
              (ids['PhaseProbe'],3009)]
        for key in keys:c.watch(*key)
        time.sleep(8);assert p.poll() is None,'engine exited'
        v=dict(c.mailbox_values);h,m=model.clock_phases(date.hour,date.minute,date.second+date.microsecond/1e6)
        day=(date.date()-datetime.date(2000,1,1)).days
        phase=model.moon_phase(day,date.hour,date.minute,date.second,date.utcoffset().total_seconds()/60)
        actual=v[(ids['PhaseProbe'],3009)]
        assert abs((actual-phase+.5)%1-.5)<.01,('lunar phase',actual,phase)
        for name,phase in (('HourShadow',h),('MinuteShadow',m)):
            assert abs((v[(ids[name],3014)]+phase+.5)%1-.5)<.01,(name,v,phase)
        for name,radius,phase in (('Lantern',3.65,m),('Moon0',2.65,h)):
            x,y=model.dial_point(radius,(phase+.5)%1)
            assert abs(v[(ids[name],3009)]-x)<.05 and abs(v[(ids[name],3010)]-y)<.05,(name,v,x,y)
        c.send({'op':'screenshot','filename':str(out)})
        assert c.wait_for(lambda msg:msg.get('op')=='screenshot_done',timeout=30)
        print('PASS',stamp,'hour',h,'minute',m,flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
