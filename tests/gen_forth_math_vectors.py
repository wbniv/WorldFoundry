#!/usr/bin/env python3
"""Generate the shared test vectors for the Forth math words.

    python3 tests/gen_forth_math_vectors.py           # rewrite tests/data/forth_math_vectors.{json,inc}
    python3 tests/gen_forth_math_vectors.py --check   # fail if the committed files differ (CI, and a test)

Plans: docs/plans/2026-11-21-forth-trig-words.md, decision D3 (the trigonometry and sqrt), and
docs/plans/2026-11-26-forth-math-words.md (27 more words: rounding, integer bits, exponentials and
logarithms). The words' contract is "the true value,
rounded to a 32-bit float, within one float ulp or 1e-7, whichever is larger", with no promise at
special points. This file is the contract in executable form: the oracle below is Python's `math`
in double precision, and every implementation of the words (the C++ bridge today, a JavaScript
zForth port if one is ever written) checks itself against the JSON, in any language.

Angles are in revolutions. Inputs are rounded to 32-bit floats first, because that is what a Forth
cell holds. A non-finite argument is a domain error for every word (the strings "inf", "-inf" and
"nan" in the JSON); asin-rev and acos-rev also refuse |x| > 1 + 1e-6 and clamp what lies in the slack;
sqrt refuses a negative; atan2-rev of the zero vector is 0.

The second plan's words refuse a non-finite argument, a result that does not fit a float cell, and
the domain errors in its table. Its groups A (floor ... fmod) and B (popcount clz ctz) are exact:
their expected outputs are the exact answers, rounded once to float, and the tests compare bits.
fma's oracle is exact rational arithmetic, rounded once to float (Python's math.fma would round to
double first, and is new in 3.13).
"""
from __future__ import annotations

import json
import math
from fractions import Fraction
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JSON_PATH = HERE / "data" / "forth_math_vectors.json"
INC_PATH = HERE / "data" / "forth_math_vectors.inc"

TWO_PI = 2.0 * math.pi
SLACK = 1e-6
TOLERANCE = {"ulp": 1, "abs": 1e-7, "abs_single_fpu": 6e-7,
             "single_fpu_tan": {"rel": 1e-5, "only_where_abs_value_at_most": 1000},
             "note": "pass if |got - want| <= max(abs, one float ulp of want). A chip whose FPU is single-precision "
                     "(Real = float) uses abs_single_fpu instead, because it computes the angle 2*pi*x in float; for the "
                     "same reason tan-rev is only specified there where |tan| <= 1000, with relative tolerance rel, "
                     "and near its poles it returns a large finite number of unspecified size",
             "exact_words": "the words listed under 'exact' must match their outputs bit for bit, in every mode",
             "random_libm_ulp": 1, "random_libm_ulp_single_fpu": 2,
             "random_note": "the unit test's random arguments hold the second plan's libm words to one float ulp of a long "
                            "double reference with no absolute floor; a single-precision FPU's own float libm gets two"}


def f32(x: float) -> float:
    return struct.unpack("f", struct.pack("f", x))[0]


def frac(x: float) -> float:
    return x - math.floor(x)


class Domain(Exception):
    pass


def finite(*xs: float) -> None:
    if not all(math.isfinite(x) for x in xs):
        raise Domain


def sin_rev(x): finite(x); return math.sin(TWO_PI * frac(x))
def cos_rev(x): finite(x); return math.cos(TWO_PI * frac(x))
def tan_rev(x): finite(x); return math.tan(TWO_PI * frac(x))
def sincos_rev(x): finite(x); a = TWO_PI * frac(x); return (math.sin(a), math.cos(a))


def asin_rev(x):
    if not abs(x) <= 1 + SLACK: raise Domain
    return math.asin(max(-1.0, min(1.0, x))) / TWO_PI


def acos_rev(x):
    if not abs(x) <= 1 + SLACK: raise Domain
    return math.acos(max(-1.0, min(1.0, x))) / TWO_PI


def atan_rev(x): finite(x); return math.atan(x) / TWO_PI
def atan2_rev(y, x): finite(y, x); return math.atan2(y, x) / TWO_PI


def sqrt_(x):
    if not x >= 0: raise Domain
    finite(x)
    return math.sqrt(x)


