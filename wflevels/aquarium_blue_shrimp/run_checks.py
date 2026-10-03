#!/usr/bin/env python3
"""Run Blue Shrimp alone, on its own debug port, and capture actual engine evidence.

python3 wflevels/aquarium_blue_shrimp/run_checks.py [--out DIR] [--video]
No aquarium rebuild, app install, engine rebuild or shared bundle writes.
"""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
import constants as C

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--out', type=Path, default=ROOT/'docs/plans/2026-10-02-aquarium-levels-blue-shrimp/engine')
ap.add_argument('--port', type=int, default=17913)
ap.add_argument('--video', action='store_true')
ap.add_argument('--probe', action='store_true')
ap.add_argument('--cost', action='store_true', help='also measure this desktop build without vsync')
args = ap.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
mapping = json.loads((HERE/'actor-map.json').read_text())
idx = mapping['indices']
player, director = idx['Player'], idx['Director']
env = os.environ.copy()
env['LD_LIBRARY_PATH'] = str(ROOT/'engine/libs')+':'+env.get('LD_LIBRARY_PATH','')
log = (out/'runtime.log').open('w')
proc = subprocess.Popen([str(ROOT/'engine/wf_game'), '-L'+str(ROOT/'wflevels/aquarium_blue_shrimp-standalone.iff'),
                         '-rate20','--debug-port',str(args.port),'--debug-bind','127.0.0.1',
                         '--debug-print-actors'], cwd=HERE, env=env,
                        stdout=log,stderr=subprocess.STDOUT,
                        preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
cli = None
results = {}
try:
    cli = BridgeClient(port=args.port,timeout=20)
    cli.send({'op':'pause'})
    def inject(bits):
        cli.inject_input('joystick1_raw',bits,duration_frames=-1)
    inject(0)
    watches = [(player,m) for m in (1906,1909,3009,3010,3011)]
    watches += [(director,C.MAILBOX[n]) for n in ('clock','init','camera','speed','head','vx','vy','vz','dx','support','gait-phase')]
    watches += [(player, m) for m in (3018,3019,3020)]
    for k in range(mapping['count']):
        watches += [(idx[f'shrimp-{k:02d}-body'],m) for m in (3009,3010,3011)]
        if k < 3:
            watches += [(idx[f'shrimp-{k:02d}-legs-near'],3012)]
    for a,m in watches:
        cli.watch(idx=a,mailbox=m)
    def value(a,m):
        with cli._lock:
            return cli.mailbox_values.get((a,m),0)
    def step(n):
        t0 = value(player,1906)
        cli.send({'op':'step','frames':n})
        deadline = time.monotonic()+20
        while time.monotonic()<deadline:
            if value(player,1906)>=t0+n*.05-.0002:
                time.sleep(.025)
                return
            if proc.poll() is not None:
                raise RuntimeError('engine exited; see runtime.log')
            time.sleep(.005)
        raise RuntimeError(f'step did not advance from {t0}')
    def position():
        return [value(player,m) for m in (3009,3010,3011)]
    def teleport(pos):
        inject(0)
        for m,v in zip((3009,3010,3011),pos):
            cli.set_mailbox(m,v,idx=player)
        for n in ('vx','vy','vz','dart'):
            cli.set_mailbox(C.MAILBOX[n],0,idx=director)
    def shot(name):
        path = out/(name+'.png')
        cli.send({'op':'screenshot','filename':str(path)})
        msg = cli.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=15)
        assert msg and msg.get('op')=='screenshot_done', msg
    step(5)
    assert value(director,C.MAILBOX['init'])==1, 'Director did not initialize (check Forth errors)'
    if args.probe:
        teleport((.5,-.85,C.SAND+C.HULL_LIFT))
        step(3)
        inject(8192)
        for _ in range(12):
            step(1)
            assert 0<=value(director,C.MAILBOX['gait-phase'])<1
            print(position(),{n:value(director,C.MAILBOX[n]) for n in ('vx','dx','support','clock')},
                  'vel', [value(player,m) for m in (3018,3019,3020)],'raw',value(player,1909),
                  'gait-phase',value(director,C.MAILBOX['gait-phase']),flush=True)
        raise SystemExit(0)
    results['actor_count'] = len(idx)
    results['shrimp_count'] = mapping['count']
    print('PASS: scripts initialized; capturing wide view',flush=True)
    # Observe the whole tank at rest, with all residents animating.
    teleport((-4,-.85,C.SAND+C.HULL_LIFT))
    step(100)
    assert value(director,C.MAILBOX['camera'])==0
    shot('whole-tank')
    before = {key:value(*key) for key in watches}
    step(40)
    after = {key:value(*key) for key in watches}
    moving = []
    for k in range(1,mapping['count']):
        a=idx[f'shrimp-{k:02d}-body']
        moved = math.dist([before[a,m] for m in (3009,3010,3011)],
                          [after[a,m] for m in (3009,3010,3011)])
        if moved>.01:
            moving.append(k)
    if mapping['count']>1:
        assert moving, 'colony did not crawl/swim'
    results['residents_moving_over_2s']=moving
    assert any(abs(after[idx[f'shrimp-{k:02d}-legs-near'],3012]-
                       before[idx[f'shrimp-{k:02d}-legs-near'],3012])>.002 for k in range(min(3,mapping['count'])))
    shot('whole-tank-later')
    # Close-up settles on the player; feet remain on the substrate.
    teleport((2,-.4,C.SAND+C.HULL_LIFT))
    step(100)
    assert value(director,C.MAILBOX['camera'])==1
    shot('grazing-close-up')
    results['close_up_player_position']=position()
    print('PASS: colony animation and both camera views',flush=True)
    # Real input: movement, release, dart, vertical/depth travel and wall clamps.
    teleport((.5,-.85,C.SAND+C.HULL_LIFT))
    step(3)
    p0=position()
    inject(8192)
    step(20)
    p1=position()
    assert p1[0]-p0[0]>.6, (p0,p1)
    inject(0)
    step(30)
    results['right_move_m']=p1[0]-p0[0]
    for button,name in [(8192,'right'),(16384,'left'),(2048,'up'),(4096,'down'),(4,'away'),(2,'toward')]:
        teleport((.5,0,3.8))
        step(3)
        inject(button)
        axis,limit = {'right':(0,C.LIMIT_X),'left':(0,-C.LIMIT_X),
                      'up':(2,C.WATER-.5),'down':(2,C.SAND+C.HULL_LIFT),
                      'away':(1,C.LIMIT_Y),'toward':(1,-C.LIMIT_Y)}[name]
        # Horizontal travel is 0.70 m/s and passive descent 0.28 m/s.
        # Six simulated seconds cannot reach every wall from this spawn.
        for _ in range(24):
            step(20)
            x,y,z=position()
            assert abs(x)<=C.LIMIT_X+.08 and abs(y)<=C.LIMIT_Y+.08
            assert C.SAND+C.HULL_LIFT-.08<=z<=C.WATER-.5+.08
            assert value(player,1909)==button, 'desktop input reached the isolated run'
            if abs(position()[axis]-limit)<.08:
                break
        results['wall_'+name]=position()
        assert abs(position()[axis]-limit)<.08, (name,position(),limit)
        at_wall=position()[axis]
        opposite={'right':16384,'left':8192,'up':4096,'down':2048,'away':2,'toward':4}[name]
        inject(opposite)
        # Reversing horizontal direction includes the authored turn; descent
        # is 0.28 m/s. Allow three seconds to turn and leave the boundary.
        step(60)
        assert abs(position()[axis]-at_wall)>.5, ('cannot leave wall',name,position())
        print('PASS: '+name+' input and bounds',flush=True)
    teleport((.5,-.85,2))
    step(3)
    cli.set_mailbox(C.MAILBOX['head'],0,idx=director)
    inject(1)
    step(1)
    inject(0)
    step(4)
    assert value(director,C.MAILBOX['vx'])<-.5, 'tail flick should move backward'
    results['dart_velocity_x']=value(director,C.MAILBOX['vx'])
    shot('tail-flick')
    print('PASS: backward tail flick; recording motion',flush=True)
    if args.video:
        frames=out/'frames'
        frames.mkdir(exist_ok=True)
        teleport((2,-.4,C.SAND+C.HULL_LIFT))
        step(100)
        for k in range(140):
            if k==60:
                inject(8192)
            if k==90:
                inject(0)
            if k==110:
                inject(1)
            if k==111:
                inject(0)
            step(1)
            shot(f'frames/frame-{k:04d}')
        subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','20','-i',str(frames/'frame-%04d.png'),
                        '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'shrimp-motion.mp4')],check=True)
    results['status']='PASS'
