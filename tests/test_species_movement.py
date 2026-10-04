"""Trajectory and contact regressions against the actual exported Forth programs."""
import ast
import csv
import io
import json
import math
from pathlib import Path
import re
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
BUTTON={'right':8192,'left':16384,'up':2048,'down':4096,'ok':1}

@pytest.fixture(scope='module')
def vm(tmp_path_factory):
    tmp=tmp_path_factory.mktemp('species-vm')
    src=(ROOT/'engine/stubs/scripting_zforth.cc').read_text()
    core=src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')]
    core=re.sub(r'//[^\n]*','',core)
    definitions=''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"',core))
    mailbox=(ROOT/'wfsource/source/mailbox/mailbox.inc').read_text()
    constants={f'INDEXOF_{k}':int(v) for k,v in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)',mailbox)}
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate('ABCDEFGHIJK')})
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate(('UP','DOWN','RIGHT','LEFT'),11)})
    definitions+='\n'+''.join(f': {k} {v} ;\n' for k,v in constants.items())
    definitions+=": read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ; : read-actor-mailbox 152 sys ; : fin-deform 172 sys ; : fish-deform 171 sys ; : jelly-deform 174 sys ; : plant-register 175 sys ; : plant-step 176 sys ; : profile-begin 169 sys ; : profile-end 170 sys ; : r@ ' lit , 0 , ' pickr , ; immediate\n"
    vendor=ROOT/'engine/vendor/zforth-41db72d1/src/zforth'
    binary=tmp/'vm'
    subprocess.run(['cc','-O1','-I'+str(ROOT/'engine/stubs'),'-I'+str(vendor),str(ROOT/'tests/species_vm.c'),str(vendor/'zforth.c'),'-lm','-o',str(binary)],check=True)
    def run(kind,trace):
        level='aquarium_'+kind; here=ROOT/'wflevels'/level
        mapping=json.loads((here/'actor-map.json').read_text())
        text=(here/(level+'.lev')).read_text()
        paths=[]
        prefix='sh' if kind=='blue_shrimp' else 'tk'
        entries=('aq-player-tick','barb-player-tick\naq-camera-tick\nsd-tick') if kind=='tiger_barbs' else (prefix+'-player-tick',prefix+'-director-tick')
        for name,entry in zip(('Player','Director'),entries):
            block=text[text.index('{ \'NAME\' "'+name+'" }'):].split("{ 'OBJ'",1)[0]
            encoded=re.search(r'\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' ("(?:\\.|[^"\\])*")',block).group(1)
            script=json.loads(encoded).removesuffix('\n'+entry+'\n')
            path=tmp/(kind+name+'.fth');path.write_text(definitions+script);paths.append(path)
        result=subprocess.run([str(binary),*map(str,paths),str(mapping['indices']['Player']),str(mapping['indices']['Director']),*entries],input=trace,text=True,capture_output=True)
        assert result.returncode==0,result.stderr
        keys=['frame','x','y','z','vx','vy','vz',*range(600,751),*range(1100,1112),*range(1200,1281),'part-x','part-y','part-z','part-a','part-b','part-c']
        return [dict(zip(keys,map(float,row))) for row in csv.reader(io.StringIO(result.stdout))]
    return run

@pytest.mark.parametrize('kind',['betta','lionfish'])
@pytest.mark.parametrize('hz',[20,30,60])
def test_fish_forward_reversal_and_camera_facing_arc(vm,kind,hz):
    rows=vm(kind,f'reset 0 0 2.5\nstep {hz} 8192 {1/hz}\nstep {hz*4} 16384 {1/hz}\nstep {hz*3} 0 {1/hz}\n')
    assert rows[hz-1]['vx']>.7
    turn=rows[hz:hz*3]
    assert any(r['vy']<-.03 for r in turn),'reversal should show the head toward the front glass'
    assert any(r['vx']<-.6 for r in turn)
    assert math.sqrt(sum(rows[-1][k]**2 for k in ['vx','vy','vz']))<.003
    for row in rows:
        yaw=row[602]*math.tau;pitch=row[700]*math.tau
        forward=(math.cos(yaw)*math.cos(pitch),math.sin(yaw)*math.cos(pitch),math.sin(pitch))
        assert all(abs(row[k]-row[704]*f)<.008 for k,f in zip(['vx','vy','vz'],forward))
        assert abs(row['y'])<=.2701