# --- the second plan's words ---------------------------------------------------------------------

FLT_MAX = 3.4028234663852886e38


def f32_or_inf(x: float) -> float:
    try:
        return f32(x)
    except OverflowError:
        return math.copysign(math.inf, x)


def fits(r: float) -> float:
    """The result as the cell holds it; a result that is not finite there is refused."""
    if not math.isfinite(f32_or_inf(r)):
        raise Domain
    return r


def guarded(fn):
    """A libm call whose overflow is a refused result, not a Python exception."""
    def call(*xs):
        finite(*xs)
        try:
            return fits(fn(*xs))
        except OverflowError:
            raise Domain
    return call


def signed(fn, x):
    """An integer rounding keeps x's sign, so ceil(-0.5) is -0, as in C (Python's ints have no -0)."""
    return math.copysign(float(fn(x)), x)


def round_away(x):
    return math.copysign(math.floor(abs(x) + 0.5), x)


def round_even(x):
    return math.copysign(float(round(x)), x)


def q_to_f32(q: Fraction) -> float:
    """An exact rational, rounded once to the nearest float (ties to even)."""
    if q == 0:
        return 0.0
    sign, a = (-1.0 if q < 0 else 1.0), abs(q)
    e = a.numerator.bit_length() - a.denominator.bit_length()       # 2^e is within a factor 2 of a
    while a >= Fraction(2) ** (e + 1):
        e += 1
    while a < Fraction(2) ** e:
        e -= 1
    step = Fraction(2) ** max(e - 23, -149)                          # the float spacing at a
    n = a / step
    whole = n.numerator // n.denominator
    rest = n - whole
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and whole % 2 == 1):
        whole += 1
    v = float(whole * step)
    if v > FLT_MAX:
        return sign * math.inf
    return sign * v


def fma_(a, b, c):
    finite(a, b, c)
    r = q_to_f32(Fraction(a) * Fraction(b) + Fraction(c))
    if not math.isfinite(r):
        raise Domain
    return r


def copysign_(x, y): finite(x, y); return math.copysign(x, y)


def fmod_(x, y):
    finite(x, y)
    if y == 0: raise Domain
    return math.fmod(x, y)


def whole(n):
    if not (n >= 0 and n <= 16777216 and n == math.floor(n)): raise Domain
    return int(n)


def popcount_(n): return float(bin(whole(n)).count("1"))
def clz_(n): k = whole(n); return float(32 - k.bit_length())
def ctz_(n): k = whole(n); return 32.0 if k == 0 else float((k & -k).bit_length() - 1)


def pow_(x, y):
    finite(x, y)
    if x < 0 and y != math.floor(y): raise Domain
    if x == 0 and y < 0: raise Domain
    try:
        return fits(math.pow(x, y))
    except OverflowError:
        raise Domain


def positive(fn):
    def call(x):
        finite(x)
        if not x > 0: raise Domain
        return fits(fn(x))
    return call


def log1p_(x):
    finite(x)
    if not x > -1: raise Domain
    return fits(math.log1p(x))


def acosh_(x):
    finite(x)
    if not x >= 1: raise Domain
    return fits(math.acosh(x))


def atanh_(x):
    finite(x)
    if not abs(x) < 1: raise Domain
    return fits(math.atanh(x))


def exact(fn):
    def call(*xs):
        finite(*xs)
        return fits(fn(*xs))
    return call


NEW_WORDS = {
    "floor": (1, exact(lambda x: signed(math.floor, x))), "ceil": (1, exact(lambda x: signed(math.ceil, x))),
    "trunc": (1, exact(lambda x: signed(math.trunc, x))), "round": (1, exact(round_away)), "roundeven": (1, exact(round_even)),
    "fma": (3, fma_), "copysign": (2, copysign_), "fmod": (2, fmod_),
    "popcount": (1, popcount_), "clz": (1, clz_), "ctz": (1, ctz_),
    "exp": (1, guarded(math.exp)), "expm1": (1, guarded(math.expm1)), "exp2": (1, guarded(lambda x: math.pow(2.0, x))),
    "pow": (2, pow_), "ln": (1, positive(math.log)), "log1p": (1, log1p_), "log2": (1, positive(math.log2)),
    "log10": (1, positive(math.log10)), "cbrt": (1, guarded(math.cbrt)), "hypot": (2, guarded(math.hypot)),
    "sinh": (1, guarded(math.sinh)), "cosh": (1, guarded(math.cosh)), "tanh": (1, guarded(math.tanh)),
    "asinh": (1, guarded(math.asinh)), "acosh": (1, acosh_), "atanh": (1, atanh_),
}
EXACT_WORDS = ["floor", "ceil", "trunc", "round", "roundeven", "fma", "copysign", "fmod", "popcount", "clz", "ctz"]


