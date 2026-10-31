"""Read wflevels/main-cd.manifest: the ordered level list of the main cd.iff.

One source for `task build-cd-iff`, wflevels/baseline/verify.py and tests/level_menu_harness.py.
The TOC index of a level is its position here. The grammar is the level-menu manifest's
(`level <path> | <name>`, `#` comments, blank lines), minus `title` and `prompt`: this bundle
has no menu.
"""
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "wflevels" / "main-cd.manifest"
SUFFIX = "-standalone.iff"

Level = namedtuple("Level", "index path name slug")


def load(manifest=MANIFEST):
    """Return the levels in TOC order, validated. Raises ValueError naming file and line."""
    manifest = Path(manifest)
    levels, seen = [], set()
    for number, raw in enumerate(manifest.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        where = "%s:%d" % (manifest, number)
        if not line.startswith("level "):
            raise ValueError("%s: only `level <path> | <name>` lines are allowed; this bundle has no menu" % where)
        path_text, bar, name = (part.strip() for part in line[len("level "):].partition("|"))
        if not bar or not path_text or not name:
            raise ValueError("%s: expected `level <path> | <name>`" % where)
        if not path_text.endswith(SUFFIX):
            raise ValueError("%s: %s must be a standalone level (%s...); the bare LVAS .iff cannot be packed" % (where, path_text, SUFFIX))
        if not (1 <= len(name) <= 60 and all(32 <= ord(c) < 127 for c in name)):
            raise ValueError("%s: the name must be 1 to 60 printable ASCII characters" % where)
        path = (manifest.parent / path_text).resolve()
        if not path.is_file():
            raise ValueError("%s: %s does not exist" % (where, path))
        if path in seen:
            raise ValueError("%s: %s is listed twice" % (where, path_text))
        seen.add(path)
        levels.append(Level(len(levels), path, name, path.name[: -len(SUFFIX)]))
    if not levels:
        raise ValueError("%s lists no levels" % manifest)
    return levels


if __name__ == "__main__":
    for level in load():
        print("%d  %-26s %s" % (level.index, level.slug, level.name))
