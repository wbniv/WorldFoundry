# Forth math words

The zForth bridge provides the trigonometry, the square root, rounding, integer bit counts, exponentials, logarithms and the hyperbolic functions: 36 words. They exist because zForth has no floating-point maths of its own, and because a hand-rolled approximation in a level script (the parabola `tk-sin` is about 0.16 % off; a `floor` that subtracts 1 until it is below 1 runs once per unit of its argument) is slower to write and less accurate than the hardware's own function. Plans: [Forth trig words](plans/2026-11-21-forth-trig-words.md) (the first nine) and [Forth math words, part 2](plans/2026-11-26-forth-math-words.md) (the other 27).

## Units

**Every angle is in revolutions**: 1.0 is a full turn, 0.25 a right angle, matching the engine's Euler angles `a`, `b` and `c`. There are no radian or degree words. `: deg>rev 360 / ;` is one line if you need it.

## The words

### Trigonometry and the square root

| Word | Stack effect | Result |
|---|---|---|
| `sin-rev` | `( rev -- sin )` | sine, −1 to 1 |
| `cos-rev` | `( rev -- cos )` | cosine, −1 to 1 |
| `tan-rev` | `( rev -- tan )` | tangent; very large near ¼ and ¾ of a turn |
| `asin-rev` | `( x -- rev )` | −¼ to ¼ |
| `acos-rev` | `( x -- rev )` | 0 to ½ |
| `atan-rev` | `( x -- rev )` | −¼ to ¼ |
| `atan2-rev` | `( y x -- rev )` | −½ to ½; `y` first, as in C |
| `sincos-rev` | `( rev -- sin cos )` | both, from one call; the cosine is on top |
| `sqrt` | `( x -- r )` | 0 or more |

`atan2-rev` gives the heading of the vector (x, y) in the engine's convention: 0 along +x, ¼ along +y, ½ along −x. A zero vector has no heading and gives 0.

### Rounding and the other exact words

Each of these gives the exact answer, so it gives the same bits on every machine.

| Word | Stack effect | Result |
|---|---|---|
| `floor` | `( x -- ⌊x⌋ )` | the largest whole number not above x: `-2.5 floor` is −3 |
| `ceil` | `( x -- ⌈x⌉ )` | the smallest whole number not below x |
| `trunc` | `( x -- r )` | toward zero: `-2.7 trunc` is −2 |
| `round` | `( x -- r )` | to the nearest whole number, ties away from zero: `2.5 round` is 3, `-2.5 round` is −3 |
| `roundeven` | `( x -- r )` | to the nearest whole number, ties to even: `2.5 roundeven` is 2, `3.5 roundeven` is 4. No bias over many values |
| `fma` | `( a b c -- a·b+c )` | a × b + c with one rounding, not two |
| `copysign` | `( x y -- r )` | the size of x with the sign of y; `-0` counts as negative |
| `fmod` | `( x y -- r )` | x − n·y with n truncated toward zero, so the result takes **x's** sign: `-7 3 fmod` is −1. For a remainder that takes the divisor's sign (wrapping a negative time into 0 to 60), write `over over / floor * -` |

### Integer bits

The argument must be a whole number from 0 to 2²⁴ = 16,777,216, the range a float cell holds exactly. The count is over 32 bits.

| Word | Stack effect | Result |
|---|---|---|
| `popcount` | `( n -- bits )` | how many bits are set: `255 popcount` is 8 |
| `clz` | `( n -- zeros )` | leading zero bits in 32: `1 clz` is 31, `0 clz` is 32. The integer log2 of n is `31 swap clz -` |
| `ctz` | `( n -- zeros )` | trailing zero bits: `40 ctz` is 3, `0 ctz` is 32 |

### Exponentials, logarithms and the hyperbolic functions

| Word | Stack effect | Result |
|---|---|---|
| `exp` | `( x -- eˣ )` | refused above about 88.7, where the result no longer fits a cell |
| `expm1` | `( x -- eˣ−1 )` | keeps its digits for tiny x, where `exp 1 -` gives 0: `1 − e^(−k·dt)` is `k dt * negate expm1 negate` |
| `exp2` | `( x -- 2ˣ )` | refused at 128 and above |
| `pow` | `( x y -- xʸ )` | x to the power y; a negative x needs a whole y |
| `ln` | `( x -- ln x )` | the natural logarithm; x must be above 0 |
| `log1p` | `( x -- ln(1+x) )` | the inverse of `expm1`; x must be above −1 |
| `log2` | `( x -- r )` | base 2; x must be above 0 |
| `log10` | `( x -- r )` | base 10; x must be above 0 |
| `cbrt` | `( x -- ∛x )` | the cube root, negative for a negative x |
| `hypot` | `( x y -- √(x²+y²) )` | without the overflow of squaring first |
| `sinh` | `( x -- r )` | hyperbolic sine |
| `cosh` | `( x -- r )` | hyperbolic cosine (a hanging cable is a cosh) |
| `tanh` | `( x -- r )` | −1 to 1: a soft limit |
| `asinh` | `( x -- r )` | inverse of `sinh` |
| `acosh` | `( x -- r )` | inverse of `cosh`, 0 or more; x must be 1 or more |
| `atanh` | `( x -- r )` | inverse of `tanh`; x must be strictly between −1 and 1 |

