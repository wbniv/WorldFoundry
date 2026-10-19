#!/usr/bin/env python3
"""Build isolated, auto-driven variants of the eight existing aquarium tanks.

The canonical gameplay levels and their player scripts stay untouched. Each
variant starts from the exported .lev, swaps only the Player's script, then uses
the usual level compiler. Run canonical tank build tasks first when art changes.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ROOT / "wflevels"
TANKS = (
    "aquarium", "aquarium_blue_shrimp", "aquarium_betta", "aquarium_jellyfish",
    "aquarium_lionfish", "aquarium_plants", "aquarium_arowana",
    "aquarium_tiger_barbs",
)
SCRIPT_NAMES = {"aquarium": "aquarium_screensaver.fth",
                "aquarium_tiger_barbs": "tiger_barbs_screensaver.fth"}
SCRIPT_FIELD = re.compile(r"(\{ 'STR' \{ 'NAME' \"Script\" \} \{ 'STR' )"
                          r"(\"(?:\\.|[^\"\\])*\")", re.S)


def player_script(level_text: str, tank: str, driver: str) -> str:
    blocks = level_text.split("\t{ 'OBJ'")
    matches = [i for i, block in enumerate(blocks)
               if re.search(r"\{ 'NAME' \"Player\" \}", block)]
    if len(matches) != 1:
        raise ValueError(f"{tank}: expected one Player block, got {len(matches)}")
    index = matches[0]
    found = SCRIPT_FIELD.search(blocks[index])
    if not found:
        raise ValueError(f"{tank}: Player script missing")
    script = json.loads(found.group(2))
    if tank in SCRIPT_NAMES:
        entry = "aq-player-tick"
        if not script.rstrip().endswith(entry):
            raise ValueError(f"{tank}: unexpected Player entry")
        script = script.rstrip()[:-len(entry)] + driver + "\naq-screensaver-tick\n"
    else:
        entry = "ar-player-tick" if tank == "aquarium_arowana" else (
            "sh-player-tick" if tank == "aquarium_blue_shrimp" else "tk-player-tick")
        if not script.rstrip().endswith(entry):
            raise ValueError(f"{tank}: unexpected Player entry")
        # These controllers already accept held/released button masks. Swap
        # only the Player's input source; the Director keeps its own script.
        mailbox = "780" if tank == "aquarium_arowana" else "760"
        if "INDEXOF_HARDWARE_JOYSTICK1_RAW" not in script:
            raise ValueError(f"{tank}: input mailbox not found")
        script = script.replace("INDEXOF_HARDWARE_JOYSTICK1_RAW", mailbox)
        script = script.rstrip()[:-len(entry)] + driver + "\nss-drive\n" + entry + "\n"
    blocks[index] = blocks[index][:found.start(2)] + json.dumps(script) + blocks[index][found.end(2):]
    return "\t{ 'OBJ'".join(blocks)


def build(tank: str) -> Path:
    source = LEVELS / tank
    target_name = tank + "_screensaver"
    target = LEVELS / target_name
    target.mkdir(exist_ok=True)
    script_name = SCRIPT_NAMES.get(tank, "screensaver_player.fth")
    driver_source = LEVELS / "aquarium" if tank == "aquarium_tiger_barbs" else source
    driver = (driver_source / script_name).read_text()
    source_lev = source / (tank + ".lev")
    if not source_lev.is_file():
        raise FileNotFoundError(f"{source_lev}: build the canonical tank first")
    (target / (target_name + ".lev")).write_text(player_script(source_lev.read_text(), tank, driver))
    wrapper = (source / (tank + "-standalone.iff.txt")).read_text()
    old_ref, new_ref = f'"../{tank}.iff"', f'"../{target_name}.iff"'
    if old_ref not in wrapper:
        raise ValueError(f"{tank}: wrapper does not reference the canonical level")
    (target / (target_name + "-standalone.iff.txt")).write_text(wrapper.replace(old_ref, new_ref))
    for pattern in ("*.iff", "*.tga", "*.flags"):
        for asset in source.glob(pattern):
            link = target / asset.name
            if not link.exists():
                link.symlink_to(asset.resolve())
    (target / ".gitignore").write_text("# Generated screensaver level and linked assets\n*\n")
    subprocess.run(["bash", "wftools/wf_blender/build_level_binary.sh", target_name],
                   cwd=ROOT, check=True)
    return LEVELS / (target_name + "-standalone.iff")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tanks", nargs="*", choices=TANKS, help="Default: all eight tanks")
    args = parser.parse_args()
    java_choice = (ROOT / "android/screensaver/src/main/java/org/worldfoundry/screensaver/TankChoice.java").read_text()
    ids_match = re.search(r"static final String\[\] IDS = \{(.*?)\};", java_choice, re.S)
    if not ids_match or tuple(re.findall(r'"([a-z_]+)"', ids_match.group(1))) != TANKS:
        raise ValueError("TankChoice.IDS must match the screensaver bundle order")
    for tank in args.tanks or TANKS:
        print(f"Screensaver level: {tank}", flush=True)
        print(build(tank), flush=True)
    if not args.tanks:
        subprocess.run(["python3", "scripts/build-seahorse-grid-level.py"], cwd=ROOT, check=True)
        bundle = LEVELS / "aquarium-screensaver-cd.iff"
        subprocess.run([
            str(ROOT / "wftools/cdpack-rs/target/release/cdpack"),
            str(ROOT / "wfsource/source/game/shell.fth"),
            *(str(LEVELS / (tank + "_screensaver-standalone.iff")) for tank in TANKS),
            str(LEVELS / "seahorse_grid-standalone.iff"),
            "-o", str(bundle),
        ], cwd=ROOT, check=True)
        if b"UIFT" not in bundle.read_bytes()[:2048]:
            raise RuntimeError("cdpack is stale: rebuild wftools/cdpack-rs to include the UI font")
        assets = ROOT / "android/screensaver/src/main/assets"
        assets.mkdir(parents=True, exist_ok=True)
        link = assets / "cd.iff"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(Path(os.path.relpath(bundle, assets)))
        print(f"Screensaver bundle: {bundle}", flush=True)


if __name__ == "__main__":
    main()
