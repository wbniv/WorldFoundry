"""Actual generated zForth controller at controlled timesteps, with mailbox IO only mocked."""
import ast
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
import arowana


@pytest.fixture(scope='module')
def vm(tmp_path_factory):
    tmp=tmp_path_factory.mktemp('arowana-vm')
    src=(ROOT/'engine/stubs/scripting_zforth.cc').read_text()
    core=src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')]
    core=re.sub(r'//[^\n]*','',core)
    bootstrap=''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"',core))
    mailbox=(ROOT/'wfsource/source/mailbox/mailbox.inc').read_text()
    constants={f'INDEXOF_{k}':int(v) for k,v in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)',mailbox)}
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate('ABCDEFGHIJK')})
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate(('UP','DOWN','RIGHT','LEFT'),11)})
    definitions=bootstrap+'\n'+''.join(f': {k} {v} ;\n' for k,v in constants.items())
    definitions+=": read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ; : read-actor-mailbox 152 sys ; : swim-deform 173 sys ; : r@ ' lit , 0 , ' pickr , ; immediate\n"
    mapping=json.loads((ROOT/'wflevels/aquarium_arowana/actor-map.json').read_text())
    spec=importlib.util.spec_from_file_location('ar_config',ROOT/'wflevels/aquarium_arowana/config.py')
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    vendor=ROOT/'engine/vendor/zforth-41db72d1/src/zforth'
    binary=tmp/'vm'
    subprocess.run(['cc','-I'+str(ROOT/'engine/stubs'),'-I'+str(vendor),str(ROOT/'tests/arowana_vm.c'),str(vendor/'zforth.c'),'-lm','-o',str(binary)],check=True)
    def run(trace,profile='keyboard'):
        player,director,_=arowana.scripts(mapping['indices'],mapping['parts'],mapping['offsets'],profile,c)
        pp=tmp/'player.fth';dp=tmp/'director.fth'
        pp.write_text(definitions+player.rsplit('\n',2)[0]+'\n')
        dp.write_text(definitions+director.rsplit('\n',2)[0]+'\n')
        result=subprocess.run([str(binary),str(pp),str(dp),str(mapping['indices']['Player']),str(mapping['indices']['Director'])],input=trace,text=True,capture_output=True)
        assert result.returncode==0,result.stderr
        names=['scenario','frame','x','y','z','vx','vy','vz','yaw','yaw_rate','yaw_target','pitch','pitch_rate','pitch_target','roll','speed','cool','turn','radius','yaw_cap','error','state','room','bend','dart','mode','neutral','push','phase','pec_phase','dy','wave_phase','wave_amp','wave_bend','fin_amp','dt']
        return [dict(zip(names,map(float,row))) for row in csv.reader(io.StringIO(result.stdout))]
    return run


def assert_safe(rows):
    previous=None
    for r in rows:
        assert abs(r['x'])<=15.521 and abs(r['y'])<=10.521 and 3.649<=r['z']<=8.351,r
        assert abs(r['pitch'])<=1/12+.00001 and abs(r['roll'])<=8/360+.00001
        assert r['push']==0, r
        f=(math.cos(r['pitch']*math.tau)*math.cos(r['yaw']*math.tau),math.cos(r['pitch']*math.tau)*math.sin(r['yaw']*math.tau),math.sin(r['pitch']*math.tau))
        assert all(abs(r[k]-r['speed']*d)<.012 for k,d in zip(('vx','vy','vz'),f)),r
        if not r['turn']:
            assert abs(r['yaw_rate'])<=r['speed']/r['radius']/math.tau+.00005,r
            if previous is not None and not previous['turn']:
                change=(r['yaw']-previous['yaw']+.5)%1-.5
                assert abs(change)/r['dt']<=r['speed']/r['radius']/math.tau+.0005,r
        previous=r


