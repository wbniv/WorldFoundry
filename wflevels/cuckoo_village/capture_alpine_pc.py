"""Capture the cooked Alpine Cuckoo Village at a fixed local time."""
import os,subprocess,sys,time
from pathlib import Path
root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient
stamp,name=sys.argv[1:3];out=root/'build-docker/alpine-captures';out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with (out/(name+'.log')).open('w') as log:
    p=subprocess.Popen([os.environ.get('WF_GAME','/engine/wf_game'),'-L'+str(root/'wflevels/cuckoo_village-standalone.iff'),
        '--debug-port','17801','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',
        '--vram-width=4096','--vram-height=4096','--vram-slot-width=2048','--vram-slot-height=2048',
        '--vram-perm-width=1024','--vram-perm-height=1024',*sys.argv[3:]],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17801,timeout=60);time.sleep(5);assert p.poll() is None
        c.send({'op':'screenshot','filename':str(out/(name+'.png'))});assert c.wait_for(lambda m:m.get('op')=='screenshot_done',timeout=30)
        print('PASS captured',stamp,name,flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
