"""Execute the actual contact Forth with the engine dictionary and mock actors."""
import importlib.util,math
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('urchin_zfhost',ROOT/'docs/reference/swarming-poster/zfhost.py');zf=importlib.util.module_from_spec(s);s.loader.exec_module(zf);
WORDS=': tk@ read-mailbox ; : tk! write-mailbox ; : tk-dt@ 790 tk@ ; : INDEXOF_DELTA_TIME 790 ; : INDEXOF_X_POS 3009 ; : INDEXOF_Y_POS 3010 ; : INDEXOF_Z_POS 3011 ; : INDEXOF_ROTATION_B 3013 ; : INDEXOF_ROTATION_C 3014 ; : INDEXOF_X_SCALE 3040 ; : write-actor-mailbox 100 * + write-mailbox ;'
FEET=' '.join(f'{.25*math.cos(k*math.tau/8)} {.25*math.sin(k*math.tau/8)} {.017+.0014*k} {k} {k+1} uf-foot' for k in range(8))
@pytest.fixture(scope='session')
def binaries(tmp_path_factory):
 import subprocess
 folder=tmp_path_factory.mktemp('urchin-forth')
 source=ROOT/'docs/reference/swarming-poster/zf_host.c'
 paths={}
 for mode in ('float','fixed'):
  src=folder/(mode+'.c')
  text=source.read_text()
  if mode=='fixed':text=text.replace('g_mail[i] = v;', 'g_mail[i] = (float)((int)(v*65536))/65536;')
  src.write_text(text);binary=folder/mode
  subprocess.run(['cc','-O1','-I'+str(ROOT/'engine/stubs'),'-I'+str(ROOT/'engine/vendor/zforth-41db72d1/src/zforth'),str(src),str(ROOT/'engine/vendor/zforth-41db72d1/src/zforth/zforth.c'),'-lm','-o',str(binary)],check=True)
  paths[mode]=binary
 return paths

@pytest.fixture(params=['float','fixed'])
def host(request,binaries):
 zf.BIN=binaries[request.param]
 h=zf.Host();assert h.eval(WORDS)=='ok';assert h.load(ROOT/'wflevels/aquarium_tanks/urchin_motion.fth')=='ok';h.write(790,.05)
 yield h;h.close()
def tick(h,x,y):assert h.eval(f'{x} {y} .865 uf-begin '+FEET)=='ok'
def feet(h):return [h.read(840+16*k,11) for k in range(8)]
def test_stationary_and_blocked_do_not_cycle(host):
 h=host;tick(h,0,0)
 for _ in range(200):tick(h,0,0)
 assert h.read(813)==0 and all(s[4]==s[10]==0 for s in feet(h))
def test_cardinal_and_diagonal_have_equal_distance(host):
 h=host;tick(h,0,0)
 for k in range(1,301):tick(h,k*.000625,0)
 cardinal=h.read(813)
 h.write(813,0);h.write(805,0);tick(h,0,0)
 for k in range(1,301):tick(h,k*.000625/math.sqrt(2),k*.000625/math.sqrt(2))
 assert abs(h.read(813)-cardinal)/1024<2/65536
@pytest.mark.parametrize('direction',[(1,0),(0,1),(1/math.sqrt(2),-1/math.sqrt(2))])
def test_planted_pads_stay_fixed_and_stems_follow_roots(host,direction):
 h=host;previous=None;max_error=0;attached=0
 for frame in range(360):
  x,y=[frame*.000625*v for v in direction];tick(h,x,y);states=feet(h)
  if previous:
   for a,b in zip(previous,states):
    if a[4]==b[4]==0:assert a[:2]==b[:2];attached+=1
  for k in range(8):
   x0,y0,z0=h.read(3109+100*k,3);pitch,yaw=h.read(3113+100*k,2);scale=h.read(3140+100*k)
   pitch*=math.tau;yaw*=math.tau
   endpoint=(x0+.1*scale*math.cos(pitch)*math.cos(yaw),y0+.1*scale*math.cos(pitch)*math.sin(yaw),z0-.1*scale*math.sin(pitch))
   root=(x+.25*math.cos(k*math.tau/8),y+.25*math.sin(k*math.tau/8),.751)
   max_error=max(max_error,math.dist(endpoint,root))
  previous=states
 assert attached>1000 and max_error<.002
 assert sum(s[10] for s in states)>15

def test_release_settles_without_more_body_travel(host):
 h=host
 for k in range(1,77):tick(h,k*.000625,0)
 distance=h.read(813)
 for _ in range(80):tick(h,76*.000625,0)
 assert h.read(813)==distance
 assert all(s[4]==s[8]==0 for s in feet(h))

def test_reversal_stays_continuous_and_teleport_reanchors(host):
 h=host
 for k in range(60):tick(h,k*.000625,0)
 old=feet(h)
 tick(h,58*.000625,0);new=feet(h)
 assert all(math.hypot(a[0]-b[0],a[1]-b[1])<.003 for a,b in zip(old,new))
 tick(h,3,.3)
 assert h.read(806)==1 and all(s[4]==s[8]==0 for s in feet(h))
 for k,s in enumerate(feet(h)):
  assert abs(s[0]-(3+.25*math.cos(k*math.tau/8)))<2/65536