**Names.** Cells are reals, so the words drop ANS Forth's `F` prefix, as `sqrt` already does: `FEXP`, `FLN`, `FEXPM1`, `FLNP1` and `F**` are `exp`, `ln`, `expm1`, `log1p` and `pow`. There is **no `log`**: it means the natural logarithm to some readers and base 10 to others (ANS `FLOG` is base 10), so the words say which: `ln`, `log2`, `log10`. `fmod` sits beside the prelude's integer `mod` (a `%`), and `round` beside `roundeven`.

## What you can rely on

- **Each result is the true value, rounded to a 32-bit float** (the size of a zForth cell), within one float ulp or 1 × 10⁻⁷, whichever is larger. The maths runs in the widest type the chip does natively: `double` on phones and desktops. The exponentials, logarithms and hyperbolic functions are held to one float ulp with no absolute floor (two on a chip whose FPU is single-precision).
- **The rounding words, `fma`, `copysign`, `fmod` and the integer-bit words are exact**: the same bits on every machine, whether the answer comes from one instruction or from a library routine. `fma` rounds once, straight into the cell.
- **Nothing is promised at special points.** `0.5 sin-rev` is about 1.2 × 10⁻¹⁶, not 0, and `0.25 cos-rev` is about 6 × 10⁻¹⁷. Do not compare a result with 0 for equality, as you would not with any float.
- **`tan-rev` has no error at its poles.** `0.25 tan-rev` is about 1.6 × 10¹⁶. A script that cannot tolerate a huge value must not call it there. On a chip whose FPU is single-precision (the maths then runs in `float`) it is only specified where its magnitude is at most 1000, with a relative tolerance of 10⁻⁵.
- **A domain error stops the script's frame, loudly.** The word and its argument go to stderr (for example `zforth: asin-rev: argument is outside -1 to 1 (argument 2)`), the frame's script aborts with the VM's external-abort code, and the next frame runs clean. The errors are:
    - any argument that is not a finite number (infinity or not-a-number), for every word;
    - any result that is not a finite number in a cell (`89 exp`, `10 39 pow`, `3e38 3e38 hypot`: each fits a `double` but not a float);
    - `asin-rev` or `acos-rev` of a number outside −1 to 1, with one tolerance: up to 1 × 10⁻⁶ past 1 is clamped, because the dot product of two unit vectors in a 32-bit cell is often 1.0000001;
    - `sqrt` of a negative number;
    - `fmod` by zero;
    - `popcount`, `clz` or `ctz` of anything but a whole number from 0 to 16,777,216;
    - `pow` of a negative number to a power that is not whole, or of zero to a negative power;
    - `ln`, `log2` or `log10` of zero or less; `log1p` of −1 or less; `acosh` of less than 1; `atanh` of −1 or less, or 1 or more.

    A word of two or three arguments logs them all, in stack order: `zforth: pow: negative base with a non-integer exponent (arguments -8 0.5)`.

## Examples

```forth
\ the heading from the player to a target, in revolutions, then a unit vector along it
: heading ( dx dy -- rev ) swap atan2-rev ;      \ atan2-rev wants y first: dy dx
: aim ( rev -- x y ) sincos-rev swap ;           \ sin cos -> cos sin, i.e. x y

\ the distance between two points
: dist ( dx dy -- d ) dup * swap dup * + sqrt ;      \ or: hypot

\ the fraction of a value, for any sign, and a remainder that takes the divisor's sign
: frac ( x -- f ) dup floor - ;
: wrap ( a b -- r ) over over / floor * - ;          \ -10 60 wrap is 50; -10 60 fmod is -10

\ linear interpolation with one rounding
: lerp ( a b t -- x ) >r over - r> swap rot fma ;    \ t*(b-a) + a

\ exponential approach to a target, frame-rate independent
: approach ( x target k dt -- x' ) * negate expm1 negate >r over - r> * + ;
```

## Which functions the hardware does

