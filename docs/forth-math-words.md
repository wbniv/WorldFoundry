# Forth math words

The zForth bridge provides the trigonometry and the square root. They exist because zForth has no floating-point maths of its own, and because a hand-rolled approximation in a level script (the parabola `tk-sin` is about 0.16 % off) is slower to write and less accurate than the hardware's own function. Plan: [Forth math words](plans/2026-11-21-forth-trig-words.md).

## Units

**Every angle is in revolutions**: 1.0 is a full turn, 0.25 a right angle, matching the engine's Euler angles `a`, `b` and `c`. There are no radian or degree words. `: deg>rev 360 / ;` is one line if you need it.

## The words

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

## What you can rely on

- **Each result is the true value, rounded to a 32-bit float** (the size of a zForth cell), within one float ulp or 1 × 10⁻⁷, whichever is larger. The maths runs in the widest type the chip does natively: `double` on phones and desktops.
- **Nothing is promised at special points.** `0.5 sin-rev` is about 1.2 × 10⁻¹⁶, not 0, and `0.25 cos-rev` is about 6 × 10⁻¹⁷. Do not compare a result with 0 for equality, as you would not with any float.
- **`tan-rev` has no error at its poles.** `0.25 tan-rev` is about 1.6 × 10¹⁶. A script that cannot tolerate a huge value must not call it there. On a chip whose FPU is single-precision (the maths then runs in `float`) it is only specified where its magnitude is at most 1000, with a relative tolerance of 10⁻⁵.
- **A domain error stops the script's frame, loudly.** The word and its argument go to stderr (for example `zforth: asin-rev: argument is outside -1 to 1 (argument 2)`), the frame's script aborts with the VM's external-abort code, and the next frame runs clean. The errors are:
    - any argument that is not a finite number (infinity or not-a-number), for every word;
    - `asin-rev` or `acos-rev` of a number outside −1 to 1, with one tolerance: up to 1 × 10⁻⁶ past 1 is clamped, because the dot product of two unit vectors in a 32-bit cell is often 1.0000001;
    - `sqrt` of a negative number.

## Examples

```forth
\ the heading from the player to a target, in revolutions, then a unit vector along it
: heading ( dx dy -- rev ) swap atan2-rev ;      \ atan2-rev wants y first: dy dx
: aim ( rev -- x y ) sincos-rev swap ;           \ sin cos -> cos sin, i.e. x y

\ the distance between two points
: dist ( dx dy -- d ) dup * swap dup * + sqrt ;
```

## Where it lives and how it is tested

- The maths: [`engine/stubs/forth_math.hpp`](../engine/stubs/forth_math.hpp), header-only and free of engine types.
- The zForth glue and the one table of words and syscalls (`ZF_SYSCALL_USER` + 73 to 81): [`engine/stubs/forth_math_zforth.hpp`](../engine/stubs/forth_math_zforth.hpp). It is registered by `scripting_zforth.cc`, and `tests/test_forth_math_docs.py` fails if this page's table and that one differ.
- Shared test vectors: `tests/data/forth_math_vectors.json`, written by `tests/gen_forth_math_vectors.py` from Python's `math` in double precision. They are language-neutral, so any other implementation of these words can check itself against them.
- `task test-forth-math` runs the C++ unit test (every vector, identities, domain errors, 100 000 random arguments against `long double`), built for `double` and for `float`. `python3 tests/verify_forth_math.py` runs every word in the real zForth VM. `tests/verify_forth_math_engine.py` runs every word through the engine's own dispatcher.

A Forth script is one language of several the engine can host; Lua and JavaScript have their own `Math`, so these words exist only for zForth. See [scripting languages](scripting-languages.md).
