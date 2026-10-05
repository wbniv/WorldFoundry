"""Exercise eight sparse basal pivots with actual Forth and quantized mailboxes."""
import math,json
from pathlib import Path
import pytest
from test_urchin_motion import host,binaries,tick,ROOT
from urchin import PIVOT_SPINES,spine_specs,urchin,spine_mesh,tube_foot
SPECS=[spine_specs()[index] for index in PIVOT_SPINES]
CALLS=' '.join(f"{s['root'][0]} {s['root'][1]} {s['root'][2]} {-math.asin(s['direction'][2])/math.tau} {math.atan2(s['direction'][1],s['direction'][0])/math.tau} {4.1+k*.41} {1 if k%2==0 else -1} {k} {k+11} us-spine" for k,s in enumerate(SPECS))
@pytest.fixture
def spine_host(host):
 assert host.load(ROOT/'wflevels/aquarium_tanks/urchin_spines.fth')=='ok'
 return host
def step(h,x=0,y=0):
 tick(h,x,y);assert h.eval(CALLS)=='ok'
def angles(h,k):return h.read(3013+100*(k+11),2)
def test_sparse_holds_bounded_rigid_pivots_and_clearance(spine_host):
 h=spine_host;previous=None;holds=moving=0;moving_counts=[]
 for frame in range(500):
  x=frame*.000625;step(h,x,0);count=0;current=[]
  for k,s in enumerate(SPECS):
   base=h.read(3009+100*(k+11),3);b,c=angles(h,k);current.append((b,c))
   assert math.dist(base,[x+s['root'][0],s['root'][1],.865+s['root'][2]])<2/65536
   rest=-math.asin(s['direction'][2])/math.tau
   assert abs(b-rest)<.022 and abs(c-math.atan2(s['direction'][1],s['direction'][0])/math.tau)<.010
   # Constant-length local +X shaft rotates about the attached base.
   tip=[base[0]+s['length']*math.cos(b*math.tau)*math.cos(c*math.tau),base[1]+s['length']*math.cos(b*math.tau)*math.sin(c*math.tau),base[2]-s['length']*math.sin(b*math.tau)]
   assert abs(math.dist(base,tip)-s['length'])<1e-12 and min(base[2],tip[2])>.635+.03
   if previous:
    delta=max(abs(b-previous[k][0]),abs(c-previous[k][1]));assert delta<.004
    if delta<1/65536:holds+=1
    else:moving+=1;count+=1
  moving_counts.append(count);previous=current
 assert holds>2000 and moving>400
 assert any(0<n<8 for n in moving_counts) and max(moving_counts)<8

def test_pause_gap_does_not_catch_up_and_teleport_resets(spine_host):
 h=spine_host
 for _ in range(100):step(h)
 before=[angles(h,k) for k in range(8)];h.write(790,8);step(h)
 assert before==[angles(h,k) for k in range(8)]
 h.write(790,.05);step(h,3,.4)
 for k,s in enumerate(SPECS):
  b,c=angles(h,k)
  assert abs(b+math.asin(s['direction'][2])/math.tau)<2/65536
  assert abs(c-math.atan2(s['direction'][1],s['direction'][0])/math.tau)<2/65536

def test_generated_binding_ownership_and_no_duplicated_geometry():
 mapping=json.loads((ROOT/'wflevels/aquarium_plants/actor-map.json').read_text());bind=mapping['urchin_spines']
 assert len(bind['spines'])==8 and len({s['actor'] for s in bind['spines']})==8
 assert set(s['source_index'] for s in bind['spines'])==set(PIVOT_SPINES)
 ranges=[mapping['urchin_contacts']['scratch'],mapping['urchin_contacts']['slots'],bind['slots'],bind['scratch']]
 occupied=set()
 for a,b in ranges:
  r=set(range(a,b+1));assert not occupied&r;occupied|=r
 triangles=lambda m:sum(len(f)-2 for f in m.faces)
 assert triangles(urchin())+sum(triangles(spine_mesh(i)) for i in PIVOT_SPINES)==triangles(urchin(articulated=False))
 assert triangles(urchin())+8*triangles(tube_foot())+sum(triangles(spine_mesh(i)) for i in PIVOT_SPINES)==3540
 assert len(mapping['indices'])==46
