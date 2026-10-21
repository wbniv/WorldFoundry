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


def check_tank_catalog(level: bytes, tank: str) -> None:
    """One RPRP catalog on a tank variant: PlantedTankSettings, the Aquarium's fields, no Hold seconds."""
    # Two RPRP tags make one catalog: the RAM chunk's reference and the chunk itself
    # (build-object-properties.py attach()), as in aquarium_plants-standalone.iff.
    if level.count(b"RPRP") != 2 or level.count(b"PlantedTankSettings") != 1:
        raise ValueError(f"{tank}: expected one PlantedTankSettings RPRP catalog")
    for key in (b"Seed", b"Water type", b"Growth speed", b"Initial age", b"Textures", b"Sway",
                b"Random seed on entry", b"Seahorses", b"Greeting"):
        if key not in level:
            raise ValueError(f"{tank}: catalog field {key.decode()} missing")
    # The Planted Tank flavor's hold-then-reload cycle does not exist in the Aquarium.
    if b"Hold seconds" in level:
        raise ValueError(f"{tank}: catalog has the Hold seconds field")


def attach_catalog(tank: str) -> bool:
    """Attach the canonical tank's settings catalog (RPRP) to its screensaver variant.

    The variant swaps only the Player's script, so the canonical's OAS, bindings and actor map
    apply as they are; the actor indices are checked against the variant's own .lev. Tanks
    without a settings-bindings.json have no catalog and are left alone. Rebuilding replaces
    the catalog already in the standalone (build-object-properties.py attach()), so this must
    run on the variant's -standalone.iff before cdpack packs the bundle.
    """
    source = LEVELS / tank
    bindings_path = source / "settings-bindings.json"
    if not bindings_path.is_file():
        return False
    target_name = tank + "_screensaver"
    target = LEVELS / target_name
    standalone = LEVELS / (target_name + "-standalone.iff")
    indices = json.loads((source / "actor-map.json").read_text())["indices"]
    blocks = (target / (target_name + ".lev")).read_text().split("\t{ 'OBJ'")
    for name, index in indices.items():
        if index >= len(blocks) or not re.search(r"\{ 'NAME' \"" + re.escape(name) + r"\" \}", blocks[index]):
            raise ValueError(f"{target_name}: actor {name} is not object {index}; the canonical actor map does not fit")
    oad = target / "settings.oad"
    subprocess.run([str(ROOT / "wftools/oas2oad-rs/target/release/oas2oad"),
                    f"--types={ROOT / 'wfsource/source/oas/types3ds.s'}",
                    f"--prep={ROOT / 'wftools/prep/prep'}",
                    "-o", str(oad), str(source / "settings.oas")], cwd=ROOT, check=True)
    subprocess.run(["python3", "scripts/build-object-properties.py",
                    "--oad", str(oad), "--bindings", str(bindings_path),
                    "--actor-map", str(source / "actor-map.json"),
                    "--out", str(target / "settings.rprp"),
                    "--level", str(standalone)], cwd=ROOT, check=True)
    check_tank_catalog(standalone.read_bytes(), target_name)
    return True


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
    attach_catalog(tank)
    return LEVELS / (target_name + "-standalone.iff")


PLANTED = "planted_tank_screensaver"
PLANTED_BUNDLE = LEVELS / "planted-screensaver-cd.iff"
ANIMAL_NAMES = ("urchin", "goby", "seahorse", "rainbow")
ANIMAL_MESHES = ("sea_urchin", "urchin_", "goby", "seahorse_", "_rock_")
ANIMAL_WORDS = ("uf-foot", "us-spine", "sh-tick", "swim-deform", "1160", "1161")


def script_of(level_text: str, name: str) -> str:
    """The Script field of the one OBJ block named `name`."""
    blocks = [block for block in level_text.split("\t{ 'OBJ'")
              if re.search(r"\{ 'NAME' \"" + re.escape(name) + r"\" \}", block)]
    if len(blocks) != 1:
        raise ValueError(f"{PLANTED}: expected one {name} block, got {len(blocks)}")
    found = SCRIPT_FIELD.search(blocks[0])
    if not found:
        raise ValueError(f"{PLANTED}: {name} script missing")
    return json.loads(found.group(2))