@pytest.mark.parametrize('kind',['betta','lionfish'])
def test_pitch_attachment_and_wall_recovery(vm,kind):
    rows=vm(kind,'reset 4.69 0 2.5\nstep 80 16384 .05\nstep 50 2048 .05\n')
    assert rows[60]['x']<3.5
    assert rows[-1][700]>.07 and rows[-1]['vz']>.25
    assert abs(rows[-1]['part-b']+rows[-1][700])<.1
    assert all(abs(r['x'])<=4.7001 and abs(r['y'])<=.2701 for r in rows)

def test_jelly_pulses_do_not_restart_and_release_retains_drift(vm):
    rows=vm('jellyfish','reset 0 0 2.6\nstep 80 8193 .05\nstep 60 4096 .05\n')
    phases=[r[732] for r in rows[:80]]
    resets=[i for i in range(1,len(phases)) if phases[i]<phases[i-1]]
    assert len(resets)<=2 and all(b-a>=55 for a,b in zip(resets,resets[1:]))
    assert rows[79]['vx']>.02 and rows[80]['vx']>.01
    assert rows[-1]['vz']<-.05,'Down suppresses strokes and lets drag/settling act'
    assert all(abs(r['y'])<=.3401 and 1.8499<=r['z']<=3.6501 for r in rows)
    # Resident state changes through integrated motion with staggered stroke clocks.
    assert rows[0][1200]!=rows[-1][1200]
    assert rows[-1][1203]!=rows[-1][1219]

def test_remote_chord_and_resume_rearm(vm):
    for kind in ['betta','lionfish','jellyfish','blue_shrimp']:
        rows=vm(kind,'reset 0 0 2.5\nstep 1 2049 .05\nstep 4 2049 .05\nstep 1 0 .05\nstep 10 2048 .05\nstep 1 2048 2\nstep 5 2048 .05\n')
        mode=628 if kind=='blue_shrimp' else 604
        assert rows[0][mode]==1
        assert abs(rows[-6]['vz'])<.001,(kind,rows[-6]['vz'])
        if kind in ['jellyfish','blue_shrimp']:
            assert all(r['vz']<=.001 for r in rows[-5:])
        else:
            assert all(abs(r['vz'])<.001 for r in rows[-5:])

def test_shrimp_stops_walking_swims_and_escapes_backwards(vm):
    rows=vm('blue_shrimp','reset 1.9 -.65 .965\nstep 40 8192 .05\nstep 80 0 .05\nstep 30 2048 .05\nstep 1 0 .05\nstep 3 1 .05\n')
    assert rows[39]['x']>2.8
    assert abs(rows[119][639]-rows[109][639])<.001,'idle walking legs keep cycling'
    assert rows[149]['z']>1.3 and rows[149][684]>.02
    assert rows[-1]['vx']<0 and rows[-1][636]>0
    assert all(r['z']>=.9649 for r in rows)

def test_urchin_depth_diagonal_cap_and_action_only_view(vm):
    rows=vm('plants','reset 0 -.5 .865\nstep 1200 10240 .05\nstep 40 1 .05\n')
    assert rows[1199]['x']>.50 and rows[1199]['y']>0
    assert all(math.sqrt(r['vx']**2+r['vy']**2)<=.012501 for r in rows)
    assert all(abs(r['z']-.865)<1e-6 for r in rows)
    assert rows[1200][625]==rows[1199][625]  # Native tap/hold controller owns this now.
    assert rows[-1][740]!=0,'contact phase should reflect displacement'

