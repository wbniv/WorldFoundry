"""Production single-mesh pose, exported rig metadata and actor reduction."""
from pathlib import Path
import subprocess,struct,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
from lionfish_model import geometry,REGIONS

def test_selective_pose_fixed_roots_independent_states_and_rest(tmp_path):
    source=tmp_path/'rig.cc'
    source.write_text(r'''
#include "renderassets/lionfish_deform.h"
#include <cassert>
int main() {
 using namespace wf_render;
 LionRest root{.27f,-.15f,-.04f},tip{-.4f,-.8f,-.3f},eye{.43f,-.2f,.06f},jaw{.6f,0,-.05f};
 LionRig r{PectoralLeft,0,.27f,-.15f,-.04f},t=r;t.weight=1;
 LionRig skull{Head,.55f,.34f,0,-.035f},j{Jaw,1,.34f,0,-.035f};
 float x,y,z;
 for(int k=0;k<10000;k++) {
  lionPose(root,r,k*.013f,1,.7f,1,x,y,z);
  assert(x==root.x&&y==root.y&&z==root.z);
  lionPose(eye,skull,k*.013f,1,1,0,x,y,z);
  assert(x==eye.x&&y==eye.y&&z==eye.z);
  lionPose(tip,t,k*.013f,1,-1,0,x,y,z);
  assert(std::isfinite(x)&&std::isfinite(y)&&std::isfinite(z));
  assert(std::abs(y-tip.y)<.36f);
 }
 lionPose(jaw,j,0,0,0,1,x,y,z);assert(z<jaw.z&&x>jaw.x);
 lionPose(jaw,j,0,0,0,0,x,y,z);assert(x==jaw.x&&y==jaw.y&&z==jaw.z);
 assert(jaw.x==.6f&&eye.z==.06f); // immutable rest data
}
''')
    binary=tmp_path/'rig'
    subprocess.run(['c++','-std=c++11','-I'+str(ROOT/'wfsource/source'),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

def test_exported_weights_follow_positions_and_uvs():
    b=(ROOT/'wflevels/aquarium_lionfish/lionfish.iff').read_bytes()
    chunks={};offset=8
    while offset<len(b):
        tag=b[offset:offset+4].decode();n=struct.unpack_from('<I',b,offset+4)[0]
        chunks[tag]=b[offset+8:offset+8+n];offset+=8+(n+3)//4*4
    version,n=struct.unpack_from('<II',chunks['LRIG'])
    assert version==1 and n==len(chunks['VRTX'])//24
    assert len(chunks['LRIG'])==8+n*20
    m=geometry()
    def fixed(v):return tuple(round(k*65536) for k in v)
    source={fixed((*p,*uv,REGIONS.index(r),w)) for p,uv,r,w in zip(m.vertices,m.uvs,m.regions,m.weights)}
    for i in range(n):
        u,v,color,x,y,z=struct.unpack_from('<iiIiii',chunks['VRTX'],i*24)
        region,weight,px,py,pz=struct.unpack_from('<Iiiii',chunks['LRIG'],8+i*20)
        assert 0<=region<10 and 0<=weight<=65536
        # VRTX truncates fixed values; metadata rounds. Blender stores float32.
        assert any(all(abs(a-b)<=1 for a,b in zip((x,y,z,u,v,region*65536,weight),record)) for record in source)
    mats=chunks['MATL'];flags=[struct.unpack_from('<I',mats,i)[0] for i in range(0,len(mats),264)]
    assert sum(bool(f&64) for f in flags)==2
    opac=struct.unpack('<'+'I'*(len(chunks['OPAC'])//4),chunks['OPAC'])
    assert round(.55*65536) in opac
    mapping=json.loads((ROOT/'wflevels/aquarium_lionfish/actor-map.json').read_text())
    assert len([n for n in mapping['indices'] if n.startswith('animal-')])==2

def test_complete_native_rig_fits_tank_glass(tmp_path):
    m=geometry()
    rows=[]
    for p,r,w in zip(m.vertices,m.regions,m.weights):
        pivot=(.27,-.15 if r.endswith('left') else .15,-.04) if r.startswith('pectoral') else (.34,0,-.035) if r in ('head','jaw') else (-.51,0,0) if r=='tail' else (p[0]+.14*w,0,.22) if r=='spines' else p
        rows.append('{'+','.join(str(v)+'f' if '.' in str(v) else str(v)+'.f' for v in (*p,w,*pivot))+','+str(REGIONS.index(r))+'}')
    source=tmp_path/'bounds.cc'
    source.write_text('''#include "renderassets/lionfish_deform.h"
#include <cassert>
struct Point {float x,y,z,w,px,py,pz;unsigned region;};
Point points[]={'''+','.join(rows)+'''};
int main(){using namespace wf_render;
 for(int phase=0;phase<8;++phase)for(int drive=0;drive<2;++drive)
 for(int turn=-1;turn<=1;++turn)for(int gape=0;gape<2;++gape)
 for(const Point& p:points){float x,y,z;
  lionPose({p.x,p.y,p.z},{p.region,p.w,p.px,p.py,p.pz},phase/8.f,drive,turn,gape,x,y,z);
  for(int yaw=0;yaw<24;++yaw)for(int pitch=-1;pitch<=1;++pitch)for(int roll=-1;roll<=1;roll+=2){
   const float a=roll*.012f*6.2831853f,b=pitch*.0833333f*6.2831853f,c=yaw/24.f*6.2831853f;
   float ry=y*std::cos(a)-z*std::sin(a),rz=y*std::sin(a)+z*std::cos(a);
   float rx=x*std::cos(b)+rz*std::sin(b);rz=-x*std::sin(b)+rz*std::cos(b);
   float wx=rx*std::cos(c)-ry*std::sin(c),wy=rx*std::sin(c)+ry*std::cos(c);
   assert(4.7f+std::abs(wx)<6.096f-.127f);
   assert(.27f+std::abs(wy)<1.651f-.127f);
   assert(1.68f+rz>.635f && 3.75f+rz<4.826f);
  }
 }
}''')
    binary=tmp_path/'bounds'
    subprocess.run(['c++','-O2','-std=c++11','-I'+str(ROOT/'wfsource/source'),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
