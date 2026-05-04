"""End-to-end tests for Phase A debug-bridge ops (set_mailbox, inject_input).

Driven against qbert_practice-standalone.iff. The director script reads
mailbox 200+i for each cube state (28 cubes), and writes 300+i*3 visibility
mailboxes. The player script reads INDEXOF_HARDWARE_JOYSTICK1_RAW (1009).
"""
from __future__ import annotations

import time

# Mailbox indices reused from wfsource/source/mailbox/mailbox.inc
EMAILBOX_HARDWARE_JOYSTICK1_RAW = 1009


def test_set_mailbox_global_changes_value(bridge):
    """Writing global mailbox 200 should be observable via watch."""
    # The director (actor 1 typically) reads mailbox 200. Watch via actor 1
    # since per-actor GetMailboxes() routes globals to the parent.
    bridge.watch(idx=1, mailbox=200)
    # Allow first broadcast through.
    time.sleep(0.2)
    bridge.set_mailbox(mailbox=200, value=2, idx=0)
    assert bridge.wait_for_mailbox(idx=1, mailbox=200, expected=2.0, timeout=3.0), \
        f"mailbox 200 did not reach 2; saw {bridge.mailbox_values.get((1, 200))}"


def test_set_mailbox_undo_restores_prior(bridge):
    """undo_step on a mailbox write should restore the previous value."""
    bridge.watch(idx=1, mailbox=201)
    time.sleep(0.2)
    bridge.set_mailbox(mailbox=201, value=2, idx=0)
    assert bridge.wait_for_mailbox(idx=1, mailbox=201, expected=2.0, timeout=3.0)
    bridge.undo_step()
    assert bridge.wait_for_mailbox(idx=1, mailbox=201, expected=0.0, timeout=3.0), \
        f"undo did not restore mailbox 201 to 0; saw {bridge.mailbox_values.get((1, 201))}"


def test_inject_input_observable_in_mailbox(bridge):
    """inject_input on joystick1_raw with sticky duration should reflect
    through the EMAILBOX_HARDWARE_JOYSTICK1_RAW broadcast."""
    # Watch global slot 1009 (HARDWARE_JOYSTICK1_RAW) via actor 1.
    bridge.watch(idx=1, mailbox=EMAILBOX_HARDWARE_JOYSTICK1_RAW)
    time.sleep(0.2)
    # 0x0800 = EJ_BUTTONF_UP per qbert player script.
    bridge.inject_input(slot="joystick1_raw", value=0x0800, duration_frames=-1)
    assert bridge.wait_for_mailbox(
        idx=1, mailbox=EMAILBOX_HARDWARE_JOYSTICK1_RAW,
        expected=float(0x0800), timeout=3.0), \
        f"injected joystick value not observed; saw {bridge.mailbox_values.get((1, EMAILBOX_HARDWARE_JOYSTICK1_RAW))}"
    # Clear the override so subsequent tests aren't poisoned.
    bridge.inject_input(slot="joystick1_raw", value=0, duration_frames=1)


def test_inject_input_one_shot_expires(bridge):
    """duration_frames=0 should hold for one frame then expire."""
    bridge.watch(idx=1, mailbox=EMAILBOX_HARDWARE_JOYSTICK1_RAW)
    time.sleep(0.2)
    # First make sure baseline is 0.
    bridge.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
    assert bridge.wait_for_mailbox(
        idx=1, mailbox=EMAILBOX_HARDWARE_JOYSTICK1_RAW,
        expected=0.0, timeout=3.0)
    # Inject a one-frame value; engine ticks at well over 60Hz, so the
    # override has likely already expired by the time we observe — what we
    # actually want is that the value DOES NOT remain stuck. Wait for it to
    # return to 0.
    bridge.inject_input(slot="joystick1_raw", value=0x4000, duration_frames=0)
    time.sleep(1.0)
    val = bridge.mailbox_values.get((1, EMAILBOX_HARDWARE_JOYSTICK1_RAW), 0.0)
    assert val == 0.0, f"one-shot inject did not expire; mailbox stuck at {val}"
