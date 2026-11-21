"""Read a level manifest (wflevels/*-menu.manifest): the roster of a multi-level package.

The same format cdpack packs a menu bundle from (wftools/cdpack-rs/src/main.rs) and the Android
screensaver's LevelCatalog reads (android/screensaver/src/main/java/org/worldfoundry/screensaver/
LevelCatalog.java): `title <text>`, `prompt <text>`, `level <id>-standalone.iff | <menu name>
[| <dream label>]`. An entry's id is its file name without -standalone.iff; its label is the
Dream label, or the menu name. docs/plans/2026-11-21-aquarium-menu-and-screensaver-launch.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AQUARIUM = ROOT / "wflevels" / "aquarium-menu.manifest"
SUFFIX = "-standalone.iff"


@dataclass(frozen=True)
class Entry:
    id: str
    menu_name: str
    label: str

    @property
    def file(self) -> str:
        return self.id + SUFFIX


@dataclass(frozen=True)
class Manifest:
    title: str
    prompt: str
    entries: tuple[Entry, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(e.id for e in self.entries)


def read(path: Path = AQUARIUM) -> Manifest:
    """Parse a manifest; a malformed line raises ValueError naming path:line."""
    title, prompt, entries = "World Foundry", "Choose a game", []
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        where, line = f"{path}:{n}", raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, rest = line.partition(" ")
        rest = rest.strip()
        if key == "title":
            title = rest
        elif key == "prompt":
            prompt = rest
        elif key == "level":
            fields = [f.strip() for f in rest.split("|")]
            if not 2 <= len(fields) <= 3 or not all(fields):
                raise ValueError(f"{where}: want `level <id>{SUFFIX} | <menu name> [| <dream label>]`")
            if not fields[0].endswith(SUFFIX) or fields[0] == SUFFIX or "/" in fields[0]:
                raise ValueError(f"{where}: level file must be <id>{SUFFIX}, got {fields[0]!r}")
            entry = Entry(fields[0][:-len(SUFFIX)], fields[1], fields[2] if len(fields) == 3 else fields[1])
            if any(e.id == entry.id for e in entries):
                raise ValueError(f"{where}: level {entry.id!r} is listed twice")
            entries.append(entry)
        else:
            raise ValueError(f"{where}: unknown keyword {key!r} (want title, prompt or level)")
    if not entries:
        raise ValueError(f"{path}: no level lines")
    return Manifest(title, prompt, tuple(entries))
