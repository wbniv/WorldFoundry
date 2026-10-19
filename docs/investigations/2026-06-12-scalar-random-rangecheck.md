# `Scalar::Random()` aborts — `RangeCheck` casts `Scalar` to `bool` (2026-06-12)

**Status:** FIXED [`2fe49ef4`](https://github.com/wbniv/WorldFoundry/commit/2fe49ef4) — `wfsource/source/pigsys/assert.hp` (cast-free `RangeCheckScalar`), `wfsource/source/math/scalar.cc`.

## Symptom

`Scalar::Random()` aborts on the **first call** in any assertion-enabled build
(`task build` debug, `task build-asan`, wf-edit, the debug bridge):

```
AssertMsg: random_value = 0.42…, Scalar::one = 1  → terminate
```

So the `Generator` actor's `Random X/Y/Z Range` displacement fields
(`generator.cc`, the main caller) can never be set non-zero, and gameplay code
worked around it — e.g. the SMB breakable-brick debris fan is a *deterministic*
actor-index pattern precisely because `Scalar::Random` is unusable.

## Root cause

`Scalar::Random()` (`scalar.cc:1193`) ends with:

```cpp
RangeCheck( Scalar::zero, random_value, Scalar::one );
```

The `RangeCheck` / `RangeCheckInclusive` / `RangeCheckExclusive` macros
(`assert.hp:200-216`) cast **every argument to `(ptrdiff_t)`**:

```cpp
#define RangeCheck( min, value, max) \
  { AssertMsg((ptrdiff_t)(value) >= (ptrdiff_t)(min), ...); \
    AssertMsg((ptrdiff_t)(value) <  (ptrdiff_t)(max), ...); }
```

`Scalar`'s **only** conversion operator is `operator bool()` (`scalar.hpi:388`)
— its constructors are all `explicit`, so there is no `Scalar→int/float`
conversion. Therefore `(ptrdiff_t)(anyScalar)` resolves through `operator bool()`
and collapses to **0 or 1**:

| expression | becomes |
|---|---|
| `(ptrdiff_t)(Scalar::zero)` | `bool(0.0)` = `0` |
| `(ptrdiff_t)(Scalar::one)`  | `bool(1.0)` = `1` |
| `(ptrdiff_t)(random_value∈[0,1))` | `bool(nonzero)` = `1` |

So the upper check becomes `1 < 1` → **always false** → abort. (The lower check
`1 >= 0` happens to pass.)

### Why it stayed dormant since 2010

The buggy line is from the 2010 first commit (`a2784f6e`). Two things kept it
hidden:

- **It's never called.** The only realistic caller, the `Generator` actor's
  Random Displacement, was always left at zero or replaced by deterministic
  workarounds (the commented-out fallbacks in `generator.cc`; the SMB debris fan
  is actor-index-based). The particle-emitter paths that would *also* trip an
  exclusive `RangeCheck` (`emitter.hpi`) aren't exercised by current levels.
- **Only the *exclusive* form aborts.** `RangeCheck` checks `value < max` →
  `1 < 1` → abort. But `RangeCheckInclusive` checks `value <= max` → `1 <= 1` →
  **passes**. So the inclusive `Scalar` sites (viewport size, particle alpha)
  never abort — they just silently degrade to a no-op check, a quieter form of
  the same bug. Random/sphere-radius/period use the exclusive `RangeCheck`, so
  those are the ones that actually abort.

Note: this engine's modern builds enable `DO_ASSERTIONS=1` **unconditionally**
(`CMakeLists.txt:151`, even the Release web build), so the abort is *not* gated
behind a debug build — `Scalar::Random()` would abort on the live web demo too,
the moment a level called it. The original 2010-era PSX shipping builds disabled
assertions (`!DO_ASSERTIONS` → `RangeCheck` is a no-op, `assert.hp:234`), which
is how it survived shipping; the revival just never wired up a caller.

This is the same shape as the negative-angle `AsUnsignedFraction` bug fixed the
same day: a `Scalar` value flowing into integer-oriented code that silently
mangles it.

### Secondary bug: half range

`Random()` also only spanned **[0, 0.5)**, not [0, 1):

```cpp
temp = rand() >> 16;          // RAND_MAX(=INT_MAX) >> 16 = 32767
random_value._value = temp;   // FIXED: 32767/65536 ≈ 0.5 max
random_value._value /= 65536; // FLOAT: same
```

`rand() >> 15` (→ [0, 65535]) gives a full [0, 1) on both backends.

## The same mistake elsewhere

`RangeCheck*` is misused with `Scalar` args at sibling sites that would abort
identically if exercised in an assertion build:

- `wfsource/source/particle/emitter.hpi:34,36,37,39,40` (sphere radius, period,
  generate-time window, alpha) — explains why particle-using levels haven't been
  run under assertions.
- `wfsource/source/particle/emitter.cc:80,81` (alpha).
- `wfsource/source/gfx/viewport.hpi:42,43` (viewport size).

## Fix

A new cast-free macro pair in `assert.hp` — `RangeCheckScalar` /
`RangeCheckScalarInclusive` — identical to `RangeCheck`/`RangeCheckInclusive` but
**without the `(ptrdiff_t)` casts**, so the value's own `operator>=/</<=` and
`operator<<` are used (correct for `Scalar`, and for any comparable+streamable
type). All `RangeCheck*`-with-`Scalar` sites above are switched to it; the
integer `RangeCheck*` sites (`display.hpi`, `pixelmap`, `_nParticles`,
`texture.cc` VRAM checks) are left unchanged. `Random()`'s `>> 16` → `>> 15`.

Regression guard: `mathtest.cc`'s random loop now *asserts* `Random() ∈ [0,1)`,
`Random(-1,2) ∈ [-1,2)` over 1000 draws and that the observed max exceeds 0.5
(catches a half-range regression). (`mathtest.cc` is in the build skip list, so
this documents/guards the invariant rather than running in CI — same as the
negative-angle assert added there.)

## Verification

1. **Compile/link the real macro with `Scalar` (the primary risk) — PASS, twice.**
   `RangeCheckScalar`/`...Inclusive` expand to `AssertMsg((value) >= (min), …)`
   with `Scalar` operands, so they must compile against `Scalar`'s
   `operator>=/</<=` + `operator<<`. Both `DO_ASSERTIONS=1` engine builds link
   clean with the fix at all 11 swapped sites:
   - `task build` (native, `build_game.sh`, `-DDO_ASSERTIONS=1 -DSCALAR_TYPE_FLOAT`) → `engine/wf_game` linked.
   - `cmake --build build --target wfengine` (`DO_ASSERTIONS=1`) → `libwfengine.a` linked.

2. **No-abort + correct range — established by construction + a regression assert.**
   With the fix, `RangeCheckScalar(Scalar::zero, random_value, Scalar::one)` is
   `random_value >= 0 && random_value < 1` over the *actual* `Scalar` values:
   `random_value = (rand()>>15)/65536 ∈ [0, 65535/65536]`, so both hold — no
   `_sys_assert`. `mathtest.cc`'s loop now asserts this over 1000 draws plus
   `max > 0.5` (the `>>15` range). (A standalone runtime harness compiled the
   fixed `scalar.cc` fine but a minimal *link* isn't practical — `scalar.cc`'s
   `binistream` operators pull the engine's GL/Jolt/zForth graph; `Xvfb` for a
   native run isn't installed here. The two full assertion-build links above
   exercise the same code, so this is a tooling limit, not a gap in the fix.)

3. **Release/web unaffected — PASS.** The web build also carries `DO_ASSERTIONS=1`
   (CMakeLists:151), and the fixed macros compile there too; the demos never call
   `Random`/particles, so behaviour is unchanged. (See the dormancy note above —
   pre-fix, a web level that called `Random` would have aborted.)

**Fix commit:** [`2fe49ef4`](https://github.com/wbniv/WorldFoundry/commit/2fe49ef4) (code + regression test); docs in the follow-up commit.
