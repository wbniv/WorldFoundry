#!/usr/bin/env python3
"""Add an Ambient Light actor to a `.lev` that has only Directional lights.

Background
----------
`wfsource/source/oas/levelcon.h` had `AMBIENT_LIGHT` and `DIRECTIONAL_LIGHT`
reversed with respect to `light.oas`'s ``"Directional|Ambient"`` enum, so every
Light actor in every level was assigned to the opposite slot.  Levels that
author only Directional lights were therefore being lit by their key light
applied as a *flat ambient* — which is the only reason they were visible.  With
the enum corrected they hit the documented Directional-only failure mode
(`docs/level-building.md`, "Lighting"): `u_ambient` defaults to `Color::black`,
so any face not facing a directional light renders pure black.

Measured on the affected levels, every one of those key lights points along
world +X (they were authored with the old `(pi/2 - alt, 0, az)` recipe, which
puts the altitude in the one euler angle that cannot move the +X axis the engine
reads the direction from).  Nothing a side-view camera sees is lit by them at
all, so the levels were, in practice, *fullbright ambient* levels.

This script preserves that: for each `light`-class object it appends a sibling
Ambient actor at the same position with the same RGB.  Result on those levels is
pixel-identical to the pre-fix build — the visible faces were already saturated
by the flat ambient, and the useless Directional adds nothing to them.  Picking
the documented ~0.4 grey here instead would dim every one of these levels to 40%
of its shipped appearance, which is a re-lighting decision, not a bug fix; that
is left as separate art work per level.

Usage
-----
    python3 scripts/add_ambient_light.py wflevels/smb_w1_1/smb_w1_1.lev
    python3 scripts/add_ambient_light.py --check wflevels/*/*.lev

Idempotent: a `.lev` that already contains a `lightType` of 1 is left alone.

See docs/plans/2026-09-20-engine-multi-directional-light-fix.md.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A `.lev` is text IFF.  Two formats are in the tree:
#   flat   — one chunk per line:   { 'I32' { 'NAME' "lightType" } { 'DATA' 0l } { 'STR' "Directional" } }
#   nested — chunk split over lines, as the original 3ds-Max exporter wrote it.
# Both are handled by locating object blocks with a brace counter and rewriting
# by regex inside the copied block, which works for either layout.

OBJ_OPEN = re.compile(r"^\s*\{\s*'OBJ'\s*$")
CLASS_LIGHT = re.compile(r"'DATA'\s+\"light\"")
NAME_ANY = re.compile(r"'NAME'\s+\"([^\"]*)\"")


def _split_objects(text: str) -> list[tuple[int, int]]:
    """Return (start_line, end_line_exclusive) for every top-level `{ 'OBJ'` block."""
    lines = text.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if OBJ_OPEN.match(lines[i]):
            depth = 0
            j = i
            while j < len(lines):
                # Brace counting ignoring anything inside a double-quoted string.
                stripped = re.sub(r'"[^"]*"', "", lines[j])
                depth += stripped.count("{") - stripped.count("}")
                j += 1
                if depth == 0:
                    break
            spans.append((i, j))
            i = j
        else:
            i += 1
    return spans


def _is_light_block(block: str) -> bool:
    """True when this object's `Class Name` field is "light"."""
    m = re.search(r"'NAME'\s+\"Class Name\"\s*\}?\s*\n?\s*\{?\s*'DATA'\s+\"([a-z]+)\"", block)
    if m:
        return m.group(1) == "light"
    # nested form: 'NAME' "Class Name" then a later 'DATA' "light"
    if '"Class Name"' in block:
        tail = block.split('"Class Name"', 1)[1]
        return bool(CLASS_LIGHT.search(tail.split("}", 6)[0] if "}" in tail else tail))
    return False


# `{ 'NAME' "lightType" } { 'DATA' <n>l` — the only difference between the flat
# and the nested 3ds-Max layout is where the newlines fall, which `\s*` absorbs.
LIGHT_TYPE_DATA = r"('NAME'\s+\"lightType\"\s*\}\s*\{\s*'DATA'\s+)(\d+)l"


def _light_type_values(block: str) -> list[int]:
    return [int(m.group(2)) for m in re.finditer(LIGHT_TYPE_DATA, block)]


