"""Piecewise motions as eased steps: value(t) = base + sum(delta * ease(seg(t, a, b))).

Every channel here is a function in timeline.py that is a sum of eased ramps. The deltas are
read off timeline.py at each ramp's ends, so timeline.py stays the single source of truth;
tests/test_minute_machine_channels.py proves the reconstruction equals it on 1 ms samples.
forth.py emits the same steps as Forth, so the engine runs the arithmetic the tests check.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import timeline as tl

EASES = {
    "lin": lambda u: u,
    "sq": lambda u: u * u,
    "sm": lambda u: u * u * (3.0 - 2.0 * u),
}
EPS = 1e-9

Step = Tuple[float, float, str]     # (a, b, ease)


def _ease(kind: str, t: float, a: float, b: float) -> float:
    u = tl.c01((t - a) / (b - a))
    return EASES[kind](u)


class Channel:
    def __init__(self, name: str, f: Callable[[float], float], steps: List[Step]):
        self.name, self.f, self.steps = name, f, steps
        self.base = f(0.0)
        self.deltas = [self._delta(a, b) for a, b, _ in steps]

    def _delta(self, a: float, b: float) -> float:
        """The value just after the ramp minus the value just before it."""
        return self.f(min(b + EPS, 60.0 - EPS)) - self.f(max(a - EPS, 0.0))

    def value(self, t: float) -> float:
        return self.base + sum(d * _ease(k, t, a, b) for d, (a, b, k) in zip(self.deltas, self.steps))


def marble_steps_x() -> List[Step]:
    lo, hi = tl.TL["marble_lift"]
    return [(0.0, 4.2, "sq"), (4.5, 8.2, "sq"), (8.5, 11.4, "sq"), (11.4, 12.0, "lin"), (12.0, 12.5, "sm"),
            (13.2, lo, "lin"), (hi, 58.0, "sm")]


def marble_steps_y() -> List[Step]:
    lo, hi = tl.TL["marble_lift"]
    return [(0.0, 4.2, "sq"), (4.2, 4.5, "sq"), (4.5, 8.2, "sq"), (8.2, 8.5, "sq"), (8.5, 11.4, "sq"),
            (12.5, 13.2, "sq"), (lo, hi, "lin")]


def build() -> Dict[str, Channel]:
    teeth = [(55.0 + k, 55.0 + k + tl.TOOTH_TIME, "sm") for k in range(tl.TEETH)]
    return {c.name: c for c in [
        Channel("marble_x", lambda t: tl.marble_px(t)[0], marble_steps_x()),
        Channel("marble_y", lambda t: tl.marble_px(t)[1], marble_steps_y()),
        Channel("seesaw", tl.seesaw_u, [(20.3, 20.8, "sm"), (52.1, 52.6, "sm")]),
        Channel("gate_open", tl.gate_open, [(21.0, 22.0, "sm"), (52.1, 52.6, "sm")]),
        Channel("gate_lift", tl.gate_lift, [(0.0, 0.3, "sm"), (1.5, 2.2, "sm")]),
        Channel("bucket_fill", tl.bucket_fill, [(2.0, 5.5, "lin"), (22.0, 52.0, "lin")]),
        Channel("hopper_fill", tl.hopper_fill, [(7.0, 20.0, "lin"), (22.0, 52.0, "lin")]),
        Channel("trough_fill", tl.trough_fill, [(2.0, 5.5, "lin"), (7.0, 20.0, "lin")]),
        Channel("bucket_tip", tl.bucket_tip, [(1.0, 2.5, "sm"), (5.5, 7.0, "sm")]),
        Channel("pin_px", tl.pin_travel_px, [(2.0, 5.5, "lin")] + teeth),
        Channel("stream", lambda t: tl.sm(tl.seg(t, 22.0, 22.3)) - tl.sm(tl.seg(t, 52.0, 52.3)),
                [(22.0, 22.3, "sm"), (52.0, 52.3, "sm")]),
        Channel("pour", lambda t: tl.sm(tl.seg(t, 2.0, 2.3)) - tl.sm(tl.seg(t, 5.5, 5.8)),
                [(2.0, 2.3, "sm"), (5.5, 5.8, "sm")]),
        Channel("hammer_deg", tl.hammer_deg, [(0.3, 0.5, "sm"), (0.5, 1.2, "sm")]),
        Channel("push", tl.push, [(1.0, 5.0, "sm"), (50.0, 58.0, "sm")]),
    ]}


CHANNELS = build()
