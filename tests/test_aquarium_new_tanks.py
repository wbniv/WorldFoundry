"""Export/geometry safety for the independently built Betta, Jellyfish and Lionfish."""
import importlib.util
import json
import math
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
COMMON=ROOT/'wflevels/aquarium_tanks'
sys.path.insert(0,str(COMMON))
from models import models

KINDS=['betta','jellyfish','lionfish']


def config(kind):
    p=ROOT/'wflevels'/('aquarium_'+kind)/'config.py'
    spec=importlib.util.spec_from_file_location('config_'+kind,p)
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    return c


@pytest.mark.parametrize('kind',KINDS)
def test_export_triangle_area_survives_fixed_point_normals(kind):
    meshes,_=models(kind)
    for mesh in meshes:
        for f in mesh.faces:
            for i in range(1,len(f)-1):
                a,b,c=[mesh.vertices[j] for j in (f[0],f[i],f[i+1])]
                u=[b[j]-a[j] for j in range(3)];v=[c[j]-a[j] for j in range(3)]
                cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
                assert math.sqrt(sum(t*t for t in cross))>8/65536,(kind,mesh.name,f)


@pytest.mark.parametrize('kind',KINDS)
def test_complete_animated_player_silhouette_fits_at_all_boundaries(kind):
    c=config(kind)
    mapping=json.loads((ROOT/'wflevels'/('aquarium_'+kind)/'actor-map.json').read_text())
    meshes,offsets=models(kind)
    for phase in range(12):
        gait=math.sin(phase*math.tau/12)
        for heading in range(72):
            yaw=heading*math.tau/72
            for j,(mesh,off) in enumerate(zip(meshes,offsets)):
                a=b=0;part_yaw=yaw
                if kind=='betta':
                    if j==1:part_yaw+=gait*.045*math.tau
                    if j in (2,3):a=gait*.018*math.tau*(1 if j==2 else -1)
                elif kind=='lionfish':
                    if j==1:part_yaw+=gait*.020*math.tau
                    if j in (2,3):a=gait*.018*math.tau*(1 if j==2 else -1)
                else:
                    if j==1:a=math.sin(phase*math.tau/12-.12*math.tau)*.018*math.tau;b=math.cos(phase*math.tau/12-.17*math.tau)*.012*math.tau
                    if j==2:a=gait*.008*math.tau
                for vx,vy,vz in mesh.vertices:
                    if kind=='jellyfish' and j==0:vx*=.9+gait*.10;vy*=.9+gait*.10;vz*=1+gait*.23
                    elif kind=='lionfish' and j==0:vy*=1+gait*.022
                    # Conservative Euler bound: exact local X/Y/Z rotations followed by heading.
                    vy,vz=vy*math.cos(a)-vz*math.sin(a),vy*math.sin(a)+vz*math.cos(a)
                    vx,vz=vx*math.cos(b)+vz*math.sin(b),-vx*math.sin(b)+vz*math.cos(b)
                    x=vx*math.cos(part_yaw)-vy*math.sin(part_yaw)+off[0]*math.cos(yaw)-off[1]*math.sin(yaw)
                    y=vx*math.sin(part_yaw)+vy*math.cos(part_yaw)+off[0]*math.sin(yaw)+off[1]*math.cos(yaw)
                    z=vz+off[2]
                    assert mapping['limits'][0]+abs(x)<6.096-.127,(kind,j,'x',x)
                    assert mapping['limits'][1]+abs(y)<1.651-.127,(kind,j,'y',y)
                    assert c.BOTTOM+z>.635,(kind,j,'bottom',z)
                    assert c.TOP+z<4.826,(kind,j,'top',z)


@pytest.mark.parametrize('kind',KINDS)
def test_export_population_anchored_parts_and_mailbox_limits(kind):
    here=ROOT/'wflevels'/('aquarium_'+kind)
    c=config(kind);mapping=json.loads((here/'actor-map.json').read_text())
    assert mapping['count']==c.COUNT
    names=[n for n in mapping['indices'] if n.startswith('animal-')]
    assert len(names)==c.COUNT*len(mapping['parts'])
    assert len(set(mapping['indices'].values()))==len(mapping['indices'])
    assert max(mapping['mailboxes'].values())<650
    assert 800+12*(c.COUNT-1)<1900
    text=(here/('aquarium_'+kind+'.lev')).read_text()
    # Export invariants: only player has Physics mobility; decorative parts are anchored platforms.
    for name in names:
        start=text.index('"'+name+'"')
        block=text[start:text.find("{ 'OBJ'",start+len(name)) if "{ 'OBJ'" in text[start+len(name):] else len(text)]
        assert "Anchored" in block
    assert 'tk-director-tick' in text and 'tk-player-tick' in text
    assert (ROOT/'wflevels'/('aquarium_'+kind+'-standalone.iff')).read_bytes()[:4]==b'L4\x00\x00'


def test_new_builds_do_not_write_active_level_or_app_bundle():
    generator=(COMMON/'generate.py').read_text()
    assert "wflevels/aquarium/" not in generator
    for kind in KINDS:
        s=(ROOT/'wflevels'/('aquarium_'+kind)/'build.sh').read_text()
        assert 'build-cd-iff-aquarium' not in s
        assert 'aquarium-cd.iff' not in s


def test_siam_pavilion_architecture_has_safe_triangles_and_a_surface_base():
    from temple import pavilion
    m=pavilion()
    assert min(v[2] for v in m.vertices)==0
    assert max(v[2] for v in m.vertices)>2
    for f in m.faces:
        for i in range(1,len(f)-1):
            a,b,c=[m.vertices[j] for j in (f[0],f[i],f[i+1])]
            u=[b[j]-a[j] for j in range(3)];v=[c[j]-a[j] for j in range(3)]
            cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            assert math.sqrt(sum(t*t for t in cross))>8/65536
    mapping=json.loads((ROOT/'wflevels/aquarium_betta/actor-map.json').read_text())
    assert 'siam-pavilion' in mapping['indices']
    assert all('statue' not in n and 'buddha' not in n for n in mapping['indices'])
