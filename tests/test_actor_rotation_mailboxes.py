"""Rotation mailbox writes must update the writing actor's own rotation.

Regression guard: Actor::WriteSystemMailbox kept one `static Euler` shared by
every actor ("kts major kludge") and applied it only on a ROTATION_C write.
A lone A or B write therefore never reached its actor and leaked into
whichever actor wrote C next. Found by the reef W5 R0 spike (2026-11-08):
the reef's sea-fan sway never applied, the feather star and nudibranch picked
up the fan's tilt, and the guard crab's threat tilt pitched the boxfish.
"""
import re
from pathlib import Path

ACTOR = Path(__file__).resolve().parents[1] / 'wfsource' / 'source' / 'game' / 'actor.cc'


def _write_system_mailbox():
    text = ACTOR.read_text()
    start = text.index('Actor::WriteSystemMailbox(')
    end = text.index('\nActor::', start + 1) if '\nActor::' in text[start + 1:] else len(text)
    return text[start:end]


def test_no_rotation_state_is_shared_between_actors():
    body = _write_system_mailbox()
    assert not re.search(r'static\s+Euler\s+\w+\s*;', body)   # a declaration, not the comment


def test_each_rotation_axis_write_applies_to_its_own_actor():
    body = _write_system_mailbox()
    for axis in 'ABC':
        case = body[body.index(f'case EMAILBOX_ROTATION_{axis}:'):]
        case = case[:case.index('break;')]
        assert '_physicalAttributes.Rotation()' in case, axis
        assert f'.Set{axis}(' in case, axis
        assert '_physicalAttributes.SetRotation(' in case, axis
