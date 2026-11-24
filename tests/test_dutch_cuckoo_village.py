"""Exercise the shipped director in the engine's zForth interpreter, including clock jumps."""
import json
import sys
from unittest.mock import patch
from pathlib import Path

import pytest
import level_modules

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'wflevels/dutch_cuckoo_village'


def test_tulpenkade_director(tmp_path):
    # The existing clock VM harness imports several levels by unqualified name.
    with patch.dict(sys.modules), patch.object(sys, "path", list(sys.path)), pytest.MonkeyPatch.context() as monkeypatch:
        check_director(tmp_path, monkeypatch)


def check_director(tmp_path, monkeypatch):
    import verify_cuckoo_village_forth as village_vm
    monkeypatch.setitem(sys.modules, 'forth', village_vm.forth)
    monkeypatch.setitem(sys.modules, 'timeline', village_vm.tl)
    director = level_modules.load('dutch_cuckoo_village', 'director')
    ix = json.loads((HERE / 'actor-map.json').read_text())['indices']
    fields = {'Camera motion': 129, 'Window lights': 130}
    vm = village_vm.mm

    class Dutch:
        @staticmethod
        def default_indices():
            return ix

        @staticmethod
        def definitions(indices):
            return director.script(indices, fields).rsplit('quay-tick', 1)[0]

    monkeypatch.setattr(vm, 'forth', Dutch)
    monkeypatch.setattr(vm, 'HOST', village_vm.HOST.replace('eval("cv-tick")', 'eval("quay-tick")'))
    monkeypatch.setattr(vm, 'CONSTANTS', village_vm.CONSTANTS)
    ids, _ = vm.build(tmp_path)
    with (tmp_path / 'bootstrap.fth').open('a') as f:
        f.write('\n: property@ 178 sys ;\n')
    host = vm.Host(tmp_path, ids)
    try:
        def sample(hour, minute, second):
            err, before, after, writes = host.frame(hour*3600 + minute*60 + second)
            assert (err, before, after) == (0, 0, 0)
            return {(name, axis): writes[index, ids[axis]]
                    for name, index in ix.items() for axis in ('X_POS','Y_POS','Z_POS','ROTATION_A','ROTATION_B')
                    if (index, ids[axis]) in writes}

        def cell(index):
            host.proc.stdin.write(f'R {index}\n')
            host.proc.stdin.flush()
            return float(host.proc.stdout.readline().split()[-1])

        for hour, start, end in ((10,-9.45,3.75),(11,3.75,-9.45),(0,-9.45,3.75)):
            for sec, lift in ((24,0),(0,0),(2,.108),(4,.216),(10,.216),(16,.216),(21,0)):
                pose = sample(hour,0,sec)
                assert pose['BridgeLeaf','ROTATION_A'] == pytest.approx(lift)
                assert pose['BridgeBeam','ROTATION_A'] == pytest.approx(lift)
                assert pose['cs_wide','X_POS'] == pytest.approx(director.ROUTE[0][0])
                pos = pose['BulbBarge','X_POS']
                if sec in (0,2,4):
                    assert pos == pytest.approx(start)
                elif sec == 24:
                    assert pos == pytest.approx(end)
                else:
                    assert min(start,end) < pos < max(start,end)
        for minute in (15,30,45):
            pose=sample(10,minute,4)
            assert pose['BridgeLeaf','ROTATION_A'] == 0
            assert pose['BulbBarge','X_POS'] == pytest.approx(3.75)
            assert pose['tower_figure_'+str(minute//15),'ROTATION_A'] > 0
        a,b,c=(sample(10,7,s) for s in (20,25,32))
        assert a['WeighedWheel','X_POS'] < b['WeighedWheel','X_POS']
        assert a['WeighedWheel','X_POS'] == c['WeighedWheel','X_POS']
        assert b['CheesePan','Z_POS'] < b['WeightPan','Z_POS']
        assert sample(10,8,0)['minute_hand','ROTATION_B'] == pytest.approx(48/360)
        assert sample(10,8,0)['hour_hand','ROTATION_B'] == pytest.approx(304/360)
        assert sample(10,5,3)['cs_wide','X_POS'] != pytest.approx(director.STILL[0])
        host.proc.stdin.write(f'P {ix["DutchCuckooVillageSettings"]} 129 1\n')
        flights = [f'RainFlight{i:02}' for i in range(director.RAIN_GROUPS)]
        def visible_flights():
            return sum(cell(director.RAIN_CELL+i) for i in range(len(flights)))

        # Check frame-to-frame travel in the real VM across the minute rollover.
        # The only upward step allowed is from below the canal to above the tower.
        pose = sample(10,0,58.75)
        for frame in range(1,66):
            following = sample(10,0,58.75+frame*.04)
            wraps = 0
            for i,name in enumerate(flights):
                dz = following[name,'Z_POS'] - pose[name,'Z_POS']
                dx = following[name,'X_POS'] - pose[name,'X_POS']
                if dz > 0:
                    assert pose[name,'Z_POS'] < 0 and following[name,'Z_POS'] > 8
                    wraps += 1
                else:
                    assert dz == pytest.approx(-director.RAIN_TRAVEL*.04/(2,2.5)[i%2], abs=.001)
                assert dx == pytest.approx(-dz*director.RAIN_WIND, abs=.001)
            assert wraps <= 2
            pose = following

        for sec in (5,85):
            sample(10,0,sec)
            assert 0 < visible_flights() < len(flights)
        for h,m,s,rain,drips in ((23,0,10,1,1),(10,1,45,0,1),(2,2,5,0,0)):
            pose=sample(h,m,s)
            for name,axis,want in zip(['cs_wide']*3+['LookAt']*3,['X_POS','Y_POS','Z_POS']*2,director.STILL):
                assert pose[name,axis] == pytest.approx(want)
            assert (visible_flights(),cell(216)) == (rain*len(flights),drips)
        assert cell(200)==1
        host.proc.stdin.write(f'P {ix["DutchCuckooVillageSettings"]} 130 0\n')
        sample(2,2,5)
        assert cell(200)==0
    finally:
        host.close()
