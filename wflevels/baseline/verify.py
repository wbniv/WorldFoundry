#!/usr/bin/env python3
"""Source/compiled checks, plus an optional owned desktop movement session."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'build'
RESULTS=[]

def check(name,condition,**details):
    RESULTS.append(dict(check=name,passed=bool(condition),**details))
    print(name, bool(condition),flush=True)
    if not condition:raise AssertionError(name)

def structural():
    c=json.loads((HERE/'baseline.json').read_text())
    inventory=json.loads((OUT/'scene-inventory.json').read_text())
    objs={o['name']:o for o in inventory}
    preset=json.loads((HERE/'actor-map.json').read_text())['preset']
    half=c['floor_size']/2
    check('configured floor and collision bounds',objs['Floor']['bounds']==[-half,-half,-c['floor_depth'],half,half,0])
    check('explicit player bounds',objs['Player']['bounds']==c['player_bounds'])
    check('no imported adventure/scaffold content',not re.search(r'snowgoons|parmenides|goddess|temple',json.dumps(inventory),re.I))
    check('default excludes diagnostics',preset!='default' or all(o['collection']!='DIAGNOSTICS' for o in inventory))
    config=[o['name'] for o in inventory if o['collection']=='CONFIG' and o['schema']=='target.oad']
    check('two settings owners: FieldTypes and RuntimeSettings, target actors in CONFIG',config==['FieldTypes','RuntimeSettings'],config=config)
    check('Pick in 3D fixture: the two owners share one spot',objs['FieldTypes']['position']==objs['RuntimeSettings']['position'],position=objs['FieldTypes']['position'])
    check('default explicit runtime camera/room objects',all(n in objs for n in ['Level','Room','Camera','CameraOrigin','TargetFollow','TargetFirst','Follow','FirstPerson','Directional','Ambient','Background']))
    from teapot import face_count
    cfg=c['teapots'];faces=[face_count(n) for n in cfg['segments']]
    ladder=[objs.get('Teapot_%d'%f) for f in faces]
    check('teapot ladder: one teapot per rung with the formula face count',all(ladder) and [o['properties'].get('teapot_faces') for o in ladder]==faces and faces==sorted(set(faces)),faces=faces)
    check('teapots are visual-only platform actors in TEAPOTS',all(o['collection']=='TEAPOTS' and o['schema']=='platform.oad' and o['properties'].get('Mass')==0 for o in ladder+[objs['TeapotLabels']]))
    check('teapots stand in one row at the configured spacing',all(abs(a-b)<1e-4 for o,i in zip(ladder,range(len(ladder))) for a,b in zip(o['position'],[cfg['first_x']+i*cfg['spacing'],cfg['row_y'],0])))
    ids=json.loads((HERE/'actor-map.json').read_text())['indices']
    check('teapot actor ids are appended after every existing actor',min(v for k,v in ids.items() if k.startswith('Teapot'))>max(v for k,v in ids.items() if not k.startswith('Teapot')))
    spec=json.loads((HERE/'settings-coverage.json').read_text())
    from settings_fixture import TYPES,SHOW
    check('every declared descriptor type accounted for',set(TYPES)=={f['type'] for f in spec['fields']}|set(spec['exclusions'])|set(spec['structural_types']))
    check('all presentation codes accounted for',set(range(len(SHOW)))<={f['show_code']&127 for f in spec['fields']})
    b=(HERE/'settings-gallery.oad').read_bytes()
    check('complete OAD framing',(len(b)-80)%1491==0)
    entries={}
    for o in range(80,len(b),1491):
        e=b[o:o+1491];key=e[1:65].split(b'\0')[0].decode()
        entries[key]=e
    for f in spec['fields']:
        e=entries[f['key']]
        check('compiled descriptor '+f['key'],e[0]==f['button_type'] and e[591]==f['show_code'] and struct.unpack_from('<iii',e,65)==(f['min'],f['max'],f['default']))
    data=(OUT/'settings.rprp').read_bytes()
    owners=catalog_rows(data)
    check('catalog contains the two owners',[(o['owner'],o['schema']) for o in owners]==[(ids['FieldTypes'],'FieldTypes'),(ids['RuntimeSettings'],'Settings')],owners=[(o['owner'],o['schema'],o['title']) for o in owners])
    examples=[c['id'] for c in json.loads((ROOT/'docs/plans/2026-10-29-touch-settings-examples.json').read_text())]
    types,runtime=owners
    check('Field types: one row per touch-settings example',sorted(r['key'] for r in types['rows'])==sorted(examples),rows=len(types['rows']))
    check('Field types carries no runtime sheet',not any(r['key'].startswith(('runtime_','memory_')) for r in types['rows']) and set(types['sheets'])=={'Numbers','Choices','Switches','Text','References','Actions'},sheets=types['sheets'])
    check('Runtime settings carries exactly the three runtime sheets, 85 rows',runtime['sheets']==['Runtime Options','Level Memory','Level Behavior'] and len(runtime['rows'])==85,sheets=runtime['sheets'],rows=len(runtime['rows']))
    check('standalone L4 and sector-aligned asset', (ROOT/'wflevels/baseline-standalone.iff').read_bytes()[:2]==b'L4' and (ROOT/'wflevels/baseline-standalone.iff').stat().st_size%2048==0)

def catalog_rows(payload):
    """Each RP01 object: owner, schema, title, its sheet names, and every row the form
    draws (stored fields, actions and spacers; sheet and group markers left out)."""
    pos=8;objects=[]
    def take(fmt):
        nonlocal pos;v=struct.unpack_from(fmt,payload,pos);pos+=struct.calcsize(fmt);return v
    def text():
        nonlocal pos;n,=take('<I');v=payload[pos:pos+n].decode();pos+=n;return v
    assert payload[:4]==b'RP01'
    for _ in range(struct.unpack_from('<I',payload,4)[0]):
        owner,=take('<I');o=dict(owner=owner,schema=text(),title=text(),sheets=[],rows=[])
        for _ in range(take('<I')[0]):
            fid,kind=take('<IBBBBiiIII')[:2];key,label=text(),text();[text() for _ in range(4)]
            if kind==5:o['sheets'].append(label)
            elif kind not in (6,7):o['rows'].append(dict(id=fid,kind=kind,key=key,label=label))
        objects.append(o)
    assert pos==len(payload)
    return objects

def main_cd_levels():
    """The main cd.iff's levels in TOC order: wflevels/main-cd.manifest is the one list."""
    import importlib.util
    spec=importlib.util.spec_from_file_location('cd_manifest',ROOT/'scripts/cd_manifest.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.load()

def bundle_checks(path):
    data=path.read_bytes()
    levels=main_cd_levels()
    check('main CD GAME and TOC framing',data[:4]==b'GAME' and data[8:12]==b'TOC\0')
    toc_size=struct.unpack_from('<I',data,12)[0]
    # Shell, the manifest's levels, then the UI font cdpack appends (UIFT).
    check('main CD has the shell, every manifest level and the UI font',toc_size==(len(levels)+2)*12)
    entries=[struct.unpack_from('<4sII',data,16+i*12) for i in range(len(levels)+2)]
    check('main CD preserves shell entry',entries[0][0]==b'SHEL' and entries[0][1]==2048)
    for level in levels:
        tag,offset,size=entries[level.index+1]
        expected=level.path.read_bytes()
        check('main CD level %d is %s'%(level.index,level.slug),offset%2048==0 and size==len(expected) and data[offset:offset+size]==expected)
    tag,offset,size=entries[len(levels)+1]
    font=(ROOT/'wfsource/source/game/ui-font.wfga').read_bytes()
    # The entry is a UIFT chunk: tag, u32 length, then the font file itself.
    body=data[offset:offset+size]
    check('main CD ends with the UI font',tag==b'UIFT' and offset%2048==0 and body[:4]==b'UIFT' and struct.unpack_from('<I',body,4)[0]==len(font) and body[8:]==font)

def desktop(bundle=None):
    sys.path.insert(0,str(ROOT/'tests'))
    from debug_bridge_client import BridgeClient
    port=7785
    ids=json.loads((HERE/'actor-map.json').read_text())['indices'];player=ids['Player']
    capture=OUT/('desktop-cd' if bundle else 'desktop');capture.mkdir(exist_ok=True)
    env=dict(os.environ,DISPLAY=os.environ.get('DISPLAY',':0'),LD_LIBRARY_PATH=str(ROOT/'engine/libs'))
    log=(capture/'engine.log').open('w')
    args=[str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/baseline-standalone.iff'),'--debug-port',str(port),'--debug-bind','127.0.0.1','--debug-print-actors','-width=1280','-height=720','--vram-width=5120','--vram-height=2048','--vram-slot-width=1024','--vram-slot-height=1024','--vram-perm-width=1024','--vram-perm-height=1024']
    # Out-of-range launch overrides, rejected by name only when the engine has loaded that
    # owner's schema and field: positive evidence that both owners are in its registry.
    # A rejected override changes nothing.
    probes=['FieldTypes.int-number=999999','Settings.runtime_show_fps=7']
    args+=['--property='+p for p in probes]
    if bundle:
        shutil.copyfile(bundle,capture/'cd.iff')
        args.pop(1);args.append(str(next(l.index for l in main_cd_levels() if l.slug=='baseline')))
    proc=subprocess.Popen(args,cwd=capture,env=env,stdout=log,stderr=subprocess.STDOUT)
    bridge=None
    try:
        bridge=BridgeClient(port=port,timeout=20)
        for m in [3009,3010,3011,3014,111]:bridge.watch(player,m)
        for m in [120,121,122,1921]:bridge.watch(ids['Director'],m)
        def position():return [bridge.mailbox_values.get((player,m)) for m in [3009,3010,3011]]
        def settle(seconds=1):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError('Runtime exited; see '+str(capture/'engine.log'))
                time.sleep(.05)
        def hold(bit,seconds=.8):
            bridge.inject_input('joystick1_raw',bit,-1)
            if not bridge.wait_for_mailbox(ids['Director'],121,bit,timeout=5):raise RuntimeError('Director did not observe injected press')
            settle(seconds)
            bridge.inject_input('joystick1_raw',0,-1)
            if not bridge.wait_for_mailbox(ids['Director'],121,0,timeout=5):raise RuntimeError('Director did not observe injected release')
            settle(.6)
        def shot(name):
            bridge.send(dict(op='screenshot',filename=str(capture/(name+'.png'))));settle(.3)
        settle(2)
        check('native script compilation succeeds','zforth compile error' not in (capture/'engine.log').read_text())
        # The engine validates every authored initial value when it loads the catalog.
        text=(capture/'engine.log').read_text()
        check('engine loads the settings catalog','PROPERTIES load failed' not in text)
        rejected=[line for line in text.splitlines() if line.startswith('PROPERTIES launch-override rejected: ')]
        check('engine registry holds both owners (launch-override probes rejected by name)',all(any(line.startswith('PROPERTIES launch-override rejected: '+p+': ') for line in rejected) for p in probes),rejected=rejected)
        start=position();check('native player grounded at spawn',all(v is not None for v in start) and abs(start[0])<.05 and abs(start[1]+5)<.05 and .85<start[2]<1.05,position=start)
        shot('spawn')
        hold(2048);forward=position();check('native held Up moves +Y',forward[1]>start[1]+.3,position=forward)
        settle(1);released=position();check('native release settles movement',sum((a-b)**2 for a,b in zip(forward,released))<.05,position=released)
        hold(2,.1);reset=position();check('B resets native player',abs(reset[0])<.05 and abs(reset[1]+5)<.05,position=reset)
        # Debug-assisted direction setup; actual movement remains native input.
        bridge.set_mailbox(3014,0,player);settle(.2);hold(2048);p=position()
        check('native Up with zero heading moves +X',abs(p[0])>.3,position=p)
        hold(2,.1)
        hold(4,.1);check('camera switches to first-person',bridge.mailbox_values.get((ids['Director'],122))==1)
        shot('first-person');hold(4,.2)
        check('camera switches back to follow',bridge.mailbox_values.get((ids['Director'],122))==0,mode=bridge.mailbox_values.get((ids['Director'],122)),previous_input=bridge.mailbox_values.get((ids['Director'],121)))
        shot('follow')
        # Debug-assisted collision approach: player starts facing the unit cube.
        bridge.send(dict(op='scene:set_transform',idx=player,pos=[5,-2,.92]));bridge.set_mailbox(3014,.25,player);settle(.3)
        hold(2048,1.2);p=position();check('unit cube blocks native movement',p[1]<-.65,position=p)
        shot('cube-collision')
        for x,y in [(-90,-90),(90,-90),(-90,90),(90,90)]:
            bridge.send(dict(op='scene:set_transform',idx=player,pos=[x,y,1.1]))
            if not bridge.wait_for_mailbox(player,3009,x,timeout=8) or not bridge.wait_for_mailbox(player,3010,y,timeout=8):raise RuntimeError('Runtime did not acknowledge quadrant setup')
            settle(.7);p=position()
            check('quadrant floor support '+str((x,y)),abs(p[0]-x)<.1 and abs(p[1]-y)<.1 and .85<p[2]<1.05,position=p)
        bridge.send(dict(op='scene:set_transform',idx=player,pos=[102,0,-9]));settle(.8)
        p=position();check('fall reset restores spawn',abs(p[0])<.05 and abs(p[1]+5)<.05,position=p)
        hold(2049,.1);p=position();check('remote Up+OK resets without jumping',abs(p[1]+5)<.05 and .85<p[2]<1.05,position=p)
        check('runtime still running',proc.poll() is None)
    finally:
        if bridge:bridge.close()
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--desktop',action='store_true');ap.add_argument('--bundle',type=Path,help='Verify baseline at TOC index 7 in a main CD');args=ap.parse_args()
    try:
        structural()
        if args.bundle:bundle_checks(args.bundle)
        if args.desktop:desktop(args.bundle)
    finally:
        OUT.mkdir(exist_ok=True)
        (OUT/'verification.json').write_text(json.dumps(dict(desktop_requested=args.desktop,bundleSha256=hashlib.sha256(args.bundle.read_bytes()).hexdigest() if args.bundle else None,desktopExecutableSha256=hashlib.sha256((ROOT/'engine/wf_game').read_bytes()).hexdigest(),standaloneSha256=hashlib.sha256((ROOT/'wflevels/baseline-standalone.iff').read_bytes()).hexdigest(),checks=RESULTS),indent=2)+'\n')
