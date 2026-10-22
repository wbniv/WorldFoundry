#!/usr/bin/env python3
"""Build a separate World Foundry level with 24 independently animated seahorses.

The planted tank supplies the exported seahorse meshes and basic room objects.
This level has its own Director script and no planted-tank gameplay objects.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from level_asset_links import link_source_assets


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "wflevels/aquarium_plants"
TARGET = ROOT / "wflevels/seahorse_grid"
SCRIPT_FIELD = re.compile(r"(\{ 'STR' \{ 'NAME' \"Script\" \} \{ 'STR' )"
                          r"(\"(?:\\.|[^\"\\])*\")", re.S)
NAME = re.compile(r'\{ \'NAME\' "([^"]+)" \}')
KEEP = {"Room", "SunLight", "Camera", "Director", "LevelObj", "Matte",
        "cs_wide", "LookAt", "Player", "AmbientLight"}
COLS, ROWS = 6, 4
COUNT = COLS * ROWS
COLUMN_SPACING = 2.8
ROW_SPACING = COLUMN_SPACING * (COLS - 1) * 9 / (16 * (ROWS - 1))
BOTTOM_ROW_Z = .25
GRID_CENTER_Z = BOTTOM_ROW_Z + (ROWS - 1) * ROW_SPACING / 2
BLOCK_BASE, BLOCK_STRIDE = 100, 40


def replace_script(block: str, source: str) -> str:
    match = SCRIPT_FIELD.search(block)
    if match is None:
        # Mesh templates do not normally carry behavior. Add the standard
        # object property before the OBJ's closing brace when one is needed.
        end = block.rfind("\n\t}")
        if end < 0:
            raise ValueError("object has no Script field or closing brace")
        return block[:end] + "\n\t\t{ 'STR' { 'NAME' \"Script\" } { 'STR' " + \
            json.dumps(source) + " } }" + block[end:]
    return block[:match.start(2)] + json.dumps(source) + block[match.end(2):]


def set_position(block: str, x: float, y: float, z: float) -> str:
    coordinates = f"{x:.8f}(1.15.16) {y:.8f}(1.15.16) {z:.8f}(1.15.16)  //x,y,z"
    block, count = re.subn(
        r"(\{ 'VEC3' \{ 'NAME' \"Position\" \} \{ 'DATA' )[^\n]+",
        lambda match: match.group(1) + coordinates, block, count=1)
    if count != 1:
        raise ValueError("Position missing")
    return block


def place(block: str, name: str, x: float, y: float, z: float,
          room_local: bool = False) -> str:
    block = NAME.sub(lambda _: "{ 'NAME' " + json.dumps(name) + " }", block, count=1)
    block = set_position(block, x, y, z)
    block, count = re.subn(
        r"(\{ 'EULR' \{ 'NAME' \"Orientation\" \} \{ 'DATA' )[^\n]+",
        lambda match: match.group(1) + "0(1.15.16) 0(1.15.16) 0(1.15.16)  //a,b,c",
        block, count=1)
    if count != 1:
        raise ValueError(f"{name}: Orientation missing")
    block, count = re.subn(
        r'\{ \'I32\' \{ \'NAME\' "Visibility Mailbox" \} '
        r'\{ \'DATA\' \d+l \} \{ \'STR\' "\d+" \} \}',
        '{ \'I32\' { \'NAME\' "Visibility Mailbox" } '
        '{ \'DATA\' 1l } { \'STR\' "1" } }', block, count=1)
    if count != 1:
        raise ValueError(f"{name}: Visibility Mailbox missing")
    if room_local:
        block, count = re.subn(
            r'(\{ \'NAME\' "Moves Between Rooms" \} \{ \'DATA\' )1l'
            r'( \} \{ \'STR\' )"True"',
            r'\g<1>0l\g<2>"False"', block, count=1)
        if count != 1:
            raise ValueError(f"{name}: Moves Between Rooms missing")
    return block


def grid_position(n: int) -> tuple[float, float, float]:
    col, row = n % COLS, n // COLS
    return ((col - (COLS - 1) / 2) * COLUMN_SPACING,
            -.15, BOTTOM_ROW_Z + row * ROW_SPACING)


def animation_script() -> str:
    """All seahorses invoke the same already-compiled actor-local behavior."""
    return "sg-tick\n"


def shared_animation_definitions() -> str:
    """Compile the small shared state machine once; actors invoke it independently."""
    return "\n".join([
        ": sg@ read-mailbox ; : sg! write-mailbox ;",
        ": sg-now INDEXOF_TIME sg@ ;",
        ": sg-play ( clip fade -- )",
        "  100 27 + sg@ 0 <> if 100 27 + sg@ 100 25 + sg!",
        "    100 28 + sg@ 100 26 + sg! then",
        "  100 29 + sg! 100 27 + sg! sg-now 100 28 + sg! ;",
        ": sg-step",
        "  sg-now 131 sg@ < if exit then",
        "  130 sg@ 0 = if",
        "    132 sg@ 0 = if 8 1.3 sg-play 1 130 sg! sg-now 5 + 131 sg!",
        "    else 132 sg@ 1 = if 4 1.3 sg-play 2 130 sg! sg-now 2.7 + 131 sg!",
        "    else 83 sg@ 1.5 sg-play 3 130 sg! sg-now 6.3 + 131 sg! then then",
        "  else 6 1.5 sg-play 0 130 sg! sg-now 7.5 + 131 sg!",
        "    132 sg@ 1 + 3 mod 132 sg! then ;",
        ": sg-init-fish 135 sg@ 0 = if",
        "  6 125 sg! 0 126 sg! 0 127 sg! 0 128 sg! 0 130 sg!",
        "  sg-now 84 sg@ + 131 sg! sg-now 82 sg@ 1.3 * - 126 sg!",
        "  1 135 sg! then ;",
        ": sg-tick sg-init-fish sg-step",
        "  100 80 sg@ dfrm-pose drop",
        "  sg-now 2.2 * 82 sg@ .071 * + .022 0 1 81 sg@ fin-deform ;",
    ]) + "\n"


def director_script(indices: dict[str, int]) -> str:
    """Install actor identity data once and set the fixed wide camera."""
    script = [
        "\\ Seahorse Grid placement setup; each body runs the shared sg-tick.",
        shared_animation_definitions(),
        f": sg-base {indices['seahorse-0-body']} ;",
        ": sg-config dup 2 * sg-base + >r",
        "  r@ 80 r@ write-actor-mailbox",
        "  r@ 1+ 81 r@ write-actor-mailbox",
        "  dup 2 / dup 82 r@ write-actor-mailbox",
        "  dup 1 & 1+ 83 r@ write-actor-mailbox",
        "  2 / 2.6 * 8 + 84 r@ write-actor-mailbox",
        "  r> drop ;",
        ": sg-setup 24 0 do i sg-config loop",
    ]
    script += ["  1 90 sg! ;", "90 sg@ 0 = if sg-setup then",
               f"  {indices['cs_wide']} INDEXOF_CAMSHOT sg!"]
    return "\n".join(script) + "\n"


def generate() -> Path:
    source = (SOURCE / "aquarium_plants.lev").read_text()
    end = source.rfind("\n}")
    if end < 0:
        raise ValueError("planted level has no closing LVL brace")
    head, *chunks = source[:end].split("\t{ 'OBJ'")
    blocks = {NAME.search(chunk).group(1): chunk for chunk in chunks}
    if not KEEP <= blocks.keys():
        raise ValueError(f"missing template objects: {KEEP - blocks.keys()}")
    ordered = [name for name in blocks if name in KEEP]
    output = [blocks[name] for name in ordered]
    for name in ("Camera", "cs_wide"):
        output[ordered.index(name)] = set_position(
            output[ordered.index(name)], 0, -9, GRID_CENTER_Z)
    output[ordered.index("LookAt")] = set_position(
        output[ordered.index("LookAt")], 0, 0, GRID_CENTER_Z)
    for n in range(COUNT):
        sex = n % 2
        x, y, z = grid_position(n)
        for part in ("body", "fins"):
            name = f"seahorse-{n}-{part}"
            output.append(place(blocks[f"seahorse-{sex}-{part}"], name, x, y, z,
                                room_local=n == 0 and part == "body"))
            if part == "body":
                output[-1] = replace_script(output[-1], animation_script())
            ordered.append(name)
    indices = {name: index + 1 for index, name in enumerate(ordered)}
    output[ordered.index("Director")] = replace_script(
        output[ordered.index("Director")], director_script(indices))
    output[ordered.index("Player")] = replace_script(
        output[ordered.index("Player")], ": sg-player 0 INDEXOF_INPUT write-mailbox ; sg-player\n")

    TARGET.mkdir(exist_ok=True)
    (TARGET / "seahorse_grid.lev").write_text(head + "\t{ 'OBJ'" + "\t{ 'OBJ'".join(output) + source[end:])
    (TARGET / "seahorse_grid-standalone.iff.txt").write_text(
        "// Independent seahorse grid level, reusing the planted tank's exported meshes.\n"
        "{ 'L4'\n { 'ALGN' .align( 2048 ) }\n"
        " { 'RAM' 'OBJD' 1000000l 'PERM' 12000000l 'ROOM' 24000000l 'FLAG' 1l 1l 'SLOT' 1l }\n"
        " { 'ALGN' .align( 2048 ) }\n [ \"../seahorse_grid.iff\" ]\n}\n")
    link_source_assets(SOURCE, TARGET)
    (TARGET / ".gitignore").write_text(
        "# Keep the authored generated level; ignore compiled files and asset links.\n"
        "*\n!.gitignore\n!seahorse_grid.lev\n!seahorse_grid-standalone.iff.txt\n")
    subprocess.run(["bash", "wftools/wf_blender/build_level_binary.sh", "seahorse_grid"],
                   cwd=ROOT, check=True)
    return ROOT / "wflevels/seahorse_grid-standalone.iff"


if __name__ == "__main__":
    print(generate())
