#!/usr/bin/env python3
"""Real-input course completion and live-window presentation regression.

Run on a private X display to avoid interrupting the desktop. Needs Pillow.
Only state-machine fault tests use mailbox mutations; the race uses input only.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from PIL import ImageGrab

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient

ROUTE=[(3.5,3.5),(3.5,12.5),(4.5,13.5),(4.5,15.5),(8.5,19.5),
       (19.5,19.5),(32.5,32.5),(35.5,32.5),(38.5,35.5),(38.5,41.5),
       (40.5,43.5),(46.5,43.5),(48.5,45.5),(48.5,54.5),(49.5,55.5)]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--port',type=int,default=7789)
    args=ap.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    with (out/'engine.log').open('w') as log:
        p=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(HERE/'marble-madness-3d-standalone.iff'),
                            '--debug-port',str(args.port),'--capture-frame=180='+str(out/'start.png')],
                            cwd=ROOT/'wfsource/source/game',stdout=log,stderr=subprocess.STDOUT)
        b=None
        try:
            b=BridgeClient(port=args.port)
            for m in (2,3,70,71,73,3009,3010,3011,3018,3019,3020):b.watch(3,m)
            def v(m):return b.mailbox_values.get((3,m),0)
            def wait(test,seconds=3):
                end=time.monotonic()+seconds
                while time.monotonic()<end:
                    if test():return
                    if p.poll() is not None:raise AssertionError('Engine exited; see engine.log')
                    time.sleep(.02)
                raise AssertionError(f'Timed out; mailboxes={b.mailbox_values}')
            def screenshot(name):
                target=out/(name+'.png')
                b.send({'op':'screenshot','filename':str(target)})
                wait(target.is_file)
            def restart():
                b.inject_input('joystick1_raw',1,8)
                wait(lambda:v(3)==1 and v(71)>58 and v(70)==0 and v(73)==0)
                time.sleep(.2);b.inject_input('joystick1_raw',0,1)
            wait(lambda:v(3)==1)
            time.sleep(.4)
            # Root pixels come from the PRESENTED X window, not the capture FBO.
            # The virtual display must contain only this test's game window.
            samples=[];post=0
            for i in range(300):
                shot=ImageGrab.grab(xdisplay=os.environ['DISPLAY']).convert('RGB')
                nonblack=sum(count for count,rgb in shot.getcolors(shot.width*shot.height) if max(rgb)>20)
                written=(out/'start.png').exists()
                samples.append({'png_written':written,'visible_pixels':nonblack})
                post+=int(written)
                if post>=12:break
                time.sleep(.08)
            assert any(not s['png_written'] for s in samples), 'No pre-capture samples'
            assert any(s['png_written'] for s in samples), 'No post-capture samples'
            assert min(s['visible_pixels'] for s in samples)>10000,samples
            (out/'presentation.json').write_text(json.dumps(samples,indent=2)+'\n')
            print(f'PASS: {len(samples)} presented frames before/after PNG; minimum visible pixels {min(s["visible_pixels"] for s in samples)}',flush=True)
            restart()
            directions=[]
            for f in (-1,0,1):
                for r in (-1,0,1):
                    if f or r:
                        dx=(f-r)/math.sqrt(2);dy=(f+r)/math.sqrt(2);length=math.hypot(dx,dy)
                        bits=(4096 if f>0 else 2048 if f<0 else 0)|(8192 if r>0 else 16384 if r<0 else 0)
                        directions.append((dx/length,dy/length,bits))
            wp=0;start=time.monotonic();lastprint=-1;captured=set()
            while time.monotonic()-start<62:
                x,y=v(3009),v(3010);tx,ty=ROUTE[wp];dist=math.hypot(tx-x,ty-y)
                if dist<.75 and wp<len(ROUTE)-1:
                    wp+=1;tx,ty=ROUTE[wp];dist=math.hypot(tx-x,ty-y)
                speed=min(4.2,dist*2.5)
                ax=(tx-x)/max(.001,dist)*speed-v(3018);ay=(ty-y)/max(.001,dist)*speed-v(3019)
                choice=max(directions,key=lambda d:d[0]*ax+d[1]*ay)
                b.inject_input('joystick1_raw',choice[2] if math.hypot(ax,ay)>.35 else 0,8)
                sec=int(time.monotonic()-start)
                if sec!=lastprint:
                    print(f't={sec} waypoint={wp} xyz={x:.2f},{y:.2f},{v(3011):.2f} race={v(3):.0f} falls={v(73):.0f} time={v(71):.1f}',flush=True);lastprint=sec
                if wp in (7,11) and wp not in captured:
                    screenshot('chute-'+str(wp));captured.add(wp)
                if v(3) in (2,3):break
                time.sleep(.04)
            b.inject_input('joystick1_raw',0,1)
            assert v(3)==2 and v(73)==0,b.mailbox_values
            time.sleep(.2);screenshot('finish')
            print(f'PASS: input-only Practice completion, zero falls, {v(71):.2f}s remaining, score {v(70):.0f}',flush=True)
            restart();print('PASS: restart after finish resets score, time and position',flush=True)
            b.set_mailbox(3011,-12,idx=3)
            wait(lambda:v(73)==1 and v(3011)>.4)
            assert abs(v(3009))<.1 and abs(v(3010))<.1
            print('PASS: forced fall increments counter and respawns at start',flush=True)
            b.set_mailbox(2,0,idx=3);wait(lambda:v(3)==3)
            origin=(v(3009),v(3010));b.inject_input('joystick1_raw',4096,30);time.sleep(.6)
            assert math.dist(origin,(v(3009),v(3010)))<.1
            screenshot('timeout');print('PASS: timeout stops directional movement',flush=True)
            restart();print('PASS: restart after timeout',flush=True)
            # Same-frame deadline expiry must not be overwritten by the goal.
            b.set_mailbox(3009,49,idx=3);b.set_mailbox(3010,55.5,idx=3)
            b.set_mailbox(3011,-4,idx=3);b.set_mailbox(2,0,idx=3)
            wait(lambda:v(3)==3);assert v(70)==0
            print('PASS: expired deadline takes precedence over goal overlap',flush=True)
        finally:
            if b:b.close()
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
    engine=(out/'engine.log').read_text(errors='replace')
    assert 'ERROR: AddressSanitizer' not in engine and 'compile error' not in engine
    print('PASS: no AddressSanitizer or script compile errors',flush=True)

if __name__=='__main__':main()
