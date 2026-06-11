# Web right-turn dead — negative-angle UB in `Scalar::AsUnsignedFraction` (2026-06-12)

**Status:** FIXED [`944cc31b`](https://github.com/wbniv/WorldFoundry/commit/944cc31b) (`wfsource/source/math/scalar.hpi`).

## Symptom

On the web build (`/v2/play/`), the **RIGHT** arrow key did nothing in levels with a
non-zero `turnRate` (snowgoons, moon). LEFT, UP, DOWN all worked. Native builds
turned right fine. Reported repeatedly ("it's only right that doesn't work",
"same no right for snowgoons", "it used to work before we put it on the web").

## Investigation path (and a false premise corrected)

The framing was "the web keyboard delivers RIGHT but it's lost downstream." That
turned out to be **wrong** — measurement overturned it in two steps:

1. **Input delivery is perfect.** Instrumenting `_HALSetJoystickButtons`
   (`WFSET`) and `QInputDigital::update` (`WFUPD`) showed ArrowRight delivers
   `0x2000` (`EJ_BUTTONF_RIGHT`, bit 13) into `_current` on *both* input-device
   instances, byte-identical to LEFT's `0x4000`. Keyboard → HAL → input layer is
   flawless. The bug is **not** input.

2. **The output is asymmetric.** Instrumenting the movement decision
   (`WFVEL`: button word + `turnRate` + `currentDir` + `wheelVelocity`) on
   snowgoons (`turnRate = 0.25`, so LEFT/RIGHT are tank-style *turns*, not
   strafes) showed the heading frozen under RIGHT and rotating under LEFT:

   | Hold | `currentDir` first → last | heading |
   |------|---------------------------|---------|
   | RIGHT | (0.906, −0.423) → (0.906, −0.423) | **frozen — no rotation** |
   | LEFT  | (0.928, −0.374) → (0.111, 0.994)  | rotates ✓ |

   LEFT calls `AddRotation(Euler(0,0, Revolution(+turnRate)))`; RIGHT calls
   `Revolution(−turnRate)`. The only difference is the **sign**.

## Root cause

`movement.cc` builds the right-turn angle as `Angle::Revolution(-turnRate)` — a
**negative** `Scalar` fed into `Angle`. `Angle` is a binary angular measure
(`uint16`, 0…65535 = one revolution), and the conversion runs through
`Scalar::AsUnsignedFraction()`. Its float/double path (authored 2010-05-01):

```cpp
FLOAT_TYPE temp = _value;
temp -= int(_value);              // -0.0125 - 0 = -0.0125  (range (-1,1))
return uint16(temp*SCALAR_ONE_LS);   // uint16(-819.2)  ← negative → unsigned
```

Converting a negative float to an unsigned integer is **undefined behavior** in
C++. clang for WebAssembly emits the *saturating* `i32.trunc_sat_f64_u`, which
**clamps negatives to 0**. So `Angle::Revolution(-turnRate)` produces a
`_value` of **0** → a zero rotation → the right-turn is dead.

## Why dormant since 2010

The same expression "worked" on every earlier target by luck:

- **Fixed-point (PSX, original target):** the `#if SCALAR_TYPE_FIXED` path is
  `return uint16(_value)` — two's-complement truncation of a negative fixed-point
  value yields exactly the correct wrapped BAM value. Negatives wrap for free.
- **Native x86 desktop (float path):** `cvttsd2si`-based `fptoui` of a small
  negative also wraps to a large `uint16` — the correct "turn the other way"
  angle. UB, but benign here.
- **WebAssembly (float path):** saturating `fptoui` clamps to 0 — the one
  platform where the UB actually bites.

And it needed a negative angle to *reach* the conversion. Only two call sites in
the engine pass a negative revolution — both are the RIGHT-turn branches in
`movement.cc` (:315, :777) — and only on a level with `turnRate != 0`. The web
demos (snowgoons, moon) are the first such combination exercised on wasm.

## Fix

Wrap the negative fraction into `[0,1)` before the unsigned convert — modular BAM
semantics, matching what the fixed-point path gets for free:

```diff
    temp -= int(_value);                // remove whole part → (-1,1)
+   if (temp < 0)
+      temp += 1;                       // wrap into [0,1)
    return uint16(temp*SCALAR_ONE_LS);
```

Verified on snowgoons after the fix: RIGHT now rotates the heading every frame,
in the opposite direction from LEFT (RIGHT clockwise, LEFT counter-clockwise).
Regression assert added in `math/mathtest.cc` (`-0.25 rev == 0.75 rev == 49152`).

## Note: this was masked by a separate stale-cache issue

The user's live testing was *also* confounded by browser cache serving a stale
`wf_game.{js,wasm,data}` trio (fixed filenames + `stale-while-revalidate`), which
is why "it used to work" and the new-levels-are-black reports coincided. That is a
distinct problem tracked under cache-busting the bundle; the right-turn bug is a
genuine engine defect independent of caching.
