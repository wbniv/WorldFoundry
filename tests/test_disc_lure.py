"""Tests for the Coily disc-lure mechanic (commit 1f4b272).

Teleports the snake to a disc coordinate with cooldown=0 via the debug bridge,
then asserts the retirement fires (COILY_SNAKE_ACTIVE → 0, score += 500,
COILY_MB_PHASE_GLOBAL → 0) within a few game frames.
"""
from __future__ import annotations

import time

# Global mailbox constants — must match blender_create_qbert.py.
MB_SCORE               = 70
MB_FREEZE_TIMER        = 546   # GB_MB_FREEZE_TIMER — >0 makes snake skip ticks
CS_MB_ROW              = 526
CS_MB_COL              = 527
CS_MB_COOLDOWN         = 528
CS_MB_PHASE            = 529
COILY_MB_PHASE_GLOBAL  = 543
COILY_SNAKE_ACTIVE     = 574

# Disc coords (must match DISC_L_*/DISC_R_* in blender_create_qbert.py).
DISC_L_ROW, DISC_L_COL = 1, -1
DISC_R_ROW, DISC_R_COL = 1,  2


def _setup(bridge, row: int, col: int) -> None:
    """Watch retirement mailboxes, zero score, and place the snake."""
    # Watch via idx=1 (director) — the bridge broadcasts global mailboxes
    # through whichever actor reads them; idx=0 is the level object and
    # doesn't broadcast.  Consistent with test_phase_a.py pattern.
    bridge.watch(idx=1, mailbox=MB_SCORE)
    bridge.watch(idx=1, mailbox=COILY_SNAKE_ACTIVE)
    bridge.watch(idx=1, mailbox=COILY_MB_PHASE_GLOBAL)
    time.sleep(0.15)

    bridge.set_mailbox(mailbox=MB_SCORE, value=0, idx=0)
    bridge.set_mailbox(mailbox=MB_FREEZE_TIMER, value=0, idx=0)  # no freeze
    bridge.set_mailbox(mailbox=COILY_MB_PHASE_GLOBAL, value=2, idx=0)
    bridge.set_mailbox(mailbox=COILY_SNAKE_ACTIVE, value=1, idx=0)
    bridge.set_mailbox(mailbox=CS_MB_PHASE, value=1, idx=0)
    bridge.set_mailbox(mailbox=CS_MB_ROW, value=row, idx=0)
    bridge.set_mailbox(mailbox=CS_MB_COL, value=col, idx=0)
    bridge.set_mailbox(mailbox=CS_MB_COOLDOWN, value=0, idx=0)   # landing tick next frame


def _teardown(bridge) -> None:
    bridge.set_mailbox(mailbox=CS_MB_PHASE, value=0, idx=0)
    bridge.set_mailbox(mailbox=COILY_SNAKE_ACTIVE, value=0, idx=0)
    bridge.set_mailbox(mailbox=COILY_MB_PHASE_GLOBAL, value=0, idx=0)


def test_disc_lure_left(bridge):
    """Snake at disc-L coord (row=1, col=-1) retires with +500 on landing tick."""
    _setup(bridge, row=DISC_L_ROW, col=DISC_L_COL)
    try:
        assert bridge.wait_for_mailbox(idx=1, mailbox=COILY_SNAKE_ACTIVE,
                                       expected=0.0, timeout=3.0), \
            f"snake did not retire; COILY_SNAKE_ACTIVE={bridge.mailbox_values.get((1, COILY_SNAKE_ACTIVE))}"
        assert bridge.wait_for_mailbox(idx=1, mailbox=MB_SCORE,
                                       expected=500.0, timeout=1.0), \
            f"score not 500; got {bridge.mailbox_values.get((1, MB_SCORE))}"
        assert bridge.wait_for_mailbox(idx=1, mailbox=COILY_MB_PHASE_GLOBAL,
                                       expected=0.0, timeout=1.0), \
            f"COILY_MB_PHASE_GLOBAL not 0; got {bridge.mailbox_values.get((1, COILY_MB_PHASE_GLOBAL))}"
    finally:
        _teardown(bridge)


def test_disc_lure_right(bridge):
    """Snake at disc-R coord (row=1, col=2) retires with +500 on landing tick."""
    _setup(bridge, row=DISC_R_ROW, col=DISC_R_COL)
    try:
        assert bridge.wait_for_mailbox(idx=1, mailbox=COILY_SNAKE_ACTIVE,
                                       expected=0.0, timeout=3.0), \
            f"snake did not retire; COILY_SNAKE_ACTIVE={bridge.mailbox_values.get((1, COILY_SNAKE_ACTIVE))}"
        assert bridge.wait_for_mailbox(idx=1, mailbox=MB_SCORE,
                                       expected=500.0, timeout=1.0), \
            f"score not 500; got {bridge.mailbox_values.get((1, MB_SCORE))}"
        assert bridge.wait_for_mailbox(idx=1, mailbox=COILY_MB_PHASE_GLOBAL,
                                       expected=0.0, timeout=1.0), \
            f"COILY_MB_PHASE_GLOBAL not 0; got {bridge.mailbox_values.get((1, COILY_MB_PHASE_GLOBAL))}"
    finally:
        _teardown(bridge)


def test_no_spurious_retire_at_normal_coord(bridge):
    """Snake at a normal pyramid coord (row=2, col=1) must NOT retire."""
    _setup(bridge, row=2, col=1)
    try:
        time.sleep(0.5)   # let several landing ticks pass
        val = bridge.mailbox_values.get((1, COILY_SNAKE_ACTIVE), 1.0)
        assert val == 1.0, \
            f"snake spuriously retired at (2,1); COILY_SNAKE_ACTIVE={val}"
    finally:
        _teardown(bridge)
