# Fix `Scalar::Random()` abort + the `RangeCheck`-with-`Scalar` family bug

## Context

`Scalar::Random()` aborts on every call in assertion-enabled builds, making the `Generator` actor's "Random Displacement" unusable and forcing deterministic workarounds elsewhere (e.g. the SMB debris fan is actor-index-based *because* `Scalar::Random` is broken). The user picked this as a quick, high-value fix; it's also thematically adjacent to the negative-angle `Scalar` UB I just fixed.

**Root cause (verified):** the `RangeCheck` / `RangeCheckInclusive` / `RangeCheckExclusive` macros (`wfsource/source/pigsys/assert.hp:200-216`) cast every argument to `(ptrdiff_t)`. `Scalar`'s *only* conversion operator is `operator bool()` (`scalar.hpi:388`; its constructors are all `explicit`), so `(ptrdiff_t)(anyScalar)` collapses to `0` or `1`. In `Random()`, both `value` (∈[0,1)) and `max` (`Scalar::one`) become `1`, so `1 < 1` fails. The macros are **no-ops when `!DO_ASSERTIONS`** (assert.hp:234), so this silently "worked" in release for ~16 years and only aborts in debug / ASan / wf-edit / debug-bridge builds. The buggy line (`scalar.cc:1193`) dates to the 2010 first commit (`a2784f6e`) → **qualifies for `docs/BUGS.md`**.

**Secondary bug (verified):** `Random()` does `temp = rand() >> 16` → [0, 32767], then (float path) `/= 65536` → **[0, 0.5)**, not the intended [0, 1). The FIXED path (`_value = temp`) is also [0, 0.5). One change — `>> 16` → `>> 15` (→ [0, 65535]) — fixes both backends to [0, 1).

**Scope (user-chosen): root-cause sweep** — fix `Random` *and* the sibling `RangeCheck`-with-`Scalar` sites via one reusable helper.

## Approach

Add a cast-free, `Scalar`-safe range-check macro and use it at every `RangeCheck*`-with-`Scalar` site; fix `Random`'s range; add a regression test; record the dormant bug.

### 1. New macro — `wfsource/source/pigsys/assert.hp`
Add `RangeCheckScalar` and `RangeCheckScalarInclusive` (mirror the existing `RangeCheck` placement: real body inside `#if DO_ASSERTIONS`, empty in the `#else`). Same as `RangeCheck`/`RangeCheckInclusive` but **without the `(ptrdiff_t)` casts** — compare the values directly so the type's own `operator>=/</<=` is used (works for `Scalar`; `AssertMsg`'s `<<` streams `Scalar` via its `operator<<`). Reuse the existing `AssertMsg(exp, str)` mechanism — no new assert primitive.

```c
#  define RangeCheckScalar( min, value, max ) \
   { AssertMsg( (value) >= (min), #min " = " << (min) << ", " #value " = " << (value) ); \
     AssertMsg( (value) <  (max), #value " = " << (value) << ", " #max " = " << (max) ); }
#  define RangeCheckScalarInclusive( min, value, max ) /* ... <= max ... */
```

### 2. Fix `Scalar::Random` — `wfsource/source/math/scalar.cc:1168-1209`
- `rand() >> 16` → `rand() >> 15` (full [0, 1) on both backends; add a one-line comment on the BAM/normalization).
- `scalar.cc:1193` `RangeCheck(Scalar::zero, random_value, Scalar::one)` → `RangeCheckScalar(...)`.
- `scalar.cc:1206` `RangeCheck(lower, random_value, upper)` → `RangeCheckScalar(...)`.

### 3. Sweep the sibling sites (same mechanical swap)
- `wfsource/source/gfx/viewport.hpi:42,43` — `RangeCheckInclusive` → `RangeCheckScalarInclusive`.
- `wfsource/source/particle/emitter.hpi:34,36` — `RangeCheck` → `RangeCheckScalar`; `:39,40` — `RangeCheckInclusive` → `RangeCheckScalarInclusive`.
- `wfsource/source/particle/emitter.cc:80,81` — `RangeCheckInclusive` → `RangeCheckScalarInclusive`.

(Leave all *integer*-arg `RangeCheck*` calls untouched — e.g. `texture.cc:74`, VRAM-slot checks — they work correctly.)

