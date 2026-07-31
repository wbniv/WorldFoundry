# Plan: Add "loss of exact equality comparison" cost to fixed-point survey doc

**Status:** DONE — the exact-equality-cost note is in the [fixed-point platform survey](../investigations/2026-05-10-fixed-point-platform-survey.md) (§ float trade-offs).

## Context

The fixed-point platform survey
[`docs/investigations/2026-05-10-fixed-point-platform-survey.md`](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-10-fixed-point-platform-survey.md)
has a §4 "Removing fixed-point from WF — cost survey" with a "What removing it
costs" subsection (lines 228–232). The user wants one more cost listed:
fixed-point integers compare cleanly with `==`, but IEEE floats do not (NaN,
denormals, lossy arithmetic), so a `Scalar`-becomes-`float` migration would
silently break every direct equality comparison currently relying on
fixed-point semantics. Mitigation worth flagging: overload `Scalar::operator==`
with an epsilon comparison so call sites continue to read naturally.

## Edit

Single edit to one file. Add a bullet to the "What removing it costs" list at
line 228, after the existing three bullets:

```
- Loses **exact equality comparison**. Fixed-point `Scalar` values compare with
  `==` deterministically — same input bits, same answer. Under
  `SCALAR_TYPE_FLOAT` the same sites become hazardous: arithmetic results
  rarely round-trip exactly, and NaN never compares equal to anything
  including itself. Every existing `Scalar a == b` comparison would need
  audit. Mitigation: overload `Scalar::operator==` (and `!=`) with an
  epsilon-based comparison so call sites keep reading naturally; the
  underlying float still has the precision pitfalls but the *site-level*
  semantics stay close to the fixed-point version.
```

## Critical files

- `docs/investigations/2026-05-10-fixed-point-platform-survey.md` — the only
  edit.

## Verification

- Diff shows a single bullet added inside §4 "What removing it costs".
- Section ordering and surrounding bullets unchanged.
- No other costs/recommendations sections need updating; the
  "Recommendation" (§5) doesn't enumerate costs, just summarises them, and the
  new cost doesn't change the recommendation.
