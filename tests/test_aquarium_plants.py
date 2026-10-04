"""Geometry and packaging contracts for the Planted Tank and its sea urchin."""
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
from planting import planting, placements
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
    assert len(entries)==8
    assert entries[5]=='level aquarium_plants-standalone.iff | Planted Tank'
    assert entries[0].startswith('level aquarium-standalone.iff | ')


def test_dense_grouping_and_real_mesh_limits():
    import struct
    here=ROOT/'wflevels/aquarium_plants'
    mapping=json.loads((here/'actor-map.json').read_text())
    groups=[name for name in mapping['indices'] if name.startswith('plant_')]
    assert len(groups)==8 and len(mapping['indices'])==38
    text=(here/'aquarium_plants.lev').read_text()
    assert all(f'{name}.iff' in text for name in groups)
    total=0
    for name in groups:
        data=(here/(name+'.iff')).read_bytes();chunks={};offset=8
        while offset<len(data):
            tag=data[offset:offset+4];size=struct.unpack_from('<I',data,offset+4)[0]
            chunks[tag]=data[offset+8:offset+8+size];offset+=8+(size+3)//4*4
        flags,colour=struct.unpack_from('<iI',chunks[b'MATL'])
        assert flags&2 and flags&4  # Opaque texture mapped, prelit; one shared atlas.
        assert chunks[b'MATL'][8:].split(b'\0',1)[0]==b'leaf_surfaces.tga'
        vertices=[struct.unpack_from('<iii',chunks[b'VRTX'],i+12) for i in range(0,len(chunks[b'VRTX']),24)]
        triangles=list(struct.iter_unpack('<hhhh',chunks[b'FACE']))
        assert 0<len(vertices)<32000 and 0<len(triangles)<32000
        for a,b,c,material in triangles:
            assert all(0<=i<len(vertices) for i in (a,b,c))
            assert len({a,b,c})==3
            u=[vertices[b][j]-vertices[a][j] for j in range(3)]
            v=[vertices[c][j]-vertices[a][j] for j in range(3)]
            assert any((u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]))
        total+=len(triangles)
    assert total==16  # Eight bounded runtime geometry placeholders.
    assert "plant-register" in text and "plant-step" in text
    wrapper=(here/'aquarium_plants-standalone.iff.txt').read_text()
    assert "'SLOT' 1l" in wrapper and "'ROOM' 24000000l" in wrapper


def test_density_and_detail_share_deterministic_population():
    from collections import Counter
    points=placements()
    assert points==placements()
    assert Counter(p['kind'] for p in points)==dict(broad=64,stems=128,carpet=192)
    assert len(planting(.635,'density'))==len(planting(.635,'detailed'))==8
    # A dense central canopy replaces the former empty central strip.
    center=[p for p in points if p['kind']=='stems' and abs(p['x'])<1]
    assert len(center)>=16 and min(p['height'] for p in center)>3
    # Starting body/feet remain clear of foreground roots.
    assert not any(abs(p['x'])<.65 and p['y']<-.55 for p in points if p['kind']=='carpet')
