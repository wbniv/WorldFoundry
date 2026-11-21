#!/usr/bin/env python3
"""Generate the shared test vectors for the Forth math words.

    python3 tests/gen_forth_math_vectors.py           # rewrite tests/data/forth_math_vectors.{json,inc}
    python3 tests/gen_forth_math_vectors.py --check   # fail if the committed files differ (CI, and a test)

Plan: docs/plans/2026-11-21-forth-trig-words.md, decision D3. The words' contract is "the true value,
rounded to a 32-bit float, within one float ulp or 1e-7, whichever is larger", with no promise at
special points. This file is the contract in executable form: the oracle below is Python's `math`
in double precision, and every implementation of the words (the C++ bridge today, a JavaScript
zForth port if one is ever written) checks itself against the JSON, in any language.

Angles are in revolutions. Inputs are rounded to 32-bit floats first, because that is what a Forth
cell holds. A non-finite argument is a domain error for every word (the strings "inf", "-inf" and
"nan" in the JSON); asin-rev and acos-rev also refuse |x| > 1 + 1e-6 and clamp what lies in the slack;
sqrt refuses a negative; atan2-rev of the zero vector is 0.
"""
from __future__ import annotations

import json
import math
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
                     "and near its poles it returns a large finite number of unspecified size"}


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
    cases = {}
    for word, (arity, fn) in WORDS.items():
        out = []
        pts = inputs[word]
        if arity == 1:
            pts = [(p,) for p in pts] + [(n,) for n in NONFINITE]
        else:
            pts = list(pts) + [(n, 1.0) for n in NONFINITE] + [(1.0, n) for n in NONFINITE]
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
    return {"tolerance": TOLERANCE, "words": cases}


def c_double(v) -> str:
    if v == "nan": return "NAN"
    if v == "inf": return "INFINITY"
    if v == "-inf": return "(-INFINITY)"
    return repr(float(v))


def to_inc(doc) -> str:
    lines = ["// generated by tests/gen_forth_math_vectors.py; do not edit", "// {word, input count, inputs, output count, outputs, is a domain error}"]
    for word, cases in doc["words"].items():
        for c in cases:
            ins = c["in"] + ["0"] * (2 - len(c["in"]))
            if "error" in c:
                outs, n_out, err = ["0", "0"], 0, "true"
            else:
                o = c["out"] if isinstance(c["out"], list) else [c["out"]]
                outs, n_out, err = o + ["0"] * (2 - len(o)), len(o), "false"
            lines.append('{"%s", %d, {%s, %s}, %d, {%s, %s}, %s},' % (word, len(c["in"]), c_double(ins[0]), c_double(ins[1]), n_out,
                                                                        c_double(outs[0]), c_double(outs[1]), err))
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
