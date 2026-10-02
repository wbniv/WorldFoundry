"""Geometry and packaging contracts for the Planted Tank and its sea urchin."""
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
from planting import planting
from urchin import urchin

def test_foliage_and_spines_survive_fixed_point_triangle_normals():
    for mesh in [*planting(.635),urchin()]:
        for face in mesh.faces:
            for j in range(1,len(face)-1):
                a,b,c=[mesh.vertices[i] for i in (face[0],face[j],face[j+1])]
                u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
                cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
                assert math.sqrt(sum(x*x for x in cross))>8/65536,(mesh.name,face)

def test_one_visible_urchin_no_fish_or_resident_rig():
    here=ROOT/'wflevels/aquarium_plants';mapping=json.loads((here/'actor-map.json').read_text())
    assert mapping['count']==1 and mapping['animal']=='sea_urchin'
    assert mapping['rows']==[] and mapping['parts']==[]
    assert mapping['title']=='Planted Tank'
    assert not any(n.startswith('animal-') for n in mapping['indices'])
    text=(here/'aquarium_plants.lev').read_text()
    assert 'sea_urchin.iff' in text
    assert 'tk-pose' not in text and 'tk-gait' not in text
    assert not (here/'player_hull.iff').exists()
    for mesh in planting(.635):
        assert min(v[2] for v in mesh.vertices)>=.63
        assert all(abs(v[0])<5.969 and abs(v[1])<1.524 and v[2]<4.826 for v in mesh.vertices)
    mesh=urchin()
    for x,y,z in mesh.vertices:
        assert mapping['bottom']+z>=.635-1e-7
        assert abs(x)+mapping['limits'][0]<5.969
        assert abs(y)+mapping['limits'][1]<1.524
    assert (ROOT/'wflevels/aquarium_plants-standalone.iff').read_bytes()[:4]==b'L4\x00\x00'

def test_menu_appends_planted_tank_without_changing_existing_indices():
    entries=[s for s in (ROOT/'wflevels/aquarium-menu.manifest').read_text().splitlines() if s.startswith('level ')]
    assert len(entries)==7
    assert entries[5]=='level aquarium_plants-standalone.iff | Planted Tank'
    assert entries[0].startswith('level aquarium-standalone.iff | ')
