#!/usr/bin/env python3
"""Audit: does every clock and every aquarium tank carry a settings object, and a way to open it?

    python3 scripts/audit-level-settings.py [--roster clocks|aquarium|all|levels] [--strict] [-h]

Rosters: wflevels/clocks-menu.manifest (the 3D Clocks package) and wflevels/aquarium-menu.manifest
(the Aquarium package). A level has a settings object when all six hold; the type is found from the
level's own source (wflevels/<id>/<id>.lev), so it does not depend on a naming rule:

  type      the level places an object of a *Settings type whose wfsource/source/oas/<type>.oas includes
            settings.inc and whose generated .oad exists
  fields    that .oas has at least one SHOW_AS_LIVE field (what makes levcomp list the object as editable)
  level     the level source places the object (this is how the type was found)
  director  the level's script reads it with property@
  phone     an android/screensaver/src/*/assets/*.json capabilities asset describes that type
            (scripts/gen-settings-capabilities.py makes it from the .oad)
  test      a tests/test_*.py mentions the type

Ways to open the settings, which follow from the six:
  hold A    on the TV remote or a gamepad, hold A (the centre button) alone for 1 second in the level:
            engine/runtime_property_host.cpp opens the form of the one editable object, or a picker
            of them. Needs `type`, `fields` and `level` (and a built level that lists the object).
  phone     the Dream form on the phone. Needs `phone`.

Prints one row per level and exits 0; with --strict it exits 1 if any level lacks any of the six.
Roster `levels` is a different audit: every built level (wflevels/<id>-standalone.iff, not only the two
packs) must carry the settings every level offers (wfsource/source/oas/global_settings.inc, today **Show
framerate**), so the player can switch the overlay on in any of them. A level has it when its built file
lists the field's key. `--strict` exits 1 while any built level lacks it
(docs/plans/2026-11-22-global-level-settings.md).
Docs: docs/howto/combine-levels-chooser-and-screensaver-launch.md, "Give every level settings".
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OAS = ROOT / "wfsource" / "source" / "oas"
ROSTERS = {
    "clocks": ROOT / "wflevels" / "clocks-menu.manifest",
    "aquarium": ROOT / "wflevels" / "aquarium-menu.manifest",
}
CHECKS = ["type", "fields", "level", "director", "phone", "test"]
# Types that end in "Settings" but are not a level's own settings holder.
NOT_A_LEVEL_TYPE = {"LevelRenderSettings", "Settings"}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def roster(name):
    """Level ids of a roster, in manifest order."""
    ids = []
    for line in read(ROSTERS[name]).splitlines():
        m = re.match(r"\s*level\s+(\S+?)(?:-standalone)?\.iff\s*\|", line)
        if m:
            ids.append(m.group(1))
    return ids


def settings_types():
    """Every registered *Settings type, from the object registry (wfsource/source/oas/objects.mac)."""
    names = re.findall(r"^\s*OBJECTENTRY\((\w+Settings),", read(OAS / "objects.mac"), re.M)
    return [n for n in names if n not in NOT_A_LEVEL_TYPE]


def global_keys():
    """The keys global_settings.inc declares: the one place a global setting is declared."""
    return re.findall(r"^\s*TYPEENTRY\w+\(([^,]+),", read(OAS / "global_settings.inc"), re.M)


def built_levels():
    """Every built level: the ids of wflevels/<id>-standalone.iff."""
    return sorted(p.name[: -len("-standalone.iff")] for p in (ROOT / "wflevels").glob("*-standalone.iff"))


def missing_globals(level_id, keys=None):
    """The global settings a built level does not list, by key (field names are plain text in the built file)."""
    keys = global_keys() if keys is None else keys
    data = (ROOT / "wflevels" / f"{level_id}-standalone.iff").read_bytes()
    return [k for k in keys if k.encode() not in data]


def audit_globals():
    """Print one row per built level; return how many lack a global setting."""
    keys = global_keys()
    print(f"\nlevels (every wflevels/<id>-standalone.iff) and the global settings {', '.join(keys)}")
    gaps = 0
    levels = built_levels()
    for level in levels:
        lacking = missing_globals(level, keys)
        gaps += bool(lacking)
        print(f"{level:40s} " + ("yes" if not lacking else "MISSING " + ", ".join(lacking)))
    print(f"\n{len(levels)} levels audited, {gaps} without the global settings")
    return gaps


def level_source(level_id):
    """The level's .lev (objects and the director script) plus its generator scripts."""
    level_dir = ROOT / "wflevels" / level_id
    lev = read(level_dir / f"{level_id}.lev")
    return lev, "".join(read(p) for p in sorted(level_dir.glob("*.py")))


def audit(level_id, types=None):
    """{check: bool, 'type_name': str or None} for one level."""
    types = settings_types() if types is None else types
    lev, generators = level_source(level_id)
    found = [t for t in types if re.search(rf'"{t}"', lev) or re.search(rf"{t.lower()}\.oad", lev, re.I)]
    name = found[0] if found else None
    res = dict.fromkeys(CHECKS, False)
    res["type_name"] = name
    if not name:
        return res
    oas = OAS / f"{name.lower()}.oas"
    src = read(oas)
    res["type"] = oas.exists() and oas.with_suffix(".oad").exists() and "settings.inc" in src
    res["fields"] = "SHOW_AS_LIVE" in src
    res["level"] = True
    res["director"] = "property@" in lev
    res["phone"] = any(name in read(p) for p in (ROOT / "android/screensaver/src").glob("*/assets/*.json"))
    res["test"] = any(name in read(p) for p in (ROOT / "tests").glob("test_*.py"))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roster", choices=[*ROSTERS, "all", "levels"], default="all")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any level lacks any of the six")
    args = ap.parse_args()
    if args.roster == "levels":
        gaps = audit_globals()
        return 1 if (args.strict and gaps) else 0
    types = settings_types()
    gaps = total = 0
    for name in (ROSTERS if args.roster == "all" else [args.roster]):
        print(f"\n{name} ({ROSTERS[name].relative_to(ROOT)})")
        print(f"{'level':26s} {'settings type':22s} " + " ".join(f"{k:8s}" for k in CHECKS) + " opens with")
        for level in roster(name):
            r = audit(level, types)
            missing = [k for k in CHECKS if not r[k]]
            total += 1
            gaps += bool(missing)
            ways = [w for w, ok in (("hold A", r["type"] and r["fields"] and r["level"]), ("phone", r["phone"])) if ok]
            print(f"{level:26s} {(r['type_name'] or '-'):22s} " + " ".join(f"{'yes' if r[k] else 'MISSING':8s}" for k in CHECKS)
                  + (" " + " + ".join(ways) if ways else " NOTHING"))
    print(f"\n{total} levels audited, {gaps} without a complete settings object")
    return 1 if (args.strict and gaps) else 0


if __name__ == "__main__":
    sys.exit(main())
