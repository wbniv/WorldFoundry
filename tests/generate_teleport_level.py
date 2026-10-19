"""Build a small four-room teleport regression from checked-in engine assets.

No Blender, chapter checkout, APK or live device is required. Room D has no
neighbours; A has B and C. Every room owns a non-permanent mesh so its RM chunk
exists. The anchored permanent Player moves only through its Forth script.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def field(obj, name, value, tag='STR'):
    pattern=r"(\{ '"+tag+r"'\s+\{ 'NAME' \""+re.escape(name)+r"\" \}\s+\{ '(?:STR|DATA)' )[^}]+"
    result,count=re.subn(pattern,lambda m:m[1]+value+' ',obj)
    if not count:
        end=obj.rfind('}')
        assert end>=0
        result=obj[:end]+"{ '"+tag+"' { 'NAME' "+json.dumps(name)+" } { 'DATA' "+value+" } }\n"+obj[end:]
    return result


def name(obj, value):
    return re.sub(r"\{ 'NAME' \"[^\"]*\" \}",lambda m:"{ 'NAME' "+json.dumps(value)+" }",obj,count=1)


def enum(obj, key, index, label):
    # levcomp follows the displayed STR for enum fields, even when DATA differs.
    pattern=r"(\{ 'I32'\s+\{ 'NAME' \""+re.escape(key)+r"\" \}\s+\{ 'DATA' )[^}]+(\}\s+\{ 'STR' )\"[^\"]*\""
    result,count=re.subn(pattern,lambda m:m[1]+str(index)+'l '+m[2]+json.dumps(label),obj)
    assert count==1,key
    return result


def vector(obj, key, values, tag):
    return field(obj,key,' '.join(f'{v:.16f}(1.15.16)' for v in values),tag)


def generate(repo, tools, out, camera='fixed', autonomous=False, unloaded_actor=False, unloaded_autonomous=False):
    assert not unloaded_autonomous or (unloaded_actor and not autonomous), 'unloaded autonomous mode requires --unloaded-actor and excludes --autonomous'
    out.mkdir(parents=True,exist_ok=True)
    source=repo/'wflevels/qbert_practice'
    text=(source/'qbert_practice.lev').read_text()
    objects={}
    for obj in text.split("\n\t{ 'OBJ'")[1:]:
        obj=obj.rsplit('\n}',1)[0] if obj.endswith('\n}\n') else obj
        objects[re.search(r"\{ 'NAME' \"([^\"]*)\"",obj)[1]]=obj
    entries=[]
    for index,(a,b) in enumerate([('B','C'),('A',''),('A',''),('','')]):
        obj=name(objects['Room01'],chr(65+index))
        obj=vector(obj,'Position',(index*100,0,0),'VEC3')
        obj=vector(obj,'Global Bounding Box',(-20,-30,-20,20,30,40),'BOX3')
        obj=field(obj,'Adjacent Room 1',json.dumps(a))
        entries.append(field(obj,'Adjacent Room 2',json.dumps(b)))
    for key in ['Level','Camera','Director','cs_pyramid','Player','Target01','Target02']:
        obj=objects[key]
        obj=vector(obj,'Position',(0,0,7),'VEC3')
        if key=='Camera':obj=vector(obj,'Position',(0,-15,12),'VEC3')
        if key=='Player':
            obj=field(obj,'Tool A','""')
            script=('\\ t4 teleport command script\n'
                '470 read-mailbox 471 read-mailbox <> if\n'
                '470 read-mailbox 1 = if 300 INDEXOF_X_POS write-mailbox then\n'
                '470 read-mailbox 2 = if 100 INDEXOF_X_POS write-mailbox then\n'
                '470 read-mailbox 3 = if 200 INDEXOF_X_POS write-mailbox then\n'
                '470 read-mailbox 4 = if 0 INDEXOF_X_POS write-mailbox then\n'
                '470 read-mailbox 6 = if 5 INDEXOF_X_POS write-mailbox then\n'
                '470 read-mailbox 5 = if 300 INDEXOF_X_POS write-mailbox '
                '100 INDEXOF_X_POS write-mailbox 200 INDEXOF_X_POS write-mailbox then\n'
                '0 INDEXOF_Y_POS write-mailbox 7 INDEXOF_Z_POS write-mailbox\n'
                '470 read-mailbox 471 write-mailbox then\n')
            if autonomous:
                emit=' '.join(f'{ord(c)} 0 sys' for c in 'T4_ARRIVAL ')
                prefix=('\\ autonomous device regression; report on the next actor update\n'
                    '0.25 INDEXOF_Z_SCALE 18 write-actor-mailbox\n'
                    '474 read-mailbox 1 = if '+emit+' '
                    '473 read-mailbox 1 sys 471 read-mailbox 1 sys INDEXOF_X_POS read-mailbox 1 sys '
                    'INDEXOF_X_POS 6 read-actor-mailbox 1 sys INDEXOF_Z_SCALE 18 read-actor-mailbox 1 sys '
                    'INDEXOF_X_POS read-mailbox INDEXOF_X_POS 6 read-actor-mailbox - abs 0.01 < '
                    'INDEXOF_Z_SCALE 18 read-actor-mailbox 0.25 = & 1 sys 10 0 sys '
                    '0 474 write-mailbox then\n'
                    '472 read-mailbox INDEXOF_DELTA_TIME read-mailbox + 472 write-mailbox\n'
                    '472 read-mailbox 0.5 >= if 0 472 write-mailbox '
                    '473 read-mailbox dup 7 / 0 | 7 * - '
                    'dup 0 = if 2 470 write-mailbox then '
                    'dup 1 = if 4 470 write-mailbox then '
                    'dup 2 = if 1 470 write-mailbox then '
                    'dup 3 = if 2 470 write-mailbox then '
                    'dup 4 = if 5 470 write-mailbox then '
                    'dup 5 = if 1 470 write-mailbox then '
                    '6 = if 4 470 write-mailbox then '
                    '473 read-mailbox 1 + 473 write-mailbox 1 474 write-mailbox then\n')
                script=prefix+script
            obj=field(obj,'Script',json.dumps(script))
            if unloaded_actor:
                script=('480 read-mailbox 1 + 480 write-mailbox\n'+script.replace(
                    '470 read-mailbox 471 write-mailbox then',
                    '470 read-mailbox 7 = if -5 INDEXOF_X_POS 20 write-actor-mailbox '
                    '0 INDEXOF_Y_POS 20 write-actor-mailbox 7 INDEXOF_Z_POS 20 write-actor-mailbox then\n'
                    '470 read-mailbox 8 = if 295 INDEXOF_X_POS 20 write-actor-mailbox then\n'
                    '470 read-mailbox 9 = if 295 INDEXOF_X_POS 20 write-actor-mailbox '
                    '-5 INDEXOF_X_POS 20 write-actor-mailbox then\n'
                    '470 read-mailbox 471 write-mailbox then'))
                obj=field(obj,'Script',json.dumps(script))
                if unloaded_autonomous:
                    emit=' '.join(f'{ord(c)} 0 sys' for c in 'T4_ACTOR ')
                    sequence=[7,8,9,8,1,4,7,8,7,8,9,8]
                    dispatch=' '.join(f'dup {index} = if {command} 470 write-mailbox then'
                                      for index,command in enumerate(sequence))+' drop '
                    prefix=('472 read-mailbox INDEXOF_DELTA_TIME read-mailbox + 472 write-mailbox\n'
                        '472 read-mailbox 0.6 >= if 0 472 write-mailbox\n'
                        '474 read-mailbox 1 = if '+emit+' '
                        '473 read-mailbox 1 sys 471 read-mailbox 1 sys '
                        'INDEXOF_X_POS read-mailbox 1 sys INDEXOF_X_POS 6 read-actor-mailbox 1 sys '
                        'INDEXOF_X_POS 20 read-actor-mailbox 1 sys '
                        '481 read-mailbox 483 read-mailbox - 1 sys '
                        '480 read-mailbox 484 read-mailbox - 1 sys 10 0 sys then\n'
                        '481 read-mailbox 483 write-mailbox 480 read-mailbox 484 write-mailbox\n'
                        '473 read-mailbox dup 12 / 0 | 12 * - '+dispatch+
                        '473 read-mailbox 1 + 473 write-mailbox 1 474 write-mailbox then\n')
                    obj=field(obj,'Script',json.dumps(prefix+script))
        if key=='Director':
            # Four room objects precede Level, Camera, Director and this shot.
            # The integration test checks these indices in real engine output.
            obj=field(obj,'Script',json.dumps('\\ t4 camera\n8 INDEXOF_CAMSHOT write-mailbox\n'))
        if key=='cs_pyramid':
            obj=field(obj,'Track Object','"Player"')
            for ref in ['Follow','Target']:obj=field(obj,ref,'"Target01"')
            obj=vector(obj,'Position',(0,-15,5),'VEC3')
            for axis in ['X','Y','Z']:
                obj=enum(obj,'Position '+axis,1 if camera=='follow' else 0,
                         'Relative' if camera=='follow' else 'Absolute')
            obj=enum(obj,'Rotation',0,'Fixed')
        entries.append(obj)
    for index in range(4):
        marker=name(objects['redball_0'],f'Marker{index}')
        marker=vector(marker,'Position',(index*100+5,0,7),'VEC3')
        marker=field(marker,'Script','""')
        marker=field(marker,'Mobility','"Anchored"','I32')
        marker=field(marker,'Moves Between Rooms','0l','I32')
        marker=field(marker,'Visibility Mailbox','1l','I32')
        entries.append(marker)
        light=name(objects['Light01'],f'Light{index}')
        entries.append(vector(light,'Position',(index*100,0,15),'VEC3'))
    if unloaded_actor:
        for label,x,heartbeat in [('InactiveTarget',295,481),('ActiveControl',-10,482)]:
            helper=name(objects['redball_0'],label)
            helper=vector(helper,'Position',(x,0,7),'VEC3')
            helper=field(helper,'Mobility','"Anchored"','I32')
            helper=field(helper,'Moves Between Rooms','1l','I32')
            helper=field(helper,'Visibility Mailbox','1l','I32')
            helper=field(helper,'Script',json.dumps(f'{heartbeat} read-mailbox 1 + {heartbeat} write-mailbox\n'))
            entries.append(helper)
    level='teleport_regression'
    (out/(level+'.lev')).write_text("{ 'LVL'\n"+''.join("\n\t{ 'OBJ'"+o for o in entries)+'\n}\n')
    for mesh in ['player.iff','redball.iff']:shutil.copy2(source/mesh,out/mesh)
    for image in source.glob('*.tga'):shutil.copy2(image,out/image.name)
    log=[]
    def run(tool,*args):
        command=[str(tools/(tool+'-rs')/'target/release'/tool),*map(str,args)]
        result=subprocess.run(command,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        log.extend(['$ '+repr(command),result.stdout,'Exit status: '+str(result.returncode)])
        (out/'compile.log').write_text('\n'.join(log))
        if result.returncode:raise RuntimeError(result.stdout[-2000:])
    run('iffcomp','-binary','-o='+level+'.lev.bin',level+'.lev')
    run('levcomp',level+'.lev.bin',repo/'wfsource/source/oas/objects.lc',level+'.lvl',repo/'wfsource/source/oas',
        '--mesh-dir','.','--iff-txt',level+'.iff.txt','--textile-ini',level+'.ini')
    run('textile','-ini='+level+'.ini','-Tlinux','-transparent=0,0,0','-pagex=1024','-pagey=1024',
        '-permpagex=1024','-permpagey=1024','-palx=256','-paly=8','-alignx=w','-aligny=h','-flipyout')
    run('iffcomp','-binary','-o='+level+'.iff',level+'.iff.txt')
    (out/(level+'-standalone.iff.txt')).write_text("{ 'L4' { 'ALGN' .align(2048) } { 'RAM' 'OBJD' 4194304l 'PERM' 16777216l 'ROOM' 8388608l 'FLAG' 1l 1l } { 'ALGN' .align(2048) } [ \""+level+".iff\" ] }\n")
    run('iffcomp','-binary','-o='+level+'-standalone.iff',level+'-standalone.iff.txt')
    receipt={'rooms':{'A':['B','C'],'B':['A'],'C':['A'],'D':[]},
        'camera':camera,
        'autonomous':autonomous,
        'unloaded_actor':unloaded_actor,
        'unloaded_autonomous':unloaded_autonomous,
        'inactive_target_index':20 if unloaded_actor else None,
        'active_control_index':21 if unloaded_actor else None,
        'player_index':9,'camera_shot_index':8,'unloaded_marker_index':18,
        'inputs':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [source/'qbert_practice.lev',source/'player.iff',source/'redball.iff']},
        'tools':{tool:hashlib.sha256((tools/(tool+'-rs')/'target/release'/tool).read_bytes()).hexdigest()
                 for tool in ['iffcomp','levcomp','textile']},
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob(level+'*') if p.is_file()}}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(out/(level+'-standalone.iff'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--tools',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--camera',choices=['fixed','follow'],default='fixed')
    parser.add_argument('--autonomous',action='store_true',help='Cycle teleports and print next-frame pose/scale assertions for coordinated device tests')
    parser.add_argument('--unloaded-actor',action='store_true',help='Add a permanent target in D and heartbeat control in A; Player command 7 moves the target into A')
    parser.add_argument('--unloaded-autonomous',action='store_true',help='Cycle inactive-source actor moves and report per-interval heartbeats for device verification')
    args=parser.parse_args();generate(args.repo,args.tools,args.out,args.camera,args.autonomous,args.unloaded_actor,args.unloaded_autonomous)
