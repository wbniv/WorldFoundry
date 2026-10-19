"""Species rig, bare scene and scale/clearance contract for Asian Arowana."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
import arowana
HERE=ROOT/'wflevels/aquarium_arowana'


def test_species_geometry_and_animated_envelope():
    meshes,offsets=arowana.models()
    assert len(meshes)==10
    assert sum(sum(len(f)-2 for f in m.faces) for m in meshes) in range(6000,10001)
    assert {m.name for m in meshes}=={'ar_body','ar_tail','ar_dorsal','ar_anal','ar_pec_near','ar_pec_far','ar_pelvic_near','ar_pelvic_far','ar_barbel_near','ar_barbel_far'}
    for m,off in zip(meshes,offsets):
        assert all(abs(x+off[0])<3.70 and abs(y+off[1])<1.23 and abs(z+off[2])<1.19 for x,y,z in m.vertices)
    assert abs(max(x for x,y,z in meshes[0].vertices)-min(x for x,y,z in meshes[1].vertices)-6.5)<1e-6
    assert all(off==(0,0,0) for off in offsets)
    assert max(y for x,y,z in meshes[4].vertices)<0<min(y for x,y,z in meshes[5].vertices)
    assert max(y for x,y,z in meshes[8].vertices)<0<min(y for x,y,z in meshes[9].vertices)
    assert all(len(m.uvs)==len(m.vertices) for m in meshes)


def test_export_has_one_animal_and_bare_tank():
    mapping=json.loads((HERE/'actor-map.json').read_text())
    assert mapping['count']==1 and mapping['rows']==[] and mapping['feeding'] is None
    assert len([n for n in mapping['indices'] if n.startswith('animal-')])==10
    assert not any(any(word in n for word in ['plant','rock','goldfish','bubble','sand','pavilion']) for n in mapping['indices'])
    text=(HERE/'aquarium_arowana.lev').read_text()
    assert 'ar-rig-tick' in text and 'ar-player-tick' in text and 'swim-deform' in text
    assert (ROOT/'wflevels/aquarium_arowana-standalone.iff').read_bytes()[:4]==b'L4\x00\x00'


def test_broad_tank_configuration_and_remote_profile():
    spec=importlib.util.spec_from_file_location('ar_config',HERE/'config.py')
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    assert c.DIMENSIONS_M==(4,3,1.2) and c.WORLD_SCALE==10
    mapping=json.loads((HERE/'actor-map.json').read_text())
    player,director,values=arowana.scripts(mapping['indices'],mapping['parts'],mapping['offsets'],'remote',c)
    assert values['aq-ix']==19.77 and values['aq-iy']==14.77
    assert ': aq-remote 1.0000000' in player and 'ar-read-remote' in player
    assert 'ar-neutral fish!' in player and 'aq-dart-req fish!' in player
    assert 'ar-rig-tick ar-camera-tick' in director


def test_entire_deformed_envelope_fits_the_continuous_turn_reserve():
    import math
    meshes,_=arowana.models()
    # Bound every phase, bend sign and local fin phase independently, including
    # root idle bob/pitch. A sphere bounds arbitrary yaw; pitch/bank have limits.
    theta=math.tau*(1/12+.002)
    bank=math.tau*8/360
    for mesh in meshes:
        for (x,y,z),(across,tip) in zip(mesh.vertices,mesh.uvs):
            t=max(0,min(1,(arowana.NOSE_X-x)/arowana.TOTAL_LENGTH))
            weight=max(0,(t-.35)/.65)**2
            y_bound=abs(y)+(.192+.35)*weight+.15*tip*tip
            assert math.sqrt(x*x+y_bound*y_bound+z*z)+.03<4.25
            assert abs(x)*math.sin(theta)+y_bound*math.sin(bank)+abs(z)+.018<3.30