Copied from the [part 2 plan](plans/2026-11-26-forth-math-words.md#which-functions-the-hardware-does). **✓** one instruction at the baseline our build targets; **2** or **3**, that many instructions; **◐** the chip has the instruction but our baseline does not let the compiler use it (on the PC, glibc's run-time dispatch, IFUNC, reaches it through a function call: `floorf`, `ceilf`, `truncf`, `rintf` and `fmaf` are IFUNC symbols in glibc 2.43, and `roundf` is not); **✗** a software routine.

| Word | x86‑64 PC (as built) | AArch64: Pixel, tablet, iOS | Chromecasts (`armeabi-v7a`, as built) | Chromecasts if built for ARMv8 32-bit | WebAssembly |
|---|---|---|---|---|---|
| `sqrt` | ✓ `sqrtss` | ✓ `fsqrt` | ✓ `vsqrt` | ✓ | ✓ `f32.sqrt` |
| `min` `max` (prelude) | ✓ `minss` `maxss` | ✓ `fminnm` `fmaxnm` | ✓ `vmin` `vmax` (NEON) | ✓ | ✓ `f32.min` `f32.max` |
| `abs` `negate` (prelude) | ✓ a mask | ✓ `fabs` `fneg` | ✓ `vabs` `vneg` | ✓ | ✓ `f32.abs` `f32.neg` |
| **`copysign`** | 3 (masks) | 2 (`bit` with a mask) | 2 | 2 | ✓ `f32.copysign` |
| **`floor` `ceil` `trunc`** | ◐ `roundss` (SSE4.1) via IFUNC | ✓ `frintm` `frintp` `frintz` | ✗ software | ✓ `vrintm` `vrintp` `vrintz` | ✓ `f32.floor` `ceil` `trunc` |
| **`roundeven`** (ties to even) | ◐ `roundss` via `rintf` IFUNC | ✓ `frintn` | ✗ | ✓ `vrintn` | ✓ `f32.nearest` |
| **`round`** (ties away from zero) | ✗ a short sequence; `roundf` has no hardware path | ✓ `frinta` | ✗ | ✓ `vrinta` | ✗ a sequence |
| **`fma`** (a·b + c, one rounding) | ◐ `vfmadd` (FMA3) via IFUNC | ✓ `fmadd` | ✗ software: correct, slow | ✓ `vfma` (VFPv4) | ✗ software; only relaxed SIMD has it |
| **`fmod`** | ✗ | ✗ | ✗ | ✗ | ✗ |
| **`popcount`** | ◐ `popcnt` (x86‑64‑v2); a sequence at baseline | 3 (`cnt` + `addv`, NEON) | 2–3 (`vcnt` + `vpaddl`) | 2–3 | ✓ `i32.popcnt` |
| **`clz`** | ◐ `lzcnt` (v3); 2 at baseline (`bsr`) | ✓ `clz` | ✓ `clz` | ✓ | ✓ `i32.clz` |
| **`ctz`** | ◐ `tzcnt` (v3); 2 at baseline (`bsf`) | 2 (`rbit` + `clz`) | 2 (`rbit` + `clz`) | 2 | ✓ `i32.ctz` |
| **`exp` … `atanh`**, and the trig words | ✗ `libm` (glibc picks FMA-tuned versions of `expf`, `logf`, `exp2f` and `sinf`: IFUNC, still software) | ✗ `libm` (bionic) | ✗ | ✗ | ✗ `libm` (Emscripten) |

Hardware support buys exactness and agreement between machines, not speed: every word costs the VM's dispatch, a syscall and a table lookup either way. IEEE 754 requires the rounding words, `fma`, `copysign` and `fmod` to be exact, so every conforming machine gives the same bits; the exponentials and logarithms are only recommended, so two machines' libraries may differ in the last bit of a `double`, which almost never survives the rounding into a float cell.

## Where it lives and how it is tested

- The maths: [`engine/stubs/forth_math.hpp`](../engine/stubs/forth_math.hpp), header-only and free of engine types.
- The zForth glue and the one table of words and syscalls (`ZF_SYSCALL_USER` + 73 to 108): [`engine/stubs/forth_math_zforth.hpp`](../engine/stubs/forth_math_zforth.hpp). It is registered by `scripting_zforth.cc`, and `tests/test_forth_math_docs.py` fails if this page's table and that one differ.
- Shared test vectors: `tests/data/forth_math_vectors.json`, written by `tests/gen_forth_math_vectors.py` from Python's `math` in double precision. They are language-neutral, so any other implementation of these words can check itself against them.
- `task test-forth-math` runs the C++ unit test (every vector, identities, domain errors, 100 000 random arguments of every word against `long double`, the exact words compared bit for bit), built for `double` and for `float`. `python3 tests/verify_forth_math.py` runs every word in the real zForth VM. `tests/verify_forth_math_engine.py` runs every word through the engine's own dispatcher.

A Forth script is one language of several the engine can host; Lua and JavaScript have their own `Math`, so these words exist only for zForth. See [scripting languages](scripting-languages.md).