def test_cruise_reverse_and_release_at_20_30_60_hz(vm):
    ends=[]
    for rate in [20,30,60]:
        rows=vm(f'reset 1 0 0 6 0\nstep {rate*3} 8192 {1/rate}\nstep {rate*24} 16384 {1/rate}\nstep {rate*6} 0 {1/rate}\n')
        assert_safe(rows)
        assert any(r['turn'] for r in rows) and any(abs(r['bend'])>.12 for r in rows)
        assert any(r['vx']<-1 for r in rows),rows[-1]
        assert rows[-1]['speed']==0
        ends.append(rows[-1])
    assert max(e['x'] for e in ends)-min(e['x'] for e in ends)<.7
    assert max(e['y'] for e in ends)-min(e['y'] for e in ends)<.7


def test_wall_corner_sweeps_and_inward_recovery(vm):
    # Begin inside the reserved envelope, facing each wall/corner.
    for x,y,z,yaw,inward in [(15.45,0,6,0,16384),(-15.45,0,6,.5,8192),(0,10.45,6,.25,2),(0,-10.45,6,-.25,4),(15.45,10.45,6,.125,16386),(15.45,-10.45,6,-.125,16388),(0,0,8.25,0,4096),(0,0,3.75,0,2048)]:
        rows=vm(f'reset 1 {x} {y} {z} {yaw}\nstep 700 {inward} .05\n')
        assert_safe(rows)
        assert math.dist((x,y,z),[rows[400][k] for k in ('x','y','z')])>1,'failed inward recovery'


def test_burst_recovery_and_held_or_repeated_action(vm):
    rows=vm('reset 1 0 0 6 0\nstep 80 8193 .05\nstep 1 8192 .05\nstep 1 8193 .05\n')
    assert_safe(rows)
    assert rows[0]['dart']>.25 and rows[7]['dart']==0
    assert all(r['dart']==0 for r in rows[8:80]),'held action restarts a burst'
    assert rows[-1]['dart']>.25,'new press after recovery did not burst'
    rows=vm('reset 1 0 0 6 0\nstep 1 8193 .05\nstep 1 8192 .05\nstep 1 8193 .05\n')
    assert rows[-1]['dart']<rows[0]['dart'],'repeated edge stacks a burst'


def test_remote_chord_neutral_rearm_and_resume(vm):
    rows=vm('reset 1 0 0 6 0\nstep 1 2048 .05\nstep 1 2049 .05\nstep 8 8193 .05\nstep 1 8192 .05\nstep 1 0 .05\nstep 1 2048 .05\n','remote')
    assert rows[1]['mode']==1 and rows[1]['neutral']==1
    assert all(r['dart']==0 for r in rows)
    assert all(r['dy']==0 for r in rows[1:11])
    assert rows[-1]['dy']==1 and rows[-1]['neutral']==0
    resumed=vm('reset 1 0 0 6 0\nstep 20 8193 .05\nstep 1 8193 2\nstep 10 8193 .05\nstep 1 0 .05\nstep 1 8193 .05\n','remote')
    assert resumed[20]['speed']==0 and resumed[20]['neutral']==1
    assert all(r['dart']==0 for r in resumed[20:31])
    assert resumed[-1]['dart']>.25


def test_touch_mode_and_desktop_depth_parity(vm):
    touch=vm('reset 1 0 0 6 0\nstep 1 1 .05\nstep 5 2048 .05\nstep 1 0 .05\nstep 1 2048 .05\nstep 1 2 .05\n','touch')
    assert touch[0]['mode']==1 and all(r['dy']==0 for r in touch[:6])
    assert touch[-2]['dy']==1 and touch[-1]['dart']>.25
    desktop=vm('reset 1 0 0 6 0\nstep 300 4 .05\n','remote')
    assert_safe(desktop)
    assert desktop[-1]['y']>5


def test_bounded_slow_frames_and_corner_burst(vm):
    rows=vm('reset 1 15.45 10.45 8.25 .125\nstep 100 22529 .15\nstep 300 16386 .05\n')
    assert_safe(rows)
    assert abs(rows[-1]['x'])<14 and abs(rows[-1]['y'])<9
