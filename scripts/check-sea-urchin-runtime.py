#!/usr/bin/env python3
"""Read-only engine diagnostic: capture crawl, diagonal, reversal and feet poses."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--port',type=int,default=17961)
    p.add_argument('--video',action='store_true')
    a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    mapping=json.loads((ROOT/'wflevels/aquarium_plants/actor-map.json').read_text())
    idx=mapping['indices'];player=idx['Player'];director=idx['Director']
    env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs'),WF_REST_PORT=str(a.port+1000))
    with (a.out/'runtime.log').open('w') as log:
        proc=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/aquarium_plants-standalone.iff'),'-rate20','--debug-port',str(a.port),'--debug-bind','127.0.0.1','--plant-seed=713','--plant-water=saltwater','--plant-age=150','--plant-speed=0'],cwd=ROOT/'wflevels/aquarium_plants',env=env,stdout=log,stderr=subprocess.STDOUT)
        cli=None
        try:
            cli=BridgeClient(port=a.port,timeout=25);cli.send({'op':'pause'});cli.inject_input('joystick1_raw',0,duration_frames=-1)
            actors=[player]+[v for n,v in idx.items() if n.startswith(('urchin-foot-','urchin-spine-'))]
            for actor in actors:
                for mb in (3009,3010,3011,3012,3013,3014,3040,3041,3042):cli.watch(idx=actor,mailbox=mb)
            cli.watch(idx=player,mailbox=1906)
            contacts=mapping.get('urchin_contacts')
            if contacts:
                for foot in contacts['feet']:
                    for field in (0,1,4,8,10):cli.watch(idx=director,mailbox=840+16*foot['slot']+field)
            def value(actor,mb):
                with cli._lock:return cli.mailbox_values.get((actor,mb),0)
            def step(n):
                clock=value(player,1906);cli.send({'op':'step','frames':n});deadline=time.monotonic()+60
                while value(player,1906)<clock+n*(3276/65536)-.0002:
                    if proc.poll() is not None:raise RuntimeError('engine exited')
                    if time.monotonic()>deadline:raise RuntimeError('frame stepping timed out')
                    time.sleep(.01)
                time.sleep(.03)
            def shot(name):
                cli.send({'op':'screenshot','filename':str(a.out/(name+'.png'))})
                msg=cli.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=15)
                assert msg and msg.get('op')=='screenshot_done',msg
            step(20);shot('wide')
            # Native plant settings consumes platform A events, whereas the debug
            # bridge injects the gameplay mailbox. Select the close view directly
            # for visual diagnostics; this is not a test of the native A gesture.
            cli.set_mailbox(mapping['mailboxes']['camera'],1,idx=0)
            # Camera selection is handled by the game loop, outside paused
            # actor stepping. Let it select the requested view, then pause.
            cli.send({'op':'resume'});time.sleep(.3);cli.send({'op':'pause'})
            step(10);shot('close')
            trace=[]
            if a.video:(a.out/'frames').mkdir(exist_ok=True)
            frame=0
            for label,bits,n in [('idle',0,40),('right',8192,100),('diagonal',8192|2048,100),('reverse',16384|4096,100),('released',0,60)]:
                cli.inject_input('joystick1_raw',bits,duration_frames=-1)
                for k in range(n):
                    step(1)
                    trace.append(dict(frame=frame,scenario=label,time=value(player,1906),poses={name:[value(actor,mb) for mb in (3009,3010,3011,3012,3013,3014,3040,3041,3042)] for name,actor in idx.items() if actor in actors},contacts={str(foot['slot']):[value(director,840+16*foot['slot']+field) for field in (0,1,4,8,10)] for foot in contacts['feet']} if contacts else {}))
                    if a.video and frame%2==0:shot(f'frames/frame-{frame//2:04d}')
                    frame+=1
                shot(label)
            (a.out/'trace.json').write_text(json.dumps(trace,indent=2)+'\n')
            (a.out/'mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
            if a.video:subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','10','-i',str(a.out/'frames/frame-%04d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(a.out/'motion.mp4')],check=True)
        finally:
            if cli:cli.close()
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log=(a.out/'runtime.log').read_text(errors='replace')
    assert not any(x in log for x in ('zforth compile error','zforth eval error','ASSERTION FAILED')),log[-3000:]
    print(a.out/'trace.json')

if __name__=='__main__':main()
