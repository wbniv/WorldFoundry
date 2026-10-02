"""Exercise actual Forth interpolation across sparse behavior updates."""
from pathlib import Path
import re
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'docs/reference/swarming-poster'))
sys.path.insert(0, str(ROOT / 'wflevels/aquarium'))
import zfhost
import tiger_barb

@pytest.fixture
def motion():
    h = zfhost.Host()
    try:
        assert h.eval(" ".join(zfhost.fish_trig().splitlines())) == 'ok'
        assert h.eval(" ".join(tiger_barb.forth_constants(29, list(range(29))).splitlines())) == 'ok'
        assert h.load(ROOT / 'wflevels/aquarium/school.fth') == 'ok'
        # Force a right-angle steering decision, including the school core's
        # normal retrospective advancement, to expose interpolation jumps.
        assert h.eval(': fish-dt 0.025 ; : fish-clamp01 0 max 1 min ; '
                      ': sd-bl 1 ; '
                      ': sch-follow MB_ME sc! 0 MB_NVX me sch! '
                      '1 MB_NVY me sch! 0 MB_NVZ me sch! '
                      '0 advance 1 advance 2 advance ;') == 'ok'
        src=(ROOT / 'wflevels/aquarium/barb_school_rig.fth').read_text()
        src='\n'.join(line.split('\\')[0] for line in src.splitlines())
        for word in ['sd-speed','sd-wrap','sd-dt','sd-predict','sd-update','sd-pos','sd-ease-angle']:
            definition=re.search(r': '+word+r'\b.*?;', src, re.S).group()
            assert h.eval(' '.join(definition.splitlines())) == 'ok', word
        for axis in range(3):
            h.write(1220+11+axis, -10)
            h.write(1220+14+axis, 10)
        h.write(814+3, 1)
        h.write(1242+15, 1)
        yield h
    finally:
        h.close()

@pytest.mark.parametrize('gap', [.0167, .1, .15, .3])
def test_new_heading_does_not_retroactively_move_fish(motion, gap):
    h=motion
    h.write(1278, gap)
    assert h.eval('0 0 sd-pos 700 write-mailbox 1 0 sd-pos 701 write-mailbox') == 'ok'
    before=(h.read(700), h.read(701))
    assert h.eval('1 sd-update 0 0 sd-pos 700 write-mailbox 1 0 sd-pos 701 write-mailbox') == 'ok'
    assert (h.read(700), h.read(701)) == pytest.approx(before, abs=.0001)
    assert before == pytest.approx((2*gap,0), abs=.0001)
    h.write(1278, gap+.025)
    assert h.eval('0 0 sd-pos 700 write-mailbox 1 0 sd-pos 701 write-mailbox') == 'ok'
    assert (h.read(700),h.read(701)) == pytest.approx((2*gap,.05),abs=.0001)

def test_between_update_prediction_stays_inside_glass(motion):
    h=motion
    h.write(814,9.9)
    h.write(1278,.15)
    assert h.eval('0 0 sd-pos 700 write-mailbox 1 sd-update 0 0 sd-pos 701 write-mailbox') == 'ok'
    assert h.read(700) == pytest.approx(10)
    assert h.read(701) == pytest.approx(10)

@pytest.mark.parametrize('target,current,expected', [(.25,0,.0125),(-.49,.49,.494),(.49,-.49,-.494)])
def test_rotation_eases_across_shortest_wrap(motion,target,current,expected):
    h=motion
    assert h.eval(f'{target} {current} sd-ease-angle 700 write-mailbox') == 'ok'
    assert h.read(700) == pytest.approx(expected,abs=.0001)
