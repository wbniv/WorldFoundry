"""The wax blob's morph targets, as functions of a point on the unit sphere (no bpy).

generate.py builds the blob mesh's shape keys from these (morph_<name>, in this order: the MRPH target order the
director's deform blocks follow), and tests/test_lava_lamp.py checks the exported MRPH chunk gives the same points
back. docs/plans/2026-11-26-lava-lamp.md, "How the wax moves" (Shapes) and E1.
"""
from __future__ import annotations

import math


def rise(v):
    """A teardrop climbing: round top, a tail below that thins toward its tip."""
    x, y, z = v
    if z < 0:
        t = -z
        k = 1 - 0.55 * t ** 1.6
        return (x * k, y * k, -t * 1.75 + 0.18)
    return (x * 0.92, y * 0.92, z * 0.92 + 0.18)


def fall(v):
    """The inverted teardrop: a drop sinking, its tail above."""
    x, y, z = rise((v[0], v[1], -v[2]))
    return (x, y, -z)


def squash(v):
    """A pancake under the cap: wide, flat on top."""
    x, y, z = v
    return (x * 1.38, y * 1.38, z * (0.62 if z < 0 else 0.30))


def neck(v):
    """A peanut along X, for two blobs merging (D5): two lobes and a waist."""
    x, y, z = v
    waist = 0.79 - 0.26 * math.exp(-(x * 3.2) ** 2)
    return (0.79 * x + 0.63 * max(-1., min(1., x * 2.6)), y * waist, z * waist)


def _wobble(phase_a, phase_b):
    def f(v):
        x, y, z = v
        th = math.atan2(y, x)
        ph = math.acos(max(-1., min(1., z)))
        k = 1 + 0.07 * math.sin(3 * th + phase_a) * math.sin(2 * ph + phase_b)
        return (x * k, y * k, z * k)
    return f


wobble_a = _wobble(0.0, 0.0)
wobble_b = _wobble(1.9, 1.1)

BLOB_TARGETS = {"rise": rise, "fall": fall, "squash": squash, "neck": neck, "wobble_a": wobble_a, "wobble_b": wobble_b}


def blob_shade(v):
    """The blob's base shade (vertex colour / 255): lit from below, the underside glows; the camera looks along +Y,
    so the edges thin out brighter."""
    x, y, z = v
    below = 0.5 - 0.5 * z
    rim = 1 - abs(y)
    s = 0.48 + 0.42 * below + 0.16 * rim
    return (s, s * 0.97, s * 0.93)
