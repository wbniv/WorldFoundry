"""The school reacts once to actual dart movement, including a delayed release from glass."""
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'docs/reference/swarming-poster'))
import zfhost


@pytest.mark.parametrize('rig', ['school_rig.fth', 'barb_school_rig.fth'])
def test_startle_requires_post_physics_dart_movement(rig):
    text = (ROOT / 'wflevels/aquarium' / rig).read_text()
    text = '\n'.join(line.split('\\')[0] for line in text.splitlines())
    word = re.search(r': sd-dart-check\b.*?;', text, re.S).group()
    h = zfhost.Host()
    try:
        assert h.eval('700 constant aq-dart-t 701 constant sd-lspeed 702 constant sd-dart-prev '
                      ': sch-startle-all drop 703 read-mailbox 1 + 703 write-mailbox ;') == 'ok'
        assert h.eval(' '.join(word.splitlines())) == 'ok'
        h.write(700, .15)
        for speed in [0, 0, .01, 3.4, 4.49]:
            h.write(701, speed)
            assert h.eval('sd-dart-check') == 'ok'
            assert h.read(703) == 0
        # Still in the same dart window: movement becomes possible, then one startle.
        h.write(701, 5.5)
        assert h.eval('sd-dart-check sd-dart-check sd-dart-check') == 'ok'
        assert h.read(703) == 1
        h.write(700, 0)
        assert h.eval('sd-dart-check') == 'ok'
        # Fast movement by itself cannot startle without a new dart.
        assert h.eval('sd-dart-check') == 'ok'
        assert h.read(703) == 1
        h.write(700, .1)
        assert h.eval('sd-dart-check') == 'ok'
        assert h.read(703) == 2
    finally:
        h.close()