def new_inputs(rng: random.Random):
    rounding = [-2.5, -1.5, -0.5, -0.0, 0.0, 0.5, 1.5, 2.5, 3.5, -3.7, 3.7, 0.49999997, -0.49999997, 1e-30, -1e-30,
                8388607.5, -8388607.5, 16777215.0, 3e38, -3e38, 1e7 + 1]
    rounding_r = lambda: rounding + [rng.uniform(-100, 100) for _ in range(60)]
    big = 1.0 + 2.0 ** -12                                           # big * big + 1e-24 rounds twice through double
    fma = [(2.0, 3.0, 4.0), (big, big, 1e-24), (big, big, -1e-24), (1.0, 1.0, -1.0), (-2.0, 0.5, 1.0), (0.0, 5.0, -0.0),
           (3e38, 10.0, 0.0), (3e38, 1.0, 3e38), (1e-30, 1e-30, 0.0), (0.1, 10.0, -1.0)]
    fma += [(rng.uniform(-10, 10), rng.uniform(-10, 10), rng.uniform(-10, 10)) for _ in range(60)]
    copysign = [(1.0, -0.0), (-2.0, 0.0), (3.0, -5.0), (0.0, -1.0), (-0.0, 1.0), (1e30, -1e-30), (-7.0, -7.0)]
    copysign += [(rng.uniform(-10, 10), rng.uniform(-10, 10)) for _ in range(60)]
    fmod = [(7.0, 3.0), (-7.0, 3.0), (7.0, -3.0), (-7.0, -3.0), (5.5, 2.0), (1.0, 0.0), (0.0, 1.0), (-0.0, 1.0), (1e30, 3.0),
            (0.3, 0.1), (1e-30, 1.0), (1.0, -0.0), (370.5, 360.0), (-10.25, 360.0)]
    fmod += [(rng.uniform(-100, 100), rng.uniform(-10, 10)) for _ in range(60)]
    bits = [0.0, -0.0, 1.0, 2.0, 3.0, 255.0, 256.0, 1023.0, 65535.0, 65536.0, 16777215.0, 16777216.0, 16777218.0,
            -1.0, 0.5, 2.5, 1e30, -16777216.0]
    bits_r = lambda: bits + [float(rng.randint(0, 2 ** 24)) for _ in range(60)]
    expo = [-1e30, -100.0, -87.0, -10.0, -1.0, -1e-7, -1e-30, 0.0, 1e-30, 1e-7, 0.5, 1.0, 10.0, 88.0, 88.7, 89.0, 127.0, 128.0, 1e30]
    expo_r = lambda: expo + [rng.uniform(-20, 20) for _ in range(60)]
    powp = [(2.0, 10.0), (2.0, 0.5), (-8.0, 1 / 3), (-2.0, 3.0), (-2.0, 2.0), (0.0, 0.0), (0.0, -1.0), (-0.0, -1.0), (0.0, 2.0),
            (10.0, 39.0), (10.0, 38.0), (1e-30, 2.0), (2.0, -150.0), (-1.0, 1e30), (4.0, 0.5), (1.0, 1e30), (-3.0, -2.0),
            (0.5, -127.0), (0.5, -128.0)]
    powp += [(rng.uniform(0, 10), rng.uniform(-5, 5)) for _ in range(60)]
    logs = [1e-30, 1e-7, 0.5, 1.0, 2.0, 10.0, 1000.0, 1e30, 3e38, 0.0, -0.0, -1.0, -1e-30]
    logs_r = lambda: logs + [rng.uniform(0.001, 1000) for _ in range(60)]
    log1p = [-1.0, -1.5, -0.99999994, -0.5, -1e-30, 0.0, 1e-30, 1e-7, 1.0, 1e30, 3e38]
    log1p += [rng.uniform(-0.99, 100) for _ in range(60)]
    cbrt = [-27.0, -8.0, -1e-30, -0.0, 0.0, 1e-30, 8.0, 27.0, 3e38, -3e38, 2.0]
    cbrt += [rng.uniform(-1000, 1000) for _ in range(60)]
    hyp = [(3.0, 4.0), (0.0, 0.0), (-3.0, 4.0), (3e38, 3e38), (2e38, 2e38), (1e-30, 1e-30), (1e30, 1e30), (5.0, -12.0)]
    hyp += [(rng.uniform(-100, 100), rng.uniform(-100, 100)) for _ in range(60)]
    reals = [-1e30, -20.0, -1.0, -1e-30, 0.0, 1e-30, 1e-7, 1.0, 20.0, 1e30]
    reals_r = lambda: reals + [rng.uniform(-20, 20) for _ in range(60)]
    acosh = [1.0, 1.0000001, 2.0, 10.0, 1e30, 3e38, 0.99999994, 0.0, -1.0]
    acosh += [rng.uniform(1, 100) for _ in range(60)]
    atanh = [-0.99999994, -0.5, -1e-30, 0.0, 0.5, 0.99999994, 1.0, -1.0, 2.0]
    atanh += [rng.uniform(-0.999, 0.999) for _ in range(60)]
    return {"floor": rounding_r(), "ceil": rounding_r(), "trunc": rounding_r(), "round": rounding_r(), "roundeven": rounding_r(),
            "fma": fma, "copysign": copysign, "fmod": fmod, "popcount": bits_r(), "clz": bits_r(), "ctz": bits_r(),
            "exp": expo_r(), "expm1": expo_r(), "exp2": expo_r(), "pow": powp, "ln": logs_r(), "log1p": log1p, "log2": logs_r(),
            "log10": logs_r(), "cbrt": cbrt, "hypot": hyp, "sinh": expo_r(), "cosh": expo_r(), "tanh": reals_r(),
            "asinh": reals_r(), "acosh": acosh, "atanh": atanh}