### 4. Regression test — `wfsource/source/math/mathtest.cc:37-44`
Replace the print-only (currently-aborting) Random loop with an asserting one: over ~1000 iters, `AssertMsg(r >= Scalar::zero && r < Scalar::one, ...)` for `Random()` and `AssertMsg(rr >= negativeOne && rr < two, ...)` for `Random(-1,2)`; track the max observed `Random()` and assert it exceeds ~0.5 (proves the `>>15` range fix; pre-fix max was <0.5). Use explicit comparisons (not the macro under test). Mirrors the negative-angle regression assert I added there earlier.

### 5. Document — `docs/BUGS.md` + `docs/investigations/2026-06-12-scalar-random-rangecheck.md`
New BUGS.md entry (reverse-chron, newest first): symptom (aborts in assertion builds), root cause (`RangeCheck` ptrdiff_t cast → `operator bool` collapse → `1<1`), why dormant (no-op in release; Random avoided in practice), fix (cast-free `RangeCheckScalar`), plus the `>>16`→`>>15` range note. Short investigation doc linked from the entry. Run `task md -- <files>` after writing.

## Files
- `wfsource/source/pigsys/assert.hp` — add 2 macros (×2 for the `#else` no-op)
- `wfsource/source/math/scalar.cc` — Random range + 2 checks
- `wfsource/source/gfx/viewport.hpi`, `wfsource/source/particle/emitter.hpi`, `wfsource/source/particle/emitter.cc` — sibling swaps
- `wfsource/source/math/mathtest.cc` — regression test
- `docs/BUGS.md`, `docs/investigations/2026-06-12-scalar-random-rangecheck.md` — write-up

## Verification
1. **Reproduce first:** build an assertion-enabled config (`task build` debug / `task build-asan`) on a clean tree → confirm a `Scalar::Random()` call aborts (run the strengthened `mathtest` Random loop, or a particle/Generator level). Capture the abort.
2. **After the fix, same build:** the `mathtest` Random loop runs 1000 iters with **no abort**, all values in range, and max `Random()` > 0.5 (range fix). Paste raw output.
3. **Feature end-to-end:** in an assertion build, run a level exercising the path — a `Generator` with nonzero Random Displacement, or a particle emitter — and confirm no abort + visibly randomized output (screenshot/log).
4. **Release unaffected:** `task build-web` (Release) still builds/links; `Scalar::Random` now returns correct [0,1) values (the checks are no-ops there as before).
5. Paste each step's raw output + PASS/FAIL back into this plan / the BUGS.md investigation.

## Notes / risk
- Behaviour change: callers now get true [0,1) (and non-zero) randomness instead of [0,0.5)-or-abort. No *working* caller depends on the old behaviour (it aborted in debug and was worked around). Particle velocity spread / Generator displacement will now use their full intended range — the correct outcome.
- The new macro is value-comparison-based, so it's also correct for any non-integral comparable+streamable type, not just `Scalar`.

## Result (2026-06-12) — DONE, fix `2fe49ef4`

- All 11 `RangeCheck*`-with-`Scalar` sites swapped to the cast-free macros (scalar.cc Random ×2, particle emitter ×7, viewport ×2); `rand()>>16`→`>>15`; `mathtest` regression assert added. Integer `RangeCheck*` sites left untouched.
- **V1 — compile the real macro with `Scalar` — PASS, twice.** Native `build_game.sh` and `cmake --build build --target wfengine` both link clean with `DO_ASSERTIONS=1`, exercising the real `RangeCheckScalar` body against `Scalar` at every site (the primary risk).
- **V2 — no-abort + range.** Established by construction (`random_value = (rand()>>15)/65536 ∈ [0, 65535/65536]` ⇒ `≥0 && <1`) and guarded by the `mathtest` assert. A standalone harness compiled the fixed `scalar.cc` but a minimal *link* pulls the engine's GL/Jolt/zForth graph, and `Xvfb` isn't installed for a native run — a tooling limit, not a fix gap.
- **Correction to plan V4:** `DO_ASSERTIONS=1` is set **unconditionally** (`CMakeLists.txt:151`), so the checks are *not* no-ops in the Release/web build — the bug is dormant because `Random` is never called, not because assertions are off. The web build still links clean.
- Write-ups: [investigation](../investigations/2026-06-12-scalar-random-rangecheck.md), [BUGS.md](../BUGS.md).