def _rewrite_as_ambient(block: str, new_name: str) -> str:
    """Copy of `block` renamed, with every lightType entry flipped to Ambient."""
    # 1. object name — the first 'NAME' in the block, which is the OBJ's own name.
    def name_once(m, done=[]):
        if done:
            return m.group(0)
        done.append(True)
        return f"'NAME' \"{new_name}\""
    block = NAME_ANY.sub(name_once, block, count=1)

    # 2. lightType DATA 0l -> 1l.  The exporter emits the field twice (once from
    #    the schema walk, once from its hardcoded light block); flip both.
    block, n_flipped = re.subn(LIGHT_TYPE_DATA, lambda m: m.group(1) + "1l", block)
    if n_flipped == 0:
        raise ValueError("copied light block has no lightType DATA field to flip")
    # 3. the human-readable STR that trails lightType.  levcomp-rs warns when
    #    STR and DATA disagree ("Directional" label on DATA 1), so keep them in
    #    step.  Flat layout carries the word; the nested 3ds-Max layout carries
    #    the number.
    block = re.sub(
        r"('NAME'\s+\"lightType\"\s*\}\s*\{\s*'DATA'\s+1l\s*\}\s*\{\s*'STR'\s+)\"Directional\"",
        lambda m: m.group(1) + '"Ambient"',
        block,
    )
    block = re.sub(
        r"('NAME'\s+\"lightType\"\s*\n\s*\}\s*\n\s*\{\s*'DATA'\s+1l[^}]*\}\s*\n\s*\{\s*'STR'\s+)\"0\"",
        lambda m: m.group(1) + '"1"',
        block,
    )
    return block


ADDED_NAME = re.compile(r"^AmbientLight\d*$")


def undo(path: Path, write: bool) -> str:
    """Remove the `AmbientLight*` objects this script appended.

    Needed because not every `.lev` is tracked by git (`pilot_demo.lev` is
    generated), so `git checkout` is not a universal undo.
    """
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    spans = _split_objects(text)
    drop = []
    for s, e in spans:
        m = NAME_ANY.search("".join(lines[s:e]))
        if m and ADDED_NAME.match(m.group(1)):
            drop.append((s, e, m.group(1)))
    if not drop:
        return "skip: no AmbientLight* objects to remove"
    out = list(lines)
    for s, e, _ in reversed(drop):
        del out[s:e]
    if write:
        path.write_text("".join(out))
    return f"{'removed' if write else 'would remove'}: " + ", ".join(n for _, _, n in drop)


def process(path: Path, write: bool) -> str:
    text = path.read_text()
    spans = _split_objects(text)
    lines = text.splitlines(keepends=True)

    light_spans = []
    for s, e in spans:
        block = "".join(lines[s:e])
        if _is_light_block(block):
            light_spans.append((s, e, block))

    if not light_spans:
        return "skip: no light-class objects"

    existing = [v for _, _, b in light_spans for v in _light_type_values(b)]
    if 1 in existing:
        return f"skip: already has an Ambient light (lightType values {sorted(set(existing))})"

    # Append the Ambient copies *after the last object in the file*, never next
    # to the light they were copied from.  Inserting mid-list renumbers every
    # later object, and object references that are resolved positionally rather
    # than by name then point one slot off: qbert_practice died on
    # `assert(camShot->kind() == BaseObject::CamShot_KIND)` (movecam.cc:505)
    # when its AmbientLight was inserted at index 4.  Appending leaves every
    # existing index untouched, and room membership is unaffected because
    # levcomp-rs assigns rooms by bbox-centre containment
    # (wftools/levcomp-rs/src/rooms.rs), not by file order.
    last_obj_end = spans[-1][1]
    out = list(lines)
    added = []
    new_blocks = []
    for idx, (_s, _e, block) in enumerate(light_spans):
        m = NAME_ANY.search(block)
        src_name = m.group(1) if m else f"light{idx}"
        new_name = f"AmbientLight{idx:02d}" if len(light_spans) > 1 else "AmbientLight"
        new_blocks.append(_rewrite_as_ambient(block, new_name))
        added.append(f"{new_name} (from {src_name})")
    out[last_obj_end:last_obj_end] = new_blocks

    if write:
        path.write_text("".join(out))
    return f"{'wrote' if write else 'would add'}: " + ", ".join(added)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Add an Ambient Light actor to .lev files that have only Directional lights.",
    )
    ap.add_argument("levs", nargs="+", type=Path, help=".lev files to process")
    ap.add_argument("--check", action="store_true",
                    help="report what would change, write nothing")
    ap.add_argument("--undo", action="store_true",
                    help="remove the AmbientLight* objects this script added")
    args = ap.parse_args(argv)

    action = undo if args.undo else process
    rc = 0
    for p in args.levs:
        if not p.exists():
            print(f"{p}: MISSING", file=sys.stderr)
            rc = 1
            continue
        try:
            print(f"{p}: {action(p, write=not args.check)}")
        except Exception as e:  # noqa: BLE001 — report and keep going
            print(f"{p}: ERROR {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