def check_planted(level_text: str, actor_map: dict, asset_inc: str) -> None:
    """Spike S4's asserts: plants only, an invisible Player, the plants registered by index."""
    indices = actor_map["indices"]
    animals = [name for name in indices if any(word in name.lower() for word in ANIMAL_NAMES)]
    if animals:
        raise ValueError(f"{PLANTED}: animal actors in the level: {animals}")
    if indices.get("Director") != 4:
        raise ValueError(f"{PLANTED}: Director is {indices.get('Director')}, expected 4")
    player = [block for block in level_text.split("\t{ 'OBJ'") if re.search(r"\{ 'NAME' \"Player\" \}", block)]
    if len(player) != 1 or not re.search(r"\"Visibility Mailbox\" \} \{ 'DATA' 0l \}", player[0]):
        raise ValueError(f"{PLANTED}: expected one Player block with Visibility Mailbox 0")
    meshes = re.findall(r"\"([\w.-]+\.iff)\"", level_text + asset_inc)
    stray = sorted({m for m in meshes if any(word in m for word in ANIMAL_MESHES)})
    if stray:
        raise ValueError(f"{PLANTED}: animal meshes referenced: {stray}")
    director = script_of(level_text, "Director")
    registered = [(int(k), int(a)) for k, a in re.findall(r"(\d+) (\d+) plant-register", director)]
    expected = [(k, indices[f"plant_chunk_{k:02d}"]) for k in range(8)]
    if registered != expected:
        raise ValueError(f"{PLANTED}: plant-register pairs {registered}, expected {expected}")
    words = [word for word in ANIMAL_WORDS if word in director]
    if words:
        raise ValueError(f"{PLANTED}: animal words in the Director script: {words}")
    writes = re.findall(r"(\S+) (?:INDEXOF_END_OF_LEVEL|1905) (?:tk!|write-mailbox)", director)
    if not writes or set(writes) != {"1"}:
        raise ValueError(f"{PLANTED}: END_OF_LEVEL must only be written with 1, found {writes}")


def check_catalog(level: bytes) -> None:
    """One RPRP catalog: PlantedTankSettings with Hold seconds and no seahorse fields."""
    # Two RPRP tags make one catalog: the RAM chunk's reference and the chunk itself
    # (build-object-properties.py attach()), as in aquarium_plants-standalone.iff.
    if level.count(b"RPRP") != 2 or level.count(b"PlantedTankSettings") != 1:
        raise ValueError(f"{PLANTED}: expected one PlantedTankSettings RPRP catalog")
    for key in (b"Seed", b"Water type", b"Growth speed", b"Initial age", b"Textures", b"Sway",
                b"Random seed on entry", b"Hold seconds"):
        if key not in level:
            raise ValueError(f"{PLANTED}: catalog field {key.decode()} missing")
    for key in (b"Seahorses", b"Greeting"):
        if key in level:
            raise ValueError(f"{PLANTED}: catalog has the {key.decode()} field")


def build_planted() -> Path:
    """The Planted Tank screensaver: its own plants-only level, no driver swap, its catalog."""
    source = LEVELS / PLANTED
    lev = source / (PLANTED + ".lev")
    if not lev.is_file():
        raise FileNotFoundError(f"{lev}: run bash wflevels/{PLANTED}/build.sh (Blender) first")
    subprocess.run(["bash", "wftools/wf_blender/build_level_binary.sh", PLANTED], cwd=ROOT, check=True)
    check_planted(lev.read_text(), json.loads((source / "actor-map.json").read_text()),
                  (source / "asset.inc").read_text() if (source / "asset.inc").is_file() else "")
    oad = source / "settings.oad"
    subprocess.run([str(ROOT / "wftools/oas2oad-rs/target/release/oas2oad"),
                    f"--types={ROOT / 'wfsource/source/oas/types3ds.s'}",
                    f"--prep={ROOT / 'wftools/prep/prep'}",
                    "-o", str(oad), str(source / "settings.oas")], cwd=ROOT, check=True)
    # The APK's coordinator settings come from this OAD (plan: Decision, Will 2026-10-21).
    subprocess.run(["python3", "scripts/gen-planted-capabilities.py", "--oad", str(oad), "--out",
                    str(ROOT / "android/screensaver/src/planted/assets/planted-settings.json")],
                   cwd=ROOT, check=True)
    standalone = LEVELS / (PLANTED + "-standalone.iff")
    subprocess.run(["python3", "scripts/build-object-properties.py",
                    "--oad", str(oad), "--bindings", str(source / "settings-bindings.json"),
                    "--actor-map", str(source / "actor-map.json"),
                    "--out", str(source / "settings.rprp"),
                    "--include", str(source / "settings-catalog.inc"),
                    "--level", str(standalone)], cwd=ROOT, check=True)
    check_catalog(standalone.read_bytes())
    subprocess.run([str(ROOT / "wftools/cdpack-rs/target/release/cdpack"),
                    str(ROOT / "wfsource/source/game/shell.fth"), str(standalone),
                    "-o", str(PLANTED_BUNDLE)], cwd=ROOT, check=True)
    if b"UIFT" not in PLANTED_BUNDLE.read_bytes()[:2048]:
        raise RuntimeError("cdpack is stale: rebuild wftools/cdpack-rs to include the UI font")
    # The flavor's asset, linked the way the Aquarium and Seahorse flavors are.
    assets = ROOT / "android/screensaver/src/planted/assets"
    assets.mkdir(parents=True, exist_ok=True)
    link = assets / "cd.iff"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(Path(os.path.relpath(PLANTED_BUNDLE, assets)))
    print(f"planted screensaver asset: {link}", flush=True)
    return PLANTED_BUNDLE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tanks", nargs="*", choices=(*TANKS, "planted"),
                        help="Default: all eight tanks. 'planted' builds only the Planted Tank screensaver bundle")
    args = parser.parse_args()
    if "planted" in args.tanks:
        if len(args.tanks) != 1:
            parser.error("'planted' builds on its own")
        print(f"planted screensaver bundle: {build_planted()}", flush=True)
        return
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
