#!/usr/bin/env python3
"""Generate the Planted Tank APK's coordinator capabilities (schema 1) from its settings OAD.

Will's decision (docs/plans/2026-10-21-planted-tank-screensaver.md, 2026-10-21): the APK's
settings come from the OAD, not from a second copy in Java. This reads each compiled OAD of
the settings class and writes the `getCapabilities` document that PlantedSettingsProvider
serves, after overlaying the saved value of each setting.

The settings class is a stand-in: until the `Settings` base class of
docs/plans/2026-10-16-runtime-object-editing.md lands, it is any type whose name ends in
`Settings`. Every field of such a type is considered; the OAD's show-as modifier decides how
it presents. Schema 1 is only proven for `choice` (docs/device-coordinator.md,
TankSettingsProvider.java), so:

  * labelled choices (radio buttons, labelled slider, drop menu, combo box) become `choice`;
  * a number with a preset list below becomes `choice` (a presentation choice, see PRESETS);
  * everything else (checkbox, bare number, text) is skipped with a warning naming it.

The OAD is parsed by the same Rust normalizer scripts/build-object-properties.py uses
(`oad_schema`), not by a second parser.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

# wfsource/source/oas/oad.h visualRepresentation.
SHOW_AS_NUMBER, SHOW_AS_SLIDER, SHOW_AS_DROPMENU = 1, 2, 4
SHOW_AS_RADIOBUTTONS, SHOW_AS_CHECKBOX, SHOW_AS_COMBOBOX = 5, 8, 10
LABELLED_CHOICE = {SHOW_AS_SLIDER, SHOW_AS_DROPMENU, SHOW_AS_RADIOBUTTONS, SHOW_AS_COMBOBOX}
SHOW_NAMES = {0: "n/a", 1: "number", 2: "slider", 3: "toggle", 4: "drop menu", 5: "radio buttons",
              6: "hidden", 7: "colour", 8: "checkbox", 9: "mailbox", 10: "combo box",
              11: "text editor", 12: "filename"}
STRUCTURAL = {"Section", "Group", "GroupEnd", "Skip"}

# OAD field -> (PlantedConfig key, tray label). The key must be one PlantedConfig accepts; the
# labels keep the tray text the provider has always shown. A field without an entry has no
# APK key (Random seed on entry is set implicitly by `seed`); it may only be non-renderable.
APK_KEYS = {
    "Water type": ("water", "Water"),
    "Seed": ("seed", "Seed"),
    "Growth speed": ("speed", "Speed"),
    "Initial age": ("age", "Age"),
    "Textures": ("textures", "Textures"),
    "Sway": ("sway", "Sway"),
    "Hold seconds": ("hold", "Hold"),
}

# APK-only options placed before the OAD's own: `random` is the APK's per-tank water policy
# (PlantedConfig.RANDOM, its default), which the level itself does not have.
LEADING_OPTIONS = {"water": [("random", "Random")]}

# OAD choices the APK rejects: Paused would leave the tank growing forever, so the screensaver
# would never move on (PlantedConfig.withSpeed rejects speed 0).
DROPPED_OPTIONS = {"speed": {"Paused"}}

# Presentation choice for numeric fields the tray cannot render as a number: a fixed preset
# list, each validated against the OAD's min/max. The provider adds the current value when
# it is a custom one.
PRESETS = {"hold": [60, 120, 300, 600]}

SPEED_LABEL = re.compile(r"^(\d+(?:\.\d+)?)x$")


class GenerateError(Exception):
    pass


def _properties():
    spec = importlib.util.spec_from_file_location(
        "build_object_properties", ROOT / "scripts/build-object-properties.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def option_id(label):
    """`0.25x` -> `0.25`, `Freshwater` -> `freshwater`: the value PlantedConfig parses."""
    speed = SPEED_LABEL.match(label)
    return speed.group(1) if speed else label.strip().lower()


def seconds_label(seconds):
    return f"{seconds // 60} min" if seconds >= 60 and seconds % 60 == 0 else f"{seconds} s"


def setting(field, key, label):
    """The schema-1 `choice` for one OAD field, or None when schema 1 cannot render it."""
    if field["kind"] == "Enum" and field["show"] in LABELLED_CHOICE and field["choices"]:
        labels = field["choices"].split("|")
        dropped = DROPPED_OPTIONS.get(key, set())
        unknown = dropped - set(labels)
        if unknown:
            raise GenerateError(f"{field['key']}: dropped options {sorted(unknown)} are not OAD choices")
        options = list(LEADING_OPTIONS.get(key, []))
        options += [(option_id(text), text) for text in labels if text not in dropped]
        default = labels[field["default"]] if 0 <= field["default"] < len(labels) else labels[0]
        value = option_id(default) if default not in dropped else options[0][0]
    elif field["kind"] == "Int" and key in PRESETS:
        presets = PRESETS[key]
        bad = [p for p in presets if not field["min"] <= p <= field["max"]]
        if bad:
            raise GenerateError(f"{field['key']}: presets {bad} are outside "
                                f"{field['min']}..{field['max']}")
        options = [(str(p), seconds_label(p)) for p in presets]
        value = str(field["default"])
    else:
        return None
    ids = [o[0] for o in options]
    if len(set(ids)) != len(ids):
        raise GenerateError(f"{field['key']}: duplicate option ids {ids}")
    return {"id": key, "type": "choice", "label": label, "value": value,
            "options": [{"id": i, "label": text} for i, text in options]}


def capabilities(schemas):
    """(document, skipped) for the OAD schemas of the settings class."""
    settings, skipped, seen = [], [], set()
    for schema in schemas:
        if not schema["name"].endswith("Settings"):
            raise GenerateError(f"{schema['name']}: not a settings class (type name must end in Settings)")
        for field in schema["fields"]:
            if field["kind"] in STRUCTURAL:
                continue
            key, label = APK_KEYS.get(field["key"], (None, None))
            if key is None and setting(field, field["key"], field["label"]) is not None:
                # All fields of a settings object are exposed: a renderable one needs a key.
                raise GenerateError(f"{field['key']}: renderable field has no APK key "
                                    "(add it to PlantedConfig and APK_KEYS)")
            entry = setting(field, key, label) if key else None
            if entry is None:
                how = SHOW_NAMES.get(field["show"], str(field["show"]))
                why = "no APK key" if key is None else "schema 1 renders only choice"
                skipped.append(f"{field['key']} ({field['kind']}, {how}; {why})")
                continue
            if key in seen:
                raise GenerateError(f"{field['key']}: setting id {key} appears twice")
            seen.add(key)
            settings.append(entry)
    present = {field["key"] for schema in schemas for field in schema["fields"]}
    missing = [name for name in APK_KEYS if name not in present]
    if missing:
        raise GenerateError(f"APK_KEYS names fields missing from the OAD: {missing}")
    return {"schema": 1, "settings": settings}, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--oad", type=Path, action="append", required=True,
                        help="compiled settings-class OAD (repeatable)")
    parser.add_argument("--out", type=Path, required=True,
                        help="capabilities JSON to write, e.g. "
                             "android/screensaver/src/planted/assets/planted-settings.json")
    args = parser.parse_args(argv)
    try:
        for oad in args.oad:
            if not oad.is_file():
                raise GenerateError(f"{oad}: no such OAD (compile settings.oas first)")
        oad_schema = _properties().oad_schema
        document, skipped = capabilities([oad_schema(oad) for oad in args.oad])
        for field in skipped:
            print(f"gen-planted-capabilities: warning: skipped {field}", file=sys.stderr)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.out.with_suffix(args.out.suffix + ".tmp")
        tmp.write_text(json.dumps(document, separators=(",", ":")) + "\n")
        tmp.replace(args.out)
    except (GenerateError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"gen-planted-capabilities: error: {error}", file=sys.stderr)
        return 1
    print(f"planted capabilities: {args.out} ({len(document['settings'])} settings, "
          f"{len(skipped)} skipped)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
