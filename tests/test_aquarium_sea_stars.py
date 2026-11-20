"""Run the shipped crawl Forth in the engine's zForth VM, then inspect every frame."""
import ast
import csv
import io
import math
from pathlib import Path
import re
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'wflevels/aquarium_sea_stars'))
from controller import player, director, CELLS
from config import RESIDENTS

@pytest.fixture(scope='module')
def crawl(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('sea-stars-vm')
    src = (ROOT/'engine/stubs/scripting_zforth.cc').read_text()
    core = src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')]
    core = re.sub(r'//[^\n]*','',core)
    definitions = ''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"',core))
    mailbox = (ROOT/'wfsource/source/mailbox/mailbox.inc').read_text()
    constants = {f'INDEXOF_{k}':int(v) for k,v in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)',mailbox)}
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate('ABCDEFGHIJK')})
    constants.update({f'JOYSTICK_BUTTON_{k}':1<<i for i,k in enumerate(('UP','DOWN','RIGHT','LEFT'),11)})
    definitions += '\n'+''.join(f': {k} {v} ;\n' for k,v in constants.items())
    definitions += ": read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ; : read-actor-mailbox 152 sys ; : r@ ' lit , 0 , ' pickr , ; immediate\n"
    vendor = ROOT/'engine/vendor/zforth-41db72d1/src/zforth'
    binary = tmp/'vm'
    subprocess.run(['cc','-O1','-I'+str(ROOT/'engine/stubs'),'-I'+str(vendor),str(ROOT/'tests/species_vm.c'),str(vendor/'zforth.c'),'-lm','-o',str(binary)],check=True)
    (tmp/'player.fth').write_text(definitions+player())
    definitions += re.search(r'zf_eval\(&g_ctx, "(: profile-begin [^"]*)"\)',src).group(1)+'\n'
    indices = {'Player':1,'Director':2,'BlueStar':3,'cs_wide':4,**{n:i+5 for i,(n,_,_) in enumerate(RESIDENTS)}}
    (tmp/'director.fth').write_text(definitions+director(indices).removesuffix('st-director-tick\n'))
    def run(trace):
        result = subprocess.run([str(binary),str(tmp/'player.fth'),str(tmp/'director.fth'),'1','2','st-tick','st-director-tick'],input=trace,text=True,capture_output=True)
        assert result.returncode == 0, result.stderr
        keys = ['frame','x','y','z','vx','vy','vz',*range(600,751),*range(1100,1112),*range(1200,1281),*range(1000,1035),*range(780,791),*range(860,866),'part-x','part-y','part-z','part-a','part-b','part-c','camshot']
        return [dict(zip(keys,map(float,row))) for row in csv.reader(io.StringIO(result.stdout))]
    return run

def test_plane_hold(crawl):
    # Sand -> front -> right -> back -> left -> front -> sand.
    rows = crawl('reset 0 0 .8\nstep 500 4096 .0166667\nstep 420 2048 .0166667\nstep 6000 8192 .0166667\nstep 1000 4096 .0166667\n')
    assert {int(r[CELLS['surface']]) for r in rows} == {0,1,2,3,4}
    assert rows[-1][CELLS['surface']] == 0
    for r in rows:
        assert abs(r['x']) <= 5.65001 and abs(r['y']) <= 2.65001
        assert .79999 <= r['z'] <= 4.85001
        distances = [abs(r['z']-.8),abs(r['y']+2.65),abs(r['x']-5.65),abs(r['y']-2.65),abs(r['x']+5.65)]
        assert min(distances) < .001
        assert max(abs(r[k]) for k in ('vx','vy','vz')) == 0

def test_release_stops_and_resume_requires_neutral(crawl):
    rows = crawl('reset 0 0 .8\nstep 60 8192 .0166667\nstep 90 0 .0166667\nstep 1 8192 .5\nstep 60 8192 .0166667\nstep 1 0 .0166667\nstep 60 8192 .0166667\n')
    assert rows[59]['x'] > .39
    assert abs(rows[149]['x']-rows[59]['x']) < .0001
    assert abs(rows[210]['x']-rows[149]['x']) < .0001
    assert rows[-1]['x'] > rows[210]['x']+.39

def test_idle_autopilot_climbs_front(crawl):
    rows = crawl('reset 0 0 .8\nstep 3600 0 .0166667\n')
    assert any(r[CELLS['surface']] == 1 and r['z'] > 2 for r in rows)

def test_reach_does_not_repeat_while_held(crawl):
    rows = crawl('reset 0 0 .8\nstep 180 1 .0166667\n')
    assert rows[0][CELLS['reach']] > 1.9
    assert rows[-1][CELLS['reach']] == 0


def test_glass_pitch_puts_the_underside_against_the_glass():
    # The top must face into the tank (-90 deg pitch); +90 shows the dorsal skin to the camera.
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'wflevels/aquarium_sea_stars/star_director.fth').read_text()
    assert '1 - .25 * -.25' in src
