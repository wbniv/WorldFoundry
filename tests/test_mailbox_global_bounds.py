"""Regression tests for the GLOBAL_USER_MAX mailbox boundary
(docs/plans/2026-05-30-a-e-b-audit-follow-up-mailbox-999-fix-shared-curso.md, §E).

Before the 2026-05-30 fix, `LevelMailboxes` allocated `MAX - START` slots
(treating GLOBAL_USER_MAX as exclusive), so writing to the named max index
itself hit an `AssertMsg(0, ...)` and aborted the engine with
``terminate called without an active exception``. The fix is `MAX - START + 1`
so the inclusive interpretation matches the constant's natural reading.
"""
from __future__ import annotations

import time

# Keep these in sync with wfsource/source/mailbox/mailbox.inc.
# GLOBAL_USER_MAX is the *inclusive* last valid user-region index.
GLOBAL_USER_MAX     = 1900
GLOBAL_SYSTEM_START = 1901
GLOBAL_SYSTEM_MAX   = 1922  # exclusive — last named system slot is CAMSHOT=1921


def test_global_user_max_is_writable(bridge):
    """Writing GLOBAL_USER_MAX (1900) must succeed and read back."""
    # Watch via actor 1 so the next broadcast reflects the global value.
    bridge.watch(idx=1, mailbox=GLOBAL_USER_MAX)
    time.sleep(0.2)
    bridge.set_mailbox(mailbox=GLOBAL_USER_MAX, value=42, idx=0)
    assert bridge.wait_for_mailbox(
        idx=1, mailbox=GLOBAL_USER_MAX, expected=42.0, timeout=3.0
    ), (f"mailbox {GLOBAL_USER_MAX} did not reach 42; "
        f"saw {bridge.mailbox_values.get((1, GLOBAL_USER_MAX))}")


def test_global_user_max_minus_one_is_writable(bridge):
    """The slot just below GLOBAL_USER_MAX has always worked — keep the regression."""
    idx = GLOBAL_USER_MAX - 1  # 1899
    bridge.watch(idx=1, mailbox=idx)
    time.sleep(0.2)
    bridge.set_mailbox(mailbox=idx, value=7, idx=0)
    assert bridge.wait_for_mailbox(
        idx=1, mailbox=idx, expected=7.0, timeout=3.0
    ), f"mailbox {idx} did not reach 7"


# NOTE: a third test that asserted the engine *survives* writes deep into
# invalid space (e.g. GLOBAL_SYSTEM_MAX + 100) is intentionally NOT here:
# `MailboxesWithStorage::WriteMailbox` still fires `AssertMsg(0, ...)` →
# abort() on clearly-invalid indices, which is the documented Debug-build
# behaviour. Making out-of-range writes a soft warn-and-discard is a separate
# design decision; this regression set only covers the off-by-one that was
# making GLOBAL_USER_MAX itself unreachable.
