# Plan — relax `PhysicalAttributes::Validate()` strict-equality check

**Date:** 2026-05-11
**Status:** Done 2026-05-11 — landed in commit [`a56cd51`](../../) `fix(physics): tolerate float-precision drift in PhysicalAttributes::Validate`. Implementation matches the plan: `Scalar::FromDouble(1e-3)` per-axis abs-diff check at [physical.hpi:69](../../wfsource/source/physics/physical.hpi), no-op for fixed-point Scalar targets.

## Symptom

`wf_game` aborts intermittently during the cam intro pan with:

```
FATAL ERROR: PhysicalAttributes::Validate() failed.
predictedMotionVector = -5.299612045, 7.949417114, -2.271261215
      expansionVector = -5.299612045, 7.949417591, -2.271261215
```

X and Z components match exactly; Y differs at the 7th decimal (~5e-7 drift).

## Root cause

[`physical.hpi:37-82`](../../wfsource/source/physics/physical.hpi) checks that the colSpace expansion (`max - unExpMax` or `min - unExpMin`) equals `PredictedPosition() - Position()`. Both quantities should be the same delta, but they're computed by different float subtractions:

- `predictedMotionVector = PredictedPosition() - Position()` — fresh subtraction
- `expansionVector       = (origMax + delta) - origMax` — round-trip via the colSpace's expanded max

When `Scalar == SCALAR_TYPE_FLOAT` (the PC dev configuration), `A + B - A != B` exactly for B of small magnitude relative to A. With A ≈ 8 and B ≈ -5, the last ULP shifts ~5e-7 between the two computations. `Vector3::operator==` is strict bit-equality, so the assert fires.

On a fixed-point `Scalar` target the two computations would be bit-identical and the assert wouldn't fire. The bug is float-mode-only.

## Fix

Replace the strict `expansionVector == predictedMotionVector` test with a per-component absolute-difference threshold:

```cpp
const Scalar tol(0, 0x40);   // ~1e-3 — well above float drift, well below any
                              // physically meaningful inaccuracy
auto axisOk = [&](Scalar a, Scalar b) { return (a - b).Abs() < tol; };
bool ok = axisOk(expansionVector.X(), predictedMotionVector.X())
       && axisOk(expansionVector.Y(), predictedMotionVector.Y())
       && axisOk(expansionVector.Z(), predictedMotionVector.Z());
if (!ok) { …assert(0); }
```

The Scalar(int, fraction) ctor takes (0, 0x40) which is 64/65536 ≈ 9.77e-4 in fixed-point, and `integer=0` for FLOAT (the fraction term is ignored — see `scalar.hpi`). To get a sensible float-mode value, use `Scalar::FromDouble(1e-3)` or `Scalar` from a known small constant. Need to check which API gives consistent semantics across SCALAR_TYPE_*.

**Tolerance choice** — 1e-3 is overkill safety: float drift accumulated from one Expand call is bounded by a few ULPs of the largest operand, which for game-world coordinates in the few-thousand-units range is ~1e-3 worst case. Anything looser starts masking real bugs; anything tighter would still risk false positives.

## Critical files

| File | Change |
|---|---|
| `wfsource/source/physics/physical.hpi` | Replace `==` check at line 69 with per-component tolerance check |

## Verification

1. Rebuild engine.
2. Re-launch qbert standalone — should no longer abort during intro pan.
3. Repeat 5-10 times to be confident (the failure was intermittent).
4. Confirm no regression in snowgoons / MM levels (no abort, gameplay normal).

## What I am NOT doing

- Not changing `Vector3::operator==` globally — too risky, lots of code uses exact equality for legitimate reasons (`v == Vector3::zero`).
- Not changing the Expand math to avoid the round-trip — minor refactor, doesn't address other Validate callers.
- Not disabling Validate — it catches real bugs, just needs tolerance for float-mode arithmetic.
