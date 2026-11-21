"""Minute Machine channels: the eased-step form equals timeline.py to a millisecond.

forth.py emits these steps as Forth, so this test is what ties the engine's arithmetic to the
tested reference model. Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wflevels" / "minute_machine"))

import channels as ch  # noqa: E402
import timeline as tl  # noqa: E402


def test_every_channel_reconstructs_its_timeline_function():
    assert set(ch.CHANNELS) >= {"marble_x", "marble_y", "seesaw", "gate_open", "gate_lift", "bucket_fill",
                                "hopper_fill", "trough_fill", "bucket_tip", "pin_px", "stream", "pour",
                                "hammer_deg", "push"}
    for name, c in ch.CHANNELS.items():
        worst = 0.0
        t = 0.0
        while t < 60.0:
            worst = max(worst, abs(c.value(t) - c.f(t)))
            t += 0.001
        assert worst < 1e-5, (name, worst)


def test_steps_do_not_overlap_except_where_they_meet():
    for name, c in ch.CHANNELS.items():
        spans = sorted((a, b) for a, b, _ in c.steps)
        for (a0, b0), (a1, b1) in zip(spans, spans[1:]):
            assert b0 <= a1 + 1e-12, (name, (a0, b0), (a1, b1))


def test_a_closed_channel_ends_where_it_starts():
    for name in ("marble_x", "marble_y", "seesaw", "gate_open", "gate_lift", "bucket_fill", "hopper_fill",
                 "trough_fill", "bucket_tip", "pin_px", "stream", "pour", "hammer_deg", "push"):
        c = ch.CHANNELS[name]
        assert abs(c.base + sum(c.deltas) - c.f(60.0 - 1e-9)) < 1e-5, name
        assert abs(c.f(60.0 - 1e-9) - c.f(0.0)) < 1e-5, name
