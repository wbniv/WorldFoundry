#!/usr/bin/env python3
"""Re-aim a `.lev`'s Directional key light and retune its Ambient fill.

Background
----------
The 2026-09-20 engine fix (`docs/plans/2026-09-20-engine-multi-directional-light-fix.md`)
corrected an inverted `lightType` enum and, with it, a second defect: the
long-standing authoring recipe ``rotation_euler = (pi/2 - alt, 0, az)`` put the
light's altitude in the **A** euler, and `Light::Set`
(`wfsource/source/game/light.hpi`) reads the direction off the actor's local
**+X** axis — which rotating about X cannot move.  Every level authored that way
has an exactly horizontal beam.

`dir = Rz(C)·Ry(B)·(1,0,0) = (cos B·cos C, cos B·sin C, -sin B)`

and that vector is handed to `RenderCamera::SetDirectionalLight` **unnegated**
(`gfx/camera.hpi:68`), reaching the vertex shader as `u_light_dir` in
``lit += color * max(0, dot(N, u_light_dir))``
(`gfx/glpipeline/backend_modern.cc:86`).  So it is the vector pointing *toward*
the light: a face is lit when its normal aligns with it.  A light that should
come down from above therefore needs **Lz > 0**, i.e. a *negative* B.  This
script takes `--alt` in the natural sense ("the light sits N degrees above the
horizon") and writes `B = -radians(alt)` so the beam comes down.

The sweep that preceded this (`scripts/add_ambient_light.py`) gave these levels
a fullbright `1.0` Ambient that merely reproduced their old (buggy) appearance.
This script is the follow-up art pass: aim the key light at something and drop
the ambient to a real fill value.

Usage
-----
    python3 scripts/relight_level.py wflevels/smb_w1_1/smb_w1_1.lev \\
        --alt 45 --az 250 --key 0.55 --ambient 0.45

    python3 scripts/relight_level.py --show wflevels/*/*.lev

Handles both `.lev` layouts in the tree (the flat one-chunk-per-line form the
Blender exporter writes, and the nested form the original 3ds-Max exporter
wrote).  `--show` is read-only; without it the file is rewritten in place.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_ambient_light import _split_objects, _is_light_block  # noqa: E402

FX = r"(-?\d+\.\d+)\(1\.15\.16\)"

ORIENT_RE = re.compile(
    r"(\"Orientation\"\s*\}\s*\{\s*'DATA'\s+)" + FX + r"(\s+)" + FX + r"(\s+)" + FX
)
LIGHTTYPE_RE = re.compile(r"\"lightType\"\s*\}?\s*\{?\s*'DATA'\s+(\d+)l")


def _colour_re(field: str) -> re.Pattern:
    return re.compile(
        r"(\"" + field + r"\"\s*\}\s*\{\s*'DATA'\s+)" + FX
        + r"(\s*\}\s*\{\s*'STR'\s+\")([^\"]*)(\")"
    )


COLOUR_RES = {f: _colour_re(f) for f in ("lightRed", "lightGreen", "lightBlue")}


def _fx(v: float) -> str:
    return f"{v:.16f}(1.15.16)"


def light_type(block: str) -> int | None:
    m = LIGHTTYPE_RE.search(block)
    return int(m.group(1)) if m else None


def block_name(block: str) -> str:
    m = re.search(r"\{\s*'NAME'\s+\"([^\"]*)\"\s*\}", block)
    return m.group(1) if m else "?"


def read_euler(block: str) -> tuple[float, float, float] | None:
    m = ORIENT_RE.search(block)
    if not m:
        return None
    return float(m.group(2)), float(m.group(4)), float(m.group(6))


def read_colour(block: str) -> tuple[float, float, float]:
    out = []
    for f in ("lightRed", "lightGreen", "lightBlue"):
        m = COLOUR_RES[f].search(block)
        out.append(float(m.group(2)) if m else float("nan"))
    return tuple(out)  # type: ignore[return-value]


def set_euler(block: str, a: float, b: float, c: float) -> str:
    def repl(m: re.Match) -> str:
        return m.group(1) + _fx(a) + m.group(3) + _fx(b) + m.group(5) + _fx(c)

    return ORIENT_RE.sub(repl, block, count=1)


def set_colour(block: str, rgb: tuple[float, float, float]) -> str:
    for field, value in zip(("lightRed", "lightGreen", "lightBlue"), rgb):
        def repl(m: re.Match, value=value) -> str:
            return m.group(1) + _fx(value) + m.group(3) + f"{value:.6f}" + m.group(5)

        block = COLOUR_RES[field].sub(repl, block)
    return block


def direction(alt_deg: float, az_deg: float) -> tuple[float, float, float]:
    """The world-space vector the engine will read, for a given alt/az."""
    b = -math.radians(alt_deg)
    c = math.radians(az_deg)
    return (math.cos(b) * math.cos(c), math.cos(b) * math.sin(c), -math.sin(b))


def _retune(block: str, args: argparse.Namespace) -> str:
    lt = light_type(block)
    if lt == 0:  # Directional key light
        if args.alt is not None:
            block = set_euler(block, 0.0, -math.radians(args.alt), math.radians(args.az))
        if args.key is not None:
            kb = args.key_blue if args.key_blue is not None else args.key
            block = set_colour(block, (args.key, args.key, kb))
    elif lt == 1:  # Ambient fill
        if args.ambient is not None:
            ab = args.ambient_blue if args.ambient_blue is not None else args.ambient
            block = set_colour(block, (args.ambient, args.ambient, ab))
    return block


def process(path: Path, args: argparse.Namespace) -> str:
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    lines = text.splitlines(keepends=True)
    spans = [(s, e) for (s, e) in _split_objects(text)
             if _is_light_block("".join(lines[s:e]))]

    if args.show:
        notes = []
        for s, e in spans:
            block = "".join(lines[s:e])
            kind = {0: "Directional", 1: "Ambient"}.get(light_type(block), "?")
            eul = read_euler(block) or (0.0, 0.0, 0.0)
            deg = [round(math.degrees(v), 2) for v in eul]
            rgb = [round(v, 3) for v in read_colour(block)]
            notes.append(f"  {block_name(block):20s} {kind:12s} eul_deg={deg} rgb={rgb}")
        return f"{path}\n" + "\n".join(notes)

    changed = 0
    # Rewrite from the end so earlier spans stay valid.
    for s, e in reversed(spans):
        block = "".join(lines[s:e])
        new = _retune(block, args)
        if new != block:
            lines[s:e] = [new]
            changed += 1
    if not changed:
        return f"{path}: no change"
    path.write_text("".join(lines), encoding="utf-8", errors="surrogateescape")
    return f"{path}: rewrote {changed} light actor(s)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("levs", nargs="+", type=Path)
    ap.add_argument("--show", action="store_true", help="print each light, change nothing")
    ap.add_argument("--alt", type=float, default=None,
                    help="key-light altitude above the horizon, degrees (written as B=-alt)")
    ap.add_argument("--az", type=float, default=0.0,
                    help="key-light azimuth, degrees (C euler)")
    ap.add_argument("--key", type=float, default=None, help="Directional light grey value")
    ap.add_argument("--key-blue", type=float, default=None, help="override the key's blue")
    ap.add_argument("--ambient", type=float, default=None, help="Ambient light grey value")
    ap.add_argument("--ambient-blue", type=float, default=None,
                    help="override the ambient's blue")
    args = ap.parse_args(argv)

    if not args.show and args.alt is not None:
        d = direction(args.alt, args.az)
        print(f"[relight] alt={args.alt}° az={args.az}° -> toward-light dir "
              f"({d[0]:+.3f}, {d[1]:+.3f}, {d[2]:+.3f})")

    for lev in args.levs:
        if not lev.exists():
            print(f"{lev}: MISSING", file=sys.stderr)
            continue
        print(process(lev, args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
