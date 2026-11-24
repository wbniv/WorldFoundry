"""Capture sampled views during an accelerated 12-hour PC clock cycle.

Run in wf-linux-test with DISPLAY and /src mounted, then check the frames with
scripts/check-beam-visibility.py. Sampled rendering is not a proof of every instant.
"""
import os,subprocess,sys,time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
out=root/'build-docker/mirror-haze-captures/sweep';out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK='2026-11-24T00:00:00+07:00@360',WF_REST_PORT='0')
with (out/'runtime.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),'-L'+str(root/'wflevels/mirror_haze-standalone.iff'),'--debug-port','17795','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps'],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17795,timeout=60);time.sleep(3)
        for i in range(80):
            assert p.poll() is None,'engine exited during visibility sweep'
            path=out/('frame-%03d.png'%i)
            c.send({'op':'screenshot','filename':str(path)})
            assert c.wait_for(lambda msg:msg.get('op')=='screenshot_done',timeout=10)
            time.sleep(1.5)
        c.close();print('Captured 80 frames across the clock and camera cycles.',flush=True)
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
