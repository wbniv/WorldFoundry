"""Root attachment, closed membranes, export weights and animated tank clearance."""
import collections
import math
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'wflevels/aquarium_tanks'),str(ROOT/'wflevels/aquarium_betta')]
from detailed_model import detailed_models

def test_native_fin_rest_pose_root_attachment_delay_and_no_accumulation(tmp_path):
    source=tmp_path/'fin.cc'
    source.write_text(r'''
#include "wfsource/source/renderassets/fin_deform.h"
#include <cassert>
int main() {
    using wf_render::FinWaveWeight;
    auto root=FinWaveWeight::make(.2f,.1f,.3f,.4f,0);
    auto tip=FinWaveWeight::make(-.8f,.02f,.4f,.4f,1);
    tip.rootX=.2f;tip.rootZ=.1f;
    auto mid=FinWaveWeight::make(-.4f,.01f,.3f,.4f,.5f);
    for(int i=0;i<10000;i++) {
        float s=std::sin(i*.02f),c=std::cos(i*.02f);
        assert(root.bentY(s,c,.2f)==.1f && root.sweptX(.1f)==.2f && root.bentZ(s,c,.2f)==.3f);
        assert(std::abs(tip.bentY(s,c,.1f)-.02f)<=.100001f);
        assert(std::abs(mid.bentY(s,c,.1f)-.01f)<=.025001f);
        assert(tip.bentY(s,c,0)==.02f && tip.sweptX(0)==-.8f);
    }
    assert(tip.sinDelay!=mid.sinDelay);
    assert(std::abs(tip.sweptX(0,.7f)+.5f)<.00001f);
    assert(std::abs(tip.bentZ(0,1,0,.7f)-.31f)<.00001f);
    auto other=FinWaveWeight::make(-.8f,.02f,.4f,.8f,1);
    assert(other.sinDelay!=tip.sinDelay);
}
''')
    binary=tmp_path/'fin'
    subprocess.run(['c++','-std=c++11','-I',str(ROOT),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

def test_eight_groups_closed_oriented_fin_surfaces_and_substantial_detail():
    meshes,offsets=detailed_models()
    assert len(meshes)==8 and offsets==[(0,0,0)]*8
    assert 3000<=sum(sum(len(f)-2 for f in m.faces) for m in meshes)<=5000
    for m in meshes[1:]:
        edges=collections.defaultdict(list)
        for f in m.faces:
            for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((a,b)))].append((a,b))
        assert all(len(p)==2 and p[0]==p[1][::-1] for p in edges.values()),m.name
        assert all(0<=u<=1 and 0<=v<=1 for u,v in m.uvs)
        assert any(v==0 for u,v in m.uvs) and any(v==1 for u,v in m.uvs)

def test_deformed_quantised_faces_and_full_heading_clearance():
    meshes,_=detailed_models()
    for phase in range(24):
        angle=phase*math.tau/12
        for m in meshes:
            vertices=[]
            roots={u:(x,z) for (x,y,z),(u,v) in zip(m.vertices,getattr(m,'uvs',[])) if v==0}
            spread=.60 if phase<12 else 1.03
            if m.name=='dorsal':spread=spread*.85+.15
            elif m.name=='anal':spread=spread*.75+.25
            elif 'pectoral' in m.name:spread=.85
            elif 'pelvic' in m.name:spread=1
            amp={'tail':.105,'dorsal':.060,'anal':.072}.get(m.name,.044 if 'pectoral' in m.name else .068)
            for i,(x,y,z) in enumerate(m.vertices):
                if hasattr(m,'uvs'):
                    u,v=m.uvs[i];delay=2.4*v+3*math.pi*u
                    sweep={'tail':.075,'dorsal':.015,'anal':.027,'near_pectoral':.023,'far_pectoral':.023}.get(m.name,.045)
                    rx,rz=roots[u];x=rx+(x-rx)*spread-sweep*v*v
                    y+=amp*v*v*math.sin(angle-delay);z=rz+(z-rz)*spread+amp*.25*v*v*math.cos(angle-1.3*v-1.1*u)
                vertices.append(tuple(round(t*65536)/65536 for t in (x,y,z)))
            for f in m.faces:
                for i in range(1,len(f)-1):
                    a,b,c=[vertices[k] for k in (f[0],f[i],f[i+1])]
                    p=[b[j]-a[j] for j in range(3)];q=[c[j]-a[j] for j in range(3)]
                    cross=[p[(j+1)%3]*q[(j+2)%3]-p[(j+2)%3]*q[(j+1)%3] for j in range(3)]
                    assert math.sqrt(sum(t*t for t in cross))>4/65536,(m.name,f)
            # Horizontal rotation maximum is radial extent; covers every yaw.
            assert max(math.hypot(x,y) for x,y,z in vertices)+4.70<6.096-.127
            assert max(math.hypot(x,y) for x,y,z in vertices)+.27<1.651-.127
            assert min(z for x,y,z in vertices)+1.36>.635
            assert max(z for x,y,z in vertices)+4.08<4.826

def test_exported_fin_weights_survive_and_parts_have_no_physics():
    text=(ROOT/'wflevels/aquarium_betta/aquarium_betta.lev').read_text()
    for m in detailed_models()[0][1:]:
        data=(ROOT/'wflevels/aquarium_betta'/(m.name+'.iff')).read_bytes()
        start=data.index(b'VRTX');size=struct.unpack_from('<I',data,start+4)[0]
        uv=[struct.unpack_from('<ii',data,i) for i in range(start+8,start+8+size,24)]
        assert min(v for u,v in uv)==0 and max(v for u,v in uv)==65536
        start=text.index('"animal-00-'+m.name+'"');end=text.find("{ 'OBJ'",start)
        assert 'Anchored' in text[start:end] and 'Physics' not in text[start:end]
    assert 'fin-deform' in text and 'bf-motion' in text
