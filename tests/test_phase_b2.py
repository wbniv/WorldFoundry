"""End-to-end tests for Phase B2 (reload_script).

Hot-swaps a per-actor zForth script over the bridge and verifies the
override drives observable mailbox changes. Also checks the common.Script
guard, the compile-error path, and undo_step.
"""
from __future__ import annotations

import time

# A sentinel global mailbox we can write from injected scripts and watch.
SENTINEL_MBX = 950


def _send_reload(bridge, idx: int, source: str):
    bridge.send({"op": "reload_script", "idx": idx, "source": source})


def test_reload_script_drives_mailbox(bridge):
    """Hot-reload actor 1 to continuously write SENTINEL_MBX, then see it."""
    bridge.watch(idx=5, mailbox=SENTINEL_MBX)
    time.sleep(0.2)
    src = f"\\ wf hot reload\n12345 {SENTINEL_MBX} write-mailbox\n"
    _send_reload(bridge, 5, src)
    msg = bridge.wait_for(lambda m: m.get("op") in ("script_reloaded", "error"),
                          timeout=5.0)
    assert msg is not None and msg.get("op") == "script_reloaded", \
        f"expected script_reloaded, got: {msg}"
    assert bridge.wait_for_mailbox(idx=5, mailbox=SENTINEL_MBX,
                                   expected=12345.0, timeout=3.0), \
        f"sentinel mailbox not driven by override; saw {bridge.mailbox_values.get((1, SENTINEL_MBX))}"


def test_reload_script_compile_error_keeps_old(bridge):
    """Broken Forth must surface as error and leave the prior override live."""
    # Establish a known good override that writes 7777 to the sentinel.
    bridge.watch(idx=5, mailbox=SENTINEL_MBX)
    time.sleep(0.2)
    _send_reload(bridge, 5, f"\\ wf good\n7777 {SENTINEL_MBX} write-mailbox\n")
    bridge.wait_for(lambda m: m.get("op") == "script_reloaded", timeout=5.0)
    assert bridge.wait_for_mailbox(idx=5, mailbox=SENTINEL_MBX,
                                   expected=7777.0, timeout=3.0)
    # Now push junk — calls a word that's not in the dict.
    _send_reload(bridge, 5, "\\ wf broken\nthis_word_does_not_exist_anywhere\n")
    msg = bridge.wait_for(
        lambda m: (m.get("op") == "error" and m.get("what") == "script_compile")
                  or m.get("op") == "script_reloaded",
        timeout=5.0)
    assert msg is not None and msg.get("op") == "error", \
        f"broken Forth reported success: {msg}"
    assert isinstance(msg.get("log"), str) and len(msg["log"]) > 0
    # Old override should still be writing 7777.
    time.sleep(0.3)
    assert bridge.mailbox_values.get((5, SENTINEL_MBX)) == 7777.0, \
        f"prior override clobbered; saw {bridge.mailbox_values.get((5, SENTINEL_MBX))}"


def test_set_prop_common_script_is_guarded(bridge):
    """scene:set_prop on common.Script must be rejected, not corrupt the handle."""
    bridge.send({"op": "scene:set_prop", "idx": 1, "key": "common.Script", "value": 42})
    msg = bridge.wait_for(
        lambda m: m.get("op") == "error" and "common.Script" in (m.get("msg") or ""),
        timeout=3.0)
    assert msg is not None, "expected error reply rejecting common.Script set_prop"


def test_revert_all_clears_script_overrides(bridge):
    """revert_all should drop the script override; the OAD director resumes."""
    # Push a sentinel-writer override.
    bridge.watch(idx=5, mailbox=SENTINEL_MBX)
    time.sleep(0.2)
    _send_reload(bridge, 5, f"\\ wf sentinel\n55555 {SENTINEL_MBX} write-mailbox\n")
    bridge.wait_for(lambda m: m.get("op") == "script_reloaded", timeout=5.0)
    assert bridge.wait_for_mailbox(idx=5, mailbox=SENTINEL_MBX,
                                   expected=55555.0, timeout=3.0)
    # Revert — override should clear and the OAD director resumes (which does
    # NOT write SENTINEL_MBX, so the value freezes at 55555 until something
    # else touches it; the test only checks that the bridge says 'reverted'
    # and that a follow-up reload still works).
    bridge.revert_all()
    rev = bridge.wait_for(lambda m: m.get("op") == "reverted", timeout=3.0)
    assert rev is not None, "no reverted reply"
    # After revert, a fresh reload should still succeed.
    _send_reload(bridge, 5, f"\\ wf post\n111 {SENTINEL_MBX} write-mailbox\n")
    msg = bridge.wait_for(lambda m: m.get("op") == "script_reloaded", timeout=5.0)
    assert msg is not None
    assert bridge.wait_for_mailbox(idx=5, mailbox=SENTINEL_MBX,
                                   expected=111.0, timeout=3.0)
