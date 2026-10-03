#!/usr/bin/env python3
"""Capture motion in the native engine, with fixed timesteps and injected D-pad input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import re
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--kinds',nargs='+',default=['betta','lionfish','jellyfish','blue_shrimp','plants','arowana'])
ap.add_argument('--port',type=int,default=17921)
ap.add_argument('--video',action='store_true')
ap.add_argument('--quick',action='store_true',help='short final-build review; the 60-second crawl is in the full capture')
args=ap.parse_args()
for kind in args.kinds:
    level='aquarium' if kind=='clownfish' else 'aquarium_'+kind; here=ROOT/'wflevels'/level; out=args.out.resolve()/kind;out.mkdir(parents=True,exist_ok=True)
    mapping=json.loads((here/'actor-map.json').read_text()) if (here/'actor-map.json').exists() else {'indices':{name:i+1 for i,name in enumerate(re.findall(r"\{ 'OBJ'\s*\{ 'NAME' \"([^\"]+)\" \}",(here/(level+'.lev')).read_text()))}}
    idx=mapping['indices'];player=idx['Player']
    (out/'build.json').write_text(json.dumps({'standalone_sha256':hashlib.sha256((ROOT/'wflevels'/(level+'-standalone.iff')).read_bytes()).hexdigest(),'engine_sha256':hashlib.sha256((ROOT/'engine/wf_game').read_bytes()).hexdigest(),'fixed_dt':.05,'video_fps':10,'quick':args.quick},indent=2)+'\n')
    env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs')+':'+os.environ.get('LD_LIBRARY_PATH',''))
    with (out/'runtime.log').open('w') as log:
        proc=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels'/(level+'-standalone.iff')),'-rate20','-width=960','-height=540','--debug-port',str(args.port),'--debug-bind','127.0.0.1'],cwd=here,env=env,stdout=log,stderr=subprocess.STDOUT,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
        cli=None
        try:
            cli=BridgeClient(port=args.port,timeout=20);cli.send({'op':'pause'})
            cli.inject_input('joystick1_raw',0,duration_frames=-1)
            for m in (1906,1909,3009,3010,3011,3018,3019,3020):cli.watch(player,m)
            time.sleep(.2)
            def val(m):return cli.mailbox_values.get((player,m),0)
            def step(n):
                before=val(1906);cli.send({'op':'step','frames':n});deadline=time.monotonic()+30
                while val(1906)<before+n*.05-.001:
                    if proc.poll() is not None:raise RuntimeError('Engine exited: '+str(out/'runtime.log'))
                    if time.monotonic()>deadline:raise RuntimeError('Step timed out')
                    time.sleep(.005)
                time.sleep(.015)
            def shot(path):
                path=path.resolve();path.unlink(missing_ok=True)
                cli.send({'op':'screenshot','filename':str(path)})
                deadline=time.monotonic()+10
                while not path.exists():
                    if time.monotonic()>deadline:raise RuntimeError('Screenshot timed out')
                    time.sleep(.01)
            step(2)
            trace=[];frame=0
            def hold(label,bits,seconds):
                global frame
                cli.inject_input('joystick1_raw',bits,duration_frames=-1);time.sleep(.03)
                for i in range(round(seconds*20)//2):
                    step(2);trace.append({'label':label,'time':val(1906),'bits':val(1909),'position':[val(m) for m in (3009,3010,3011)],'velocity':[val(m) for m in (3018,3019,3020)]})
                    if args.video:
                        frames=out/'frames';frames.mkdir(exist_ok=True);shot(frames/f'f{frame:05d}.png');frame+=1
                shot(out/(label+'.png'))
            hold('rest',0,.2 if args.quick else 1)
            if kind=='plants':
                hold('crawl-depth',10240,2 if args.quick else 60);hold('close-view',1,.2);hold('rest-after-crawl',0,2)
            else:
                hold('cruise',8192,1 if args.quick else 2);hold('camera-facing-turn',16384,1.5 if args.quick else 2)
                hold('climb',2048,1 if args.quick else 2);hold('release',0,1 if args.quick else 2)
                hold('action',1,.5 if args.quick else 1);hold('recover',0,1 if args.quick else 2)
                if kind=='lionfish':hold('release-prey',4097,.2);hold('feeding-resident',0,2 if args.quick else 6)
            (out/'telemetry.json').write_text(json.dumps(trace,indent=2)+'\n')
            if args.video:
                subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','10','-i',str(out/'frames/f%05d.png'),'-c:v','libx264','-crf','24','-pix_fmt','yuv420p',str(out/'motion.mp4')],check=True)
            print('Captured',kind,flush=True)
        finally:
            if cli:cli.close()
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    errors=[line for line in (out/'runtime.log').read_text(errors='replace').splitlines() if any(s in line.lower() for s in ('forth error','zforth: script','assertion failed','unknown sys'))]
    if errors:raise RuntimeError(errors)
