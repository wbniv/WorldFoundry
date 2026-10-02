#!/usr/bin/env python3
"""Exercise the actual standalone lionfish level without touching an app/menu/device."""
import json, math, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
OUT=Path(os.environ.get('OUT',ROOT/'docs/plans/2026-10-02-lionfish-goldfish-feeding/engine'))
OUT.mkdir(parents=True,exist_ok=True)
mapping=json.loads((ROOT/'wflevels/aquarium_lionfish/actor-map.json').read_text())
idx=mapping['indices'];pl=idx['Player'];director=idx['Director']
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs'),WF_REST_HOST='127.0.0.1',WF_REST_PORT='18933')
log=(OUT/'runtime.log').open('w')
proc=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/aquarium_lionfish-standalone.iff'),
                       '-rate20','-width=1280','-height=960','--debug-port','17933','--debug-bind','127.0.0.1','--debug-print-actors'],
                       cwd=ROOT/'wflevels/aquarium_lionfish',env=env,stdout=log,stderr=subprocess.STDOUT)
cli=None
report={}
try:
    cli=BridgeClient(port=17933,timeout=20);cli.send({'op':'pause'})
    cli.inject_input('joystick1_raw',0,duration_frames=-1)
    for actor,boxes in [(pl,[1906,3009,3010,3011]),(director,list(range(930,979))+list(range(1000,1048))+list(range(1050,1074))+list(range(1100,1110))+list(range(1200,1232))+[600,602,605,606,609])]:
        for m in boxes:cli.watch(idx=actor,mailbox=m)
    def value(m,a=director):
        with cli._lock:return cli.mailbox_values.get((a,m),0)
    def setval(m,v,a=director):cli.set_mailbox(m,v,idx=a)
    def step(n=1):
        start=value(1906,pl);cli.send({'op':'step','frames':n});deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if value(1906,pl)>=start+n*3276/65536-.0002:time.sleep(.025);return
            if proc.poll() is not None:raise RuntimeError('engine exited; see runtime.log')
            time.sleep(.005)
        raise RuntimeError('step timeout')
    def hold(bits,n):cli.inject_input('joystick1_raw',bits,duration_frames=-1);step(n)
    def shot(name):
        cli.send({'op':'screenshot','filename':str(OUT/(name+'.png'))})
        msg=cli.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=10)
        assert msg and msg.get('op')=='screenshot_done',msg
    def player(pos):
        hold(0,1)
        for m,v in zip([3009,3010,3011],pos):setval(m,v,pl)
        for m in [605,610,611,612]:setval(m,0)
        setval(602,0)
    def resident(pos=(4.2,.12,2.4)):
        for m,v in zip([1100,1101,1102,1103,1104],list(pos)+[.5,0]):setval(m,v)
        setval(932,-1)
    def reset_food():
        for k in range(3):setval(1000+16*k,0)
        setval(933,0);setval(932,-1);setval(930,0);setval(931,0)
        for base in [1200,1216]:setval(base,-1);setval(base+1,-1)
        for k in range(3):
            for offset in [11,12,13,14,15]:setval(1000+16*k+offset,0)
            setval(1050+8*k+4,-1);setval(1050+8*k+5,-1)
    time.sleep(.2);step(5)
    assert value(600)==1 and value(933)==0,'Initialization failed or phantom prey'
    player((-3.4,0,2.5));step(5);shot('inactive-wide')
    for k in range(3):
        hold(0,1);hold(4097,1)
        assert value(933)==k+1,('release',k,value(933))
    hold(4097,10);assert value(933)==3 and value(605)==0 and value(609)==0
    hold(0,1);hold(4097,1);assert value(933)==3
    shot('three-goldfish-wide');report['release_limit_held_edge']='PASS'
    # Pin prey at known mouth distances; these teleports are test setup only.
    reset_food();resident();player((0,0,2.5))
    setval(1000,1);setval(933,1);setval(1002,.9);setval(1003,0);setval(1004,2.5)
    hold(1,1);assert value(933)==1,'Out-of-range fish eaten'
    hold(0,1);setval(1002,.65);setval(1003,0);setval(1004,2.5)
    eaten=value(934);shot('mouth-rest');hold(1,1)
    assert value(934)==eaten and value(1015)==1 and value(936)>0
    shot('mouth-open');hold(1,1);shot('mouth-capture')
    assert value(934)==eaten+1 and value(933)==0 and value(1000)==0
    report['player_mouth_capture_and_out_of_range']='PASS'
    hold(1,5);shot('mouth-closed');assert value(936)==0 and value(934)==eaten+1
    report['whole_gulp_held_input']='PASS'
    player((-3.4,0,2.5));hold(4097,1);assert value(933)==1
    report['slot_reuse']='PASS'
    # Natural chase: a real release, no prey/player teleports after initialization.
    reset_food();resident((3.7,.12,2.4));player((-4.0,0,2.0))
    hold(4097,1);assert value(932)==-1,'Spawn instantly noticed'
    hold(0,1);assert value(932)==-1,'Ordinary observation delay missing'
    report['release_not_instantly_noticed']='PASS'
    start=[value(m) for m in (1100,1101,1102)];before=value(935)
    samples=[];max_step=0;prior=start
    (OUT/'frames').mkdir(exist_ok=True)
    for k in range(240):
        step(2)
        pos=[value(m) for m in (1100,1101,1102)]
        max_step=max(max_step,math.dist(prior,pos));prior=pos
        samples.append({'tick':2*k,'resident':pos,'active':value(933),'target':value(932),'state':value(1108),'awareness':value(1011),'alarm':value(1012),'burst':value(1013),'gape':value(937)})
        if k<180:shot(f'frames/frame-{k:03d}')
        if value(935)>before:break
    assert value(935)>before,('Resident never caught prey',samples[-1])
    assert max_step<.15,('Resident teleported',max_step)
    report['resident_chase_auto_capture']='PASS';report['chase_trace']=samples
    report['detected_after_seconds']=next((.1*(k+1) for k,s in enumerate(samples) if s['target']>=0),None)
    report['escape_burst_seen']=any(s['burst']>0 for s in samples)
    report['resident_max_two_tick_step']=max_step
    shot('after-resident-capture')
    # Faster real player approach, using movement input after a single setup.
    reset_food();resident();player((-1.4,0,2.5))
    for m,v in [(1000,1),(933,1),(1002,0),(1003,0),(1004,2.5),(1005,.5),(1010,1)]:setval(m,v)
    hold(0,1);burst=False;escape=[]
    for k in range(24):
        hold(8192,1)
        escape.append({'tick':k,'player_x':value(3009,pl),'prey_x':value(1002),'alarm':value(1012),'burst':value(1013)})
        if value(1013)>0:
            burst=True;shot('goldfish-escape');break
    assert burst,('Approaching player never caused escape',escape)
    report['actual_moving_threat_escape']='PASS';report['escape_trace']=escape
    # Camera close-up with prey, then hiding/restart initialization remain readable.
    player((0,0,2.5));reset_food();resident();hold(4097,1);hold(0,5);shot('goldfish-close-up')
    report.update(status='PASS',actors=len(idx),goldfish_actors=[idx[f'goldfish-{k}'] for k in range(3)],
                  player_consumed=value(934),resident_consumed=value(935),simulation_Hz=20)
finally:
    if cli:cli.close()
    proc.terminate()
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close()
    text=(OUT/'runtime.log').read_text(errors='replace')
    assert not any(t in text for t in ['zforth compile error','zforth eval error','ASSERTION FAILED']),text[-2000:]
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT/'.gitignore').write_text('frames/\n*.log\n')
frames=sorted((OUT/'frames').glob('frame-*.png'))
if frames:
    subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','10','-i',str(OUT/'frames/frame-%03d.png'),
                    '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'chase.mp4')],check=True)
print(json.dumps({k:v for k,v in report.items() if k not in ('chase_trace','escape_trace')},indent=2))