finally:
    if cli:
        cli.close()
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log.close()
    text=(out/'runtime.log').read_text(errors='replace')
    if any(s in text for s in ('zforth compile error','zforth eval error','ASSERTION FAILED')):
        raise RuntimeError('Engine script/assertion errors; see '+str(out/'runtime.log'))
(out/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
if args.cost:
    times={}
    timing_env=env.copy()
    timing_env.update(__GL_SYNC_TO_VBLANK='0',vblank_mode='0')
    for frames in (30,130):
        started=time.monotonic()
        with (out/f'cost-{frames}.log').open('w') as timing_log:
            subprocess.run([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/aquarium_blue_shrimp-standalone.iff'),
                            f'--frame-step-smoke={frames}'],cwd=HERE,env=timing_env,
                           stdout=timing_log,stderr=subprocess.STDOUT,check=True,timeout=60)
        timing_text=(out/f'cost-{frames}.log').read_text(errors='replace')
        assert 'zforth compile error' not in timing_text and 'ASSERTION FAILED' not in timing_text
        times[frames]=time.monotonic()-started
    results['desktop_debug_ms_per_frame_estimate']=(times[130]-times[30])*10
    results['cost_note']='Two frame counts with vsync disabled; desktop debug build, not a device benchmark.'
(out/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
(out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Blue Shrimp — engine captures</title>
<style>body{background:#09151f;color:#e2edf3;font:18px/1.6 system-ui;max-width:1100px;margin:auto;padding:32px}
img,video{display:block;width:100%;height:auto;border-radius:12px;margin:16px 0 44px}a{color:#7acfff}p{color:#a4c1d0}
pre{overflow:auto;background:#112333;padding:24px;border-radius:12px;font-size:15px}</style>
<h1>Blue Shrimp · actual engine captures</h1><p>The independent second Aquarium level: 24 animated shrimp,
plants, wood, moss and rocks. These images and the clip come from the running World Foundry engine.</p>
<h2>Motion · 7 seconds</h2><p>Grazing colony, player movement and a backward tail flick. Fixed simulation steps encoded at 20 fps.</p>
<video controls loop muted playsinline poster="grazing-close-up.png" src="shrimp-motion.mp4"></video>
<h2>Whole tank</h2><img src="whole-tank.png" alt="Wide engine view of the planted blue shrimp aquarium">
<h2>Grazing close-up</h2><img src="grazing-close-up.png" alt="Actual engine close-up of the articulated blue shrimp">
<h2>Verification</h2><pre>'''+json.dumps(results,indent=2)+'''</pre>
<p><a href="../mockups.html">Earlier design mockups</a> · <a href="checks.json">Raw check results</a></p></html>''')
print(json.dumps(results,indent=2))
