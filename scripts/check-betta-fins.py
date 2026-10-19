#!/usr/bin/env python3
"""Capture actual hover/swim/turn/settle fin motion and verify exported runtime state."""
import json,math,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
OUT=ROOT/'docs/plans/2026-10-02-betta-poster-and-flowing-fins/engine';OUT.mkdir(parents=True,exist_ok=True)
mapping=json.loads((ROOT/'wflevels/aquarium_betta/actor-map.json').read_text());idx=mapping['indices'];pl=idx['Player'];director=idx['Director']
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs'),ASAN_OPTIONS='detect_leaks=0',WF_REST_HOST='127.0.0.1',WF_REST_PORT='18937')
with (OUT/'runtime.log').open('w') as log:
    proc=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/aquarium_betta-standalone.iff'),'-rate30',
        '--debug-port','17937','--debug-bind','127.0.0.1'],cwd=ROOT/'wflevels/aquarium_betta',env=env,stdout=log,stderr=log)
    cli=None;trace=[]
    try:
        cli=BridgeClient(port=17937,timeout=20);cli.send({'op':'pause'})
        for actor,mbs in [(pl,[1906,3009,3010,3011]),(director,list(range(660,667))+[602])]:
            for m in mbs:cli.watch(idx=actor,mailbox=m)
        def value(m,a=director):
            with cli._lock:return cli.mailbox_values.get((a,m),0)
        def step(n):
            before=value(1906,pl);cli.send({'op':'step','frames':n});end=time.monotonic()+20
            while time.monotonic()<end:
                if value(1906,pl)>=before+n*2184/65536-.0005:time.sleep(.02);return
                if proc.poll() is not None:raise RuntimeError('Engine exited')
                time.sleep(.005)
            raise RuntimeError('Step timeout')
        def shot(path):
            cli.send({'op':'screenshot','filename':str(path)})
            msg=cli.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=10)
            assert msg and msg.get('op')=='screenshot_done',msg
        cli.inject_input('joystick1_raw',0,duration_frames=-1);step(6)
        frames=OUT/'frames';frames.mkdir(exist_ok=True)
        # Twenty-four simulated seconds, sampled at 10 fps. Inputs are actual controller masks.
        actions=[('hover',0,40),('swim',8192,45),('turn',16384,40),('settle',0,35),
                 ('action',1,3),('recover',0,30),('climb',2048,25),('depth',8192|4,22)]
        frame=0
        for name,mask,samples in actions:
            cli.inject_input('joystick1_raw',mask,duration_frames=-1)
            for sample in range(samples):
                step(3)
                row={'frame':frame,'seconds':frame/10,'state':name,'position':[value(m,pl) for m in (3009,3010,3011)],
                     'drive':value(660),'turn':value(661),'phase':value(663),'pectoral_phase':value(664),'sweep':value(665),'spread':value(666)}
                assert all(math.isfinite(v) for v in row['position'])
                assert 0<=row['phase']<1 and 0<=row['pectoral_phase']<1
                assert .55<=row['spread']<=1.1 and 0<=row['drive']<=1.0001
                trace.append(row);shot(frames/f'frame-{frame:03d}.png');frame+=1
            shot(OUT/(name+'.png'))
        assert max(r['drive'] for r in trace)>.8
        assert max(abs(r['turn']) for r in trace)>.3
        assert max(r['spread'] for r in trace)-min(r['spread'] for r in trace)>.10
        assert trace[0]['phase']!=trace[-1]['phase']
    finally:
        if cli:cli.close()
        proc.terminate();proc.wait(timeout=5)
text=(OUT/'runtime.log').read_text(errors='replace')
assert proc.returncode in (0,-15) and not any(t in text for t in ['ASSERTION FAILED','zforth compile error','zforth eval error','AddressSanitizer:']),text[-3000:]
report={'status':'PASS','actors':len(idx),'groups':mapping['parts'],'triangles':mapping['betta_fins']['triangles'],
        'frames':len(trace),'simulated_seconds':len(trace)/10,'trace':trace,
        'note':'Actual GL engine, 30 Hz simulation; controller masks, no actor teleports. Fin deformation consumes cached UV weights before the shared renderer path.'}
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'.gitignore').write_text('*.log\nframes/\n')
subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','10','-i',str(OUT/'frames/frame-%03d.png'),
                '-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(OUT/'betta-motion.mp4')],check=True)
print('PASS: '+str(OUT/'betta-motion.mp4'))
