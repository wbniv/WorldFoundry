"""Independent 50-barb tank: exported population, sizes, allocation and real VM."""
from pathlib import Path
import json
import math
import sys
import pytest
from test_aquarium_level import _objects,by_name,_header
from test_species_movement import vm
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium'))
import tiger_barb as TB
HERE=ROOT/'wflevels/aquarium_tiger_barbs'

def test_fifty_single_mesh_fish_and_no_marine_animals():
    objs=_objects(HERE/'aquarium_tiger_barbs.lev')
    fish=[o for o in objs if o['name'].startswith('tiger-barb-')]
    assert len(fish)==50
    assert len({o['mesh'] for o in fish})==1
    assert all(o['mesh']=='tiger_barb_refined.iff' and o['class']=='platform' and o['mass']==0 and not o['script'] for o in fish)
    assert not any(o['name'].startswith(('clownfish','anemone')) or o['name']=='rock' for o in objs)
    script=by_name(objs,'Director')['script']
    assert script.rstrip().endswith('barb-player-tick\naq-camera-tick\nsd-tick')
    assert ': aq-sway-' not in script and ': aq-sway-b ' not in script
    assert ': fish-off 0 ;' in script and '1037 read-mailbox' not in script

def test_size_range_and_large_fish_wall_margin():
    mapping=json.loads((HERE/'actor-map.json').read_text())
    sizes=mapping['resident_lengths_m']
    assert mapping['fish_count']==50 and len(sizes)==49
    assert min(sizes)==.25 and max(sizes)==.70 and len(set(sizes))==16
    assert sum(.37<=s<=.58 for s in sizes)>len(sizes)/2
    maximum_radius=max(math.sqrt(sum(x*x for x in v)) for v in TB.geometry(refined=True)[0])
    assert (maximum_radius+.04)*max(sizes)/TB.LENGTH_M < .85*TB.LENGTH_M
    # Exported selector sizes match the planned population rather than old 29 modulo.
    script=by_name(_objects(HERE/'aquarium_tiger_barbs.lev'),'Director')['script']
    assert 'me sd-size-scale dup' in script
    assert '11 * 29 mod 28 /' not in script

def test_mailboxes_and_exported_actor_lookup_are_disjoint():
    objs=_objects(HERE/'aquarium_tiger_barbs.lev');script=by_name(objs,'Director')['script']
    values=_header(script);ranges=TB.mailbox_ranges(49)
    spans=sorted([(600,639),(700,719),(740,759)]+list(ranges.values()))
    assert all(a[1]<b[0] for a,b in zip(spans,spans[1:]))
    assert spans[-1][1]<1901
    assert ranges['state']==(800,1499)
    assert values['sch-n']==50 and values['sd-budget']==5
    assert values['sch-par']==1500 and values['sch-scr']==1522
    for k in range(1,50):
        actor=next(i+1 for i,o in enumerate(objs) if o['name']==f'tiger-barb-{k}')
        assert f'{actor} {1580+k-1} write-mailbox' in script

def test_fifty_fish_scripts_execute_and_player_rig_follows(vm):
    rows=vm('tiger_barbs','reset -1.6 0 2.4\nset 650 10\nstep 50 8192 .025\nstep 30 1 .025\nstep 60 16384 .025\nstep 20 0 .025\n')
    assert rows[49]['x']>rows[0]['x']+.5
    assert all(math.isfinite(v) for r in rows for v in r.values())
    assert all(abs(r['part-x']-r['x'])<1e-5 and abs(r['part-z']-r['z'])<1e-5 for r in rows)
    assert all(abs(r['x'])<6 and abs(r['y'])<1.525 and .635<r['z']<4.826 for r in rows)
