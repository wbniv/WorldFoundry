"""Compare cached scans to the preserved pre-optimization Forth, including commits."""
from pathlib import Path
import math
import random
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'docs/reference/swarming-poster'))
import zfhost

@pytest.mark.parametrize('population',[11,30])
def test_cached_scan_preserves_state_and_reduces_bridge_calls(population):
    hosts=[zfhost.Host(),zfhost.Host()]
    rng=random.Random(3029+population)
    try:
        for h in hosts:
            assert h.eval(' '.join(zfhost.fish_trig().splitlines()))=='ok'
            assert h.eval(f': sch-base 800 ; : sch-scr 1242 ; : sch-par 1220 ; : sch-n {population} ;')=='ok'
        assert hosts[0].load(ROOT/'tests/fixtures/aquarium/school-before-cache.fth')=='ok'
        assert hosts[1].load(ROOT/'wflevels/aquarium/school.fth')=='ok'
        calls=[0,0]
        for trial in range(30):
            params=[.55,.7,1.5,-.75,.98,.199,.04,3,.22,.45,.025,-3,-2,-1,3,2,1,.7,1.5,1.5,.7,2]
            # Cover empty/dense scans, different zones, all blind angles, and walls.
            params[0:4]=[rng.uniform(.1,1),rng.uniform(0,2),rng.uniform(0,3),rng.uniform(-1,1)]
            states=[]
            for fish in range(population):
                xyz=[rng.uniform(-3,3),rng.uniform(-2,2),rng.uniform(-1,1)]
                v=[rng.uniform(-1,1) for _ in range(3)];norm=math.sqrt(sum(x*x for x in v));v=[x/norm for x in v]
                if trial%5==0 and fish in (1,2): xyz=[0,0,0] # coincident neighbour
                states.extend(xyz+v+[0]*6+[.15 if fish%4==0 else 0,0])
            for h in hosts:
                for i,v in enumerate(params):h.write(1220+i,v)
                for i,v in enumerate(states):h.write(800+i,v)
                h.cmd('N')
            for step in range(8):
                fish=1+(step*5+trial)%(population-1)
                if step==3:
                    for h in hosts:assert h.eval('1.5 sch-startle-all')=='ok'
                for h in hosts:assert h.eval(f'{fish} sch-follow {fish} sch-commit1')=='ok'
                assert hosts[1].read(800,14*population)==hosts[0].read(800,14*population), (trial,step)
                assert hosts[1].read(1242,15)==hosts[0].read(1242,15), (trial,step)
            for i,h in enumerate(hosts):
                values=h.cmd('N').split();calls[i]+=int(values[0])+int(values[2])
        print(f"population={population}: mailbox calls {calls[0]} -> {calls[1]}; saved {100*(1-calls[1]/calls[0]):.2f}%")
        assert calls[1]<calls[0]*.95,calls
    finally:
        for h in hosts:h.close()
