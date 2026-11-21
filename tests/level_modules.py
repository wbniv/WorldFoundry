"""Import one level's generator modules (timeline, parts, forth, ...) without clashing with another level's.

Every clock level has a timeline.py, a parts.py and a forth.py, imported by their plain names from the level's
directory. In one pytest process the first level's modules would stay in sys.modules and the second level's
tests would silently get them (found 2026-11-21: Minute Machine's parts tests failed when run after Tide
Harbour's). load() clears those names, imports the level's modules from its directory, and clears the names
again, so each caller keeps its own module objects and the next level imports its own.

    tl, parts, forth = level_modules.load("tide_harbour", "timeline", "parts", "forth")
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(level: str, *names: str):
    directory = str(ROOT / "wflevels" / level)
    for name in names:
        sys.modules.pop(name, None)
    sys.path.insert(0, directory)
    try:
        modules = [importlib.import_module(name) for name in names]
        for name, module in zip(names, modules):
            assert Path(module.__file__).parent == Path(directory), (name, module.__file__)
    finally:
        sys.path.remove(directory)
        for name in names:
            sys.modules.pop(name, None)
    return modules[0] if len(modules) == 1 else modules
