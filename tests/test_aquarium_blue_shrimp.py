"""Independent Blue Shrimp content guards; no dependency on the first aquarium.

Runtime controls/camera/animation: wflevels/aquarium_blue_shrimp/run_checks.py.
"""
import importlib.util
import itertools
import json
import math
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parent.parent
LEVEL = ROOT/'wflevels/aquarium_blue_shrimp'


def load(name):
    spec = importlib.util.spec_from_file_location('blue_shrimp_'+name, LEVEL/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C, G = load('constants'), load('geometry')


def test_mesh_triangles_clear_engine_normalization_limit():
    # vector3.hpi normalizes face cross products only above Scalar(0,4).
    # Test the actual fan triangles, with extra room for 16.16 quantization.
    for mesh in G.shrimp_meshes():
        for face in mesh.faces:
            a = mesh.vertices[face[0]]
            for i in range(1,len(face)-1):
                b,c = mesh.vertices[face[i]],mesh.vertices[face[i+1]]
                u,v = [b[j]-a[j] for j in range(3)],[c[j]-a[j] for j in range(3)]
                cross = [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
                assert math.sqrt(sum(x*x for x in cross)) > 2*4/65536, mesh.name


def test_turned_player_rig_fits_wall_margins():
    meshes = G.shrimp_meshes()
    for heading in range(72):
        a=math.tau*heading/72
        for mesh,off in zip(meshes,G.OFFSETS):
            for v in mesh.vertices:
                x,y,z = [v[j]+off[j] for j in range(3)]
                wx,wy = x*math.cos(a)-y*math.sin(a), x*math.sin(a)+y*math.cos(a)
                assert abs(wx)+C.LIMIT_X < C.HX-C.WALL
                assert abs(wy)+C.LIMIT_Y < C.HY-C.WALL
                assert z+C.WATER-.5-C.HULL_LIFT < C.WATER
                assert z >= -.015  # feet rest on substrate, never deep in it


def test_resident_routes_stay_in_tank_and_do_not_intersect_boulders():
    for seconds in range(240):
        for row in C.residents():
            (x,y,z),_ = C.route_at(row,seconds)
            assert abs(x)+.7*row['size'] < C.HX-C.WALL
            assert abs(y)+.7*row['size'] < C.HY-C.WALL
            assert C.SAND <= z < C.WATER-.4
            if z==C.SAND:
                for rx,ry,half_x,half_y,h in C.ROCKS:
                    # Crawlers' feet, not antennae, need clear substrate.
                    assert abs(x-rx)>=half_x+.30*row['size'] or abs(y-ry)>=half_y+.30*row['size']


def test_authored_lanes_have_spacing_and_varied_states():
    minimum = 100
    moving_counts = []
    for seconds in range(240):
        states = [C.route_at(r,seconds) for r in C.residents()]
        minimum=min(minimum,*(math.dist(a[0],b[0]) for a,b in itertools.combinations(states,2)))
        moving_counts.append(sum(moving for _,moving in states))
    assert minimum > .45, minimum
    assert min(moving_counts)<max(moving_counts)
    assert all(0<count<23 for count in moving_counts)


def test_mailboxes_and_build_count_limits():
    assert len(C.MAILBOX)==len(set(C.MAILBOX.values()))
    assert max(C.MAILBOX.values())<700
    assert not set(C.MAILBOX.values()) & set(range(650,655))
    assert C.TABLE+23*C.STRIDE<1400
    assert 1400+23<1900
    assert len(C.residents(0))==0 and len(C.residents())==23
    with pytest.raises(ValueError):
        C.residents(24)


@pytest.fixture(scope='module')
def exported():
    path=LEVEL/(C.LEVEL+'.lev')
    assert path.exists(), 'run bash wflevels/aquarium_blue_shrimp/build.sh'
    chunks={}
    for chunk in path.read_text().split("{ 'OBJ'")[1:]:
        name=re.search(r"\{ 'NAME' \"([^\"]+)\"",chunk).group(1)
        chunks[name]=chunk
    return chunks


def test_exported_population_shares_five_meshes(exported):
    mapping=json.loads((LEVEL/'actor-map.json').read_text())
    names=list(exported)
    assert mapping['count']==24
    assert len([n for n in names if n.startswith('shrimp-')])==24*5
    for k in range(24):
        for part in G.PARTS:
            name=f'shrimp-{k:02d}-{part}'
            chunk=exported[name]
            assert '"Class Name" } { \'DATA\' "platform"' in chunk
            assert '"Mass" } { \'DATA\' 0.000000' in chunk
            assert ('shrimp_'+part.replace('-','_')+'.iff') in chunk
            assert mapping['indices'][name]==names.index(name)+1


def test_invisible_player_has_neutral_physics_and_script(exported):
    player=exported['Player']
    assert '"Visibility Mailbox" } { \'DATA\' 0l' in player
    assert '"Falling Acceleration" } { \'DATA\' 0.000000' in player
    assert '"Mobility" } { \'STR\' "Physics"' in player
    assert 'sh-player-tick' in player
    assert 'sh-director-tick' in exported['Director']
    assert 'sh-cam-close' in exported['Director']
    box_data=re.search(r'"Global Bounding Box".*?\{ \'DATA\' (.*?)//',player).group(1)
    box=[float(x) for x in re.findall(r'(-?\d+\.\d+)\(1\.15\.16\)',box_data)]
    assert len(box)==6
    for j in range(3):
        assert box[j]==pytest.approx(-box[j+3])
        assert box[j+3]-box[j]>=.25  # levcomp must not shift a thin Player box


def test_generator_does_not_load_or_write_the_other_aquarium():
    generator=(LEVEL/'blender_create_aquarium_blue_shrimp.py').read_text()
    builder=(LEVEL/'build.sh').read_text()
    assert 'aquarium/blender' not in generator+builder
    assert 'import clownfish' not in generator
    assert 'aquarium-cd.iff' not in generator+builder
