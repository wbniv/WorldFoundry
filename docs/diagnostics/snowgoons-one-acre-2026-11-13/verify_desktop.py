"""Drive the real Snowgoons CharacterVirtual through the acre using held input.

Run inside the Linux test container under Xvfb. Writes samples/screenshots beside
this script; --binary chooses the frozen desktop acceptance build.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/src')
sys.path.insert(0, str(ROOT/'tests'))
from debug_bridge_client import BridgeClient

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', default='/build/snowgoons-acceptance/wf_game')
args = parser.parse_args()
out = Path(__file__).resolve().parent
rows = []
log = (out/'walk.log').open('w')
p = subprocess.Popen([args.binary, '-L/src/wflevels/snowgoons-standalone.iff', '-rate20',
                      '--debug-port','17914','--debug-bind','127.0.0.1', '-width=1280','-height=720'],
                     cwd=ROOT/'wfsource/source/game', stdout=log, stderr=subprocess.STDOUT)
c = None
try:
    c = BridgeClient(port=17914, timeout=90)
    c.send({'op':'pause'})
    for mb in [3009,3010,3011,3014,1906]: c.watch(33,mb)
    deadline=time.monotonic()+10
    while (33,1906) not in c.mailbox_values:
        assert time.monotonic()<deadline, 'no clock broadcast'
        time.sleep(.02)

    def value(mb):
        with c._lock: return c.mailbox_values.get((33,mb),0)

    def step(n):
        start=value(1906)
        c.send({'op':'step','frames':n})
        deadline=time.monotonic()+90
        while value(1906)<start+n*.05-.002:
            assert p.poll() is None, 'engine exited'
            assert time.monotonic()<deadline, ('step timeout',start,value(1906),n)
            time.sleep(.005)
        time.sleep(.02)

    def sample(label):
        row=dict(segment=label, time=value(1906), x=value(3009),y=value(3010),z=value(3011))
        rows.append(row)
        (out/'walk-positions.json').write_text(json.dumps(rows,indent=2)+'\n')
        return row

    def shot(label):
        c.send({'op':'screenshot','filename':str(out/(label+'.png'))})
        reply=c.wait_for(lambda m:m.get('op') in ['screenshot_done','error'],timeout=15)
        assert reply and reply.get('op')=='screenshot_done',reply

    def stop():
        c.inject_input('joystick1_raw',0,duration_frames=-1)
        step(20)

    def drive(label,yaw,seconds):
        c.set_mailbox(3014,yaw,33)
        c.inject_input('joystick1_raw',1<<11,duration_frames=-1)
        for _ in range(seconds):
            step(20)
            r=sample(label)
            assert -.68<r['z']<-.56, r
        stop()
        return sample(label+'-stopped')

    stop()
    shot('after-opening')
    spawn=sample('spawn')
    assert abs(spawn['z']+.62)<.05,spawn
    south=drive('south',.75,30)
    shot('south-wall')
    assert -46<south['y']<-45.3,south
    east=drive('east',0,25)
    shot('far-corner')
    assert 29.3<east['x']<30,east
    west=drive('west',.5,40)
    assert -30<west['x']<-29.3,west
    # A continuous path outside the house footprint, then across its rear path.
    drive('north-west-side',.25,40)
    north=sample('north-wall')
    assert 21.3<north['y']<22,north
    drive('behind-house',0,25)
    shot('behind-house')
    assert all(r['z']>-1 for r in rows)
    print('PASS: held-input south/east/west/north walls and rear-house traversal',flush=True)
finally:
    if c: c.close()
    p.terminate()
    try:p.wait(timeout=10)
    except subprocess.TimeoutExpired:p.kill();p.wait()
    log.close()