WORDS = {"sin-rev": (1, sin_rev), "cos-rev": (1, cos_rev), "tan-rev": (1, tan_rev), "asin-rev": (1, asin_rev),
         "acos-rev": (1, acos_rev), "atan-rev": (1, atan_rev), "atan2-rev": (2, atan2_rev),
         "sincos-rev": (1, sincos_rev), "sqrt": (1, sqrt_)}

NONFINITE = [float("inf"), float("-inf"), float("nan")]


def turn_inputs(rng: random.Random):
    xs = [k / 8 for k in range(-16, 17)]                                   # every eighth turn from -2 to 2
    xs += [1e-9, -1e-9, 1e-30, 1e6 + 0.25, -1e6 - 0.125, 375000.0, 0.1, 0.2, 0.3, 0.7, 0.9, 0.99999994, 1.0000001]
    xs += [0.25 - 1e-6, 0.25 + 1e-6, 0.75 - 1e-6, 0.75 + 1e-6]              # either side of the tangent's poles
    xs += [rng.uniform(-4, 4) for _ in range(60)]
    return xs


def unit_inputs(rng: random.Random):
    xs = [-1.0, -0.5, 0.0, 0.5, 1.0, 1.0000005, -1.0000005, 1.00001, -1.00001, -1.5, 2.0, 1e-30, 0.999999, -0.999999]
    xs += [rng.uniform(-1, 1) for _ in range(60)]
    return xs


def real_inputs(rng: random.Random):
    xs = [-1e30, -100.0, -1.0, -0.5, 0.0, 0.5, 1.0, 100.0, 1e30, 1e-30, -1e-30, 1.7320508]
    xs += [rng.uniform(-20, 20) for _ in range(60)]
    return xs