def test_native_jelly_apex_margin_roots_and_repeatable_rest(tmp_path):
    source=tmp_path/'jelly.cc'
    source.write_text('''
#include <cassert>
#include <cmath>
#include <renderassets/jelly_deform.h>
int main() {
 using wf_render::JellyWeight;
 float x,y,z;
 auto apex=JellyWeight::make(0,0,.30f);
 auto margin=JellyWeight::make(.48f,0,0);
 auto root=JellyWeight::make(.13f,0,0);
 auto arm=JellyWeight::make(.13f,0,-1.f);
 apex.deform(1,.2f,.025f,.025f,x,y,z); assert(z==.30f && x==0 && y==0);
 margin.deform(1,.2f,0,0,x,y,z); assert(std::abs(x-.3936f)<.00001f && z==0);
 root.deform(1,.2f,.025f,.025f,x,y,z); assert(std::abs(x-.1066f)<.00001f && y==0 && z==0);
 arm.deform(1,.2f,.025f,.025f,x,y,z); assert(x<.01f && y>.14f && z==-1.f);
 for(int i=0;i<100000;i++) arm.deform((i%100)/100.f,i*.01f,.025f,-.025f,x,y,z);
 arm.deform(0,0,0,0,x,y,z);
 float rx,ry,rz;arm.deform(0,0,0,0,rx,ry,rz);
 assert(x==rx && y==ry && z==rz); // rest cache, no accumulated movement
}
''')
    binary=tmp_path/'jelly'
    subprocess.run(['c++','-std=c++11','-I'+str(ROOT/'wfsource/source'),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

@pytest.mark.parametrize('kind',['betta','lionfish'])
def test_full_pitched_banked_rig_keeps_floor_and_glass_clear(kind):
    import importlib.util
    import sys
    import numpy as np
    sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
    if kind=='betta':
        sys.path.insert(0,str(ROOT/'wflevels/aquarium_betta'))
        from detailed_model import detailed_models
        meshes,offsets=detailed_models()
    else:
        from lionfish_mouth import feeding_models
        meshes,offsets=feeding_models()
    spec=importlib.util.spec_from_file_location('movement_config',ROOT/f'wflevels/aquarium_{kind}/config.py')
    cfg=importlib.util.module_from_spec(spec);spec.loader.exec_module(cfg)
    mapping=json.loads((ROOT/f'wflevels/aquarium_{kind}/actor-map.json').read_text())
    points=np.array([tuple(v[i]+off[i] for i in range(3)) for mesh,off in zip(meshes,offsets) for v in mesh.vertices])
    for pitch in (-math.pi/6,0,math.pi/6):
        for roll in (-.018*math.tau,0,.018*math.tau):
            ca,sa=math.cos(roll),math.sin(roll);cb,sb=math.cos(-pitch),math.sin(-pitch)
            posed=points@np.array([[1,0,0],[0,ca,-sa],[0,sa,ca]]).T@np.array([[cb,0,sb],[0,1,0],[-sb,0,cb]]).T
            # Extra reserve for free-edge deformation/local sculling, in addition to root pose.
            radial=np.sqrt(posed[:,0]**2+posed[:,1]**2).max()+.12
            assert radial+mapping['limits'][1]<1.524
            assert radial+mapping['limits'][0]<5.969
            assert cfg.BOTTOM+posed[:,2].min()-.04>.635
            assert cfg.TOP+posed[:,2].max()+.04<4.826


def test_jelly_bounded_slow_frame_integration(vm):
    ends=[]
    for dt,n in [(.05,240),(.1,120),(.15,80)]:
        rows=vm('jellyfish',f'reset 0 0 2.6\nstep {n} 8193 {dt}\n')
        assert all(abs(r['x'])<=4.7001 and abs(r['y'])<=.3401 and 1.8499<=r['z']<=3.6501 for r in rows)
        ends.append(rows[-1])
    assert max(r['x'] for r in ends)-min(r['x'] for r in ends)<.10
    assert max(r['z'] for r in ends)-min(r['z'] for r in ends)<.10
