"""Deterministic local-time envelope for the village's day/night appearance.

The same envelope drives the sky and foreground. Window/candle staggering stays
in timeline.py; a jump or restart simply evaluates this function again.
"""
from __future__ import annotations

DAY_SECONDS = 24 * 3600
DAWN_START, DAWN_END = 5.5 * 3600, 6.5 * 3600
DUSK_START, DUSK_END = 17.5 * 3600, 18.5 * 3600


def _smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def appearance(seconds: float) -> tuple[float, float]:
    """Return (daylight, twilight warmth), each in [0, 1]."""
    t = seconds % DAY_SECONDS
    if DAWN_START <= t < DAWN_END:
        q = _smooth((t - DAWN_START) / (DAWN_END - DAWN_START))
        return q, 4.0 * q * (1.0 - q)
    if DUSK_START <= t < DUSK_END:
        q = _smooth((t - DUSK_START) / (DUSK_END - DUSK_START))
        return 1.0 - q, 4.0 * q * (1.0 - q)
    return (1.0, 0.0) if DAWN_END <= t < DUSK_START else (0.0, 0.0)