def atan2_inputs(rng: random.Random):
    pts = []
    for mag in (1e-20, 0.5, 1.0, 1e20):
        for dx, dy in ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)):
            pts.append((dy * mag, dx * mag))
    pts += [(0.0, 0.0), (0.0, -1.0), (-0.0, -1.0), (0.0, 1.0), (-0.0, 1.0), (1.0, 0.0), (1.0, 3.0), (-2.0, 0.5)]
    pts += [(rng.uniform(-5, 5), rng.uniform(-5, 5)) for _ in range(60)]
    return pts


def sqrt_inputs(rng: random.Random):
    xs = [0.0, -0.0, 1e-30, 0.25, 1.0, 2.0, 1e30, 3.0e38, -1.0, -1e-30]
    xs += [rng.uniform(0, 100) for _ in range(60)]
    return xs


def encode(x: float):
    if math.isnan(x): return "nan"
    if math.isinf(x): return "inf" if x > 0 else "-inf"
    return x


def build():
    rng = random.Random(20261121)
    inputs = {"sin-rev": turn_inputs(rng), "cos-rev": turn_inputs(rng), "tan-rev": turn_inputs(rng), "sincos-rev": turn_inputs(rng),
              "asin-rev": unit_inputs(rng), "acos-rev": unit_inputs(rng), "atan-rev": real_inputs(rng),
              "atan2-rev": atan2_inputs(rng), "sqrt": sqrt_inputs(rng)}
    inputs.update(new_inputs(random.Random(20261126)))       # its own generator: the trig vectors stay as they were
    cases = {}
    for word, (arity, fn) in {**WORDS, **NEW_WORDS}.items():
        out = []
        pts = inputs[word]
        if arity == 1:
            pts = [(p,) for p in pts] + [(n,) for n in NONFINITE]
        elif arity == 2:
            pts = list(pts) + [(n, 1.0) for n in NONFINITE] + [(1.0, n) for n in NONFINITE]
        else:
            pts = list(pts) + [(n, 1.0, 1.0) for n in NONFINITE] + [(1.0, n, 1.0) for n in NONFINITE] + [(1.0, 1.0, n) for n in NONFINITE]
        for p in pts:
            p = tuple(f32(v) for v in p)
            case = {"in": [encode(v) for v in p]}
            try:
                r = fn(*p)
                case["out"] = [encode(f32(v)) for v in r] if isinstance(r, tuple) else encode(f32(r))
            except Domain:
                case["error"] = "domain"
            out.append(case)
        cases[word] = out
    return {"tolerance": TOLERANCE, "exact": EXACT_WORDS, "words": cases}


def c_double(v) -> str:
    if v == "nan": return "NAN"
    if v == "inf": return "INFINITY"
    if v == "-inf": return "(-INFINITY)"
    return repr(float(v))


def to_inc(doc) -> str:
    lines = ["// generated by tests/gen_forth_math_vectors.py; do not edit", "// {word, input count, inputs, output count, outputs, is a domain error}"]
    for word, cases in doc["words"].items():
        for c in cases:
            ins = c["in"] + ["0"] * (3 - len(c["in"]))
            if "error" in c:
                outs, n_out, err = ["0", "0"], 0, "true"
            else:
                o = c["out"] if isinstance(c["out"], list) else [c["out"]]
                outs, n_out, err = o + ["0"] * (2 - len(o)), len(o), "false"
            lines.append('{"%s", %d, {%s, %s, %s}, %d, {%s, %s}, %s},' % (word, len(c["in"]), c_double(ins[0]), c_double(ins[1]),
                                                                            c_double(ins[2]), n_out, c_double(outs[0]), c_double(outs[1]), err))
    return "\n".join(lines) + "\n"


def main() -> int:
    doc = build()
    js = json.dumps(doc, indent=1) + "\n"
    inc = to_inc(doc)
    if "--check" in sys.argv:
        ok = JSON_PATH.exists() and INC_PATH.exists() and JSON_PATH.read_text() == js and INC_PATH.read_text() == inc
        print("vectors up to date" if ok else "vectors are STALE: run python3 tests/gen_forth_math_vectors.py")
        return 0 if ok else 1
    JSON_PATH.parent.mkdir(exist_ok=True)
    JSON_PATH.write_text(js)
    INC_PATH.write_text(inc)
    total = sum(len(v) for v in doc["words"].values())
    print(f"wrote {total} cases for {len(doc['words'])} words to {JSON_PATH.name} and {INC_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
