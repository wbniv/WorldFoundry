#!/usr/bin/env python3
"""Audit: does every clock level carry a settings object, the same way for all clocks?

    python3 scripts/audit-clock-settings.py [--strict] [-h]

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (D13). A clock level has a settings object when it has all of:

  1. type      wfsource/source/oas/<id>settings.oas, which includes settings.inc, and its generated .oad
  2. fields    at least one SHOW_AS_LIVE field in the .oas (a field the engine re-reads after the level loads)
  3. level     the level's generator places one object of that type (no model, no mass)
  4. director  the clock's director reads it with property@ (indices written at export time)
  5. phone     android/screensaver/src/clocks/assets/<clock>-settings.json, generated from the .oad by
               scripts/gen-settings-capabilities.py, so the phone and coordinator can show the fields
  6. test      tests/test_<id>_settings.py edits and checks every live field

<id> is the clock's directory under wflevels/ with the underscores removed (minute_machine -> minutemachine).
The clocks are those in wflevels/clocks-menu.manifest when it exists, else the built-in list below.
Prints one row per clock and exits 0; with --strict it exits 1 if any clock lacks any of the six.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = ["minute_machine", "tide_harbour"]
MANIFEST = ROOT / "wflevels" / "clocks-menu.manifest"
CHECKS = ["type", "fields", "level", "director", "phone", "test"]


def clocks():
    if MANIFEST.exists():
        out = []
        for line in MANIFEST.read_text().splitlines():
            m = re.match(r"\s*level\s+(\S+?)(?:-standalone)?\.iff\s*\|", line)
            if m:
                out.append(m.group(1))
        if out:
            return out
    return BUILTIN


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def audit(clock):
    ident = clock.replace("_", "")
    oas = ROOT / "wfsource" / "source" / "oas" / f"{ident}settings.oas"
    oad = oas.with_suffix(".oad")
    src = read(oas)
    res = {
        "type": oas.exists() and oad.exists() and "settings.inc" in src,
        "fields": "SHOW_AS_LIVE" in src,
    }
    level_dir = ROOT / "wflevels" / clock
    gen = "".join(read(p) for p in sorted(level_dir.glob("*.py")) + sorted(level_dir.glob("*.lev")))
    res["level"] = bool(re.search(rf"{ident}settings\.oad|{ident}settings", gen, re.I))
    res["director"] = "property@" in gen
    phone_dir = ROOT / "android" / "screensaver" / "src"
    res["phone"] = any(phone_dir.glob(f"*/assets/{clock.replace('_', '-')}-settings.json"))
    res["test"] = (ROOT / "tests" / f"test_{clock}_settings.py").exists() or (ROOT / "tests" / f"test_{ident}_settings.py").exists()
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 if any clock lacks any of the six")
    args = ap.parse_args()
    rows = {c: audit(c) for c in clocks()}
    print(f"{'clock':16s} " + " ".join(f"{k:8s}" for k in CHECKS) + " settings object")
    gaps = 0
    for c, r in rows.items():
        missing = [k for k in CHECKS if not r[k]]
        gaps += bool(missing)
        print(f"{c:16s} " + " ".join(f"{'yes' if r[k] else 'MISSING':8s}" for k in CHECKS) + (" complete" if not missing else f" {len(missing)} of 6 missing"))
    print(f"{len(rows)} clocks audited, {gaps} without a complete settings object")
    return 1 if (args.strict and gaps) else 0


if __name__ == "__main__":
    sys.exit(main())
