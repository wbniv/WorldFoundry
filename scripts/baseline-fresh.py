#!/usr/bin/env python3
"""Prove the committed baseline outputs rebuild identically from their inputs (task baseline:fresh).

The baseline's built files are committed: the level bundles, the actor map, the compiled settings
catalogs and bindings, and the main cd.iff. A change to any input (baseline.blend, baseline.json,
memory-settings.json, a settings fixture, the exporter, a level tool) leaves them stale until
someone rebuilds. This runs the same build as `task baseline:build` and `task build-cd-iff`, and
compares the SHA-256 of every committed output before and after. A difference means the committed
file was stale; the file is left rebuilt, so commit it.

The Aquarium's `task aquarium-check` does this in a scratch copy of HEAD, in a container. The
baseline's build is host-only and needs tools built in the tree, so this rebuilds in place and
compares only the files it owns, which also works in a tree with other people's edits.

Exit codes: 0 fresh, 1 stale, 2 a build step failed.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STEPS = (
    ("baseline level", [sys.executable, "wflevels/baseline/build.py"]),
    ("main cd.iff", [sys.executable, "scripts/build-main-cd.py"]),
)
PATTERNS = (
    "wflevels/baseline-standalone.iff",
    "wflevels/baseline.iff",
    "wfsource/source/game/cd.iff",
    "wflevels/baseline/actor-map.json",
    "wflevels/baseline/settings-coverage.json",
    "wflevels/baseline/*.oas",
    "wflevels/baseline/*.oad",
    "wflevels/baseline/*-bindings.json",
)


def outputs():
    """Committed output files: tracked now, so a new untracked output is not judged."""
    listed = subprocess.run(["git", "ls-files", "--", *PATTERNS], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.split()
    return sorted(listed)


def digests(paths):
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() if (ROOT / p).is_file() else None
            for p in paths}


def main():
    argparse.ArgumentParser(description=__doc__.strip().splitlines()[0]).parse_args()
    paths = outputs()
    before = digests(paths)
    for label, command in STEPS:
        print("rebuilding %s ..." % label, flush=True)
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if done.returncode:
            print(done.stdout[-1500:] + done.stderr[-1500:])
            print("baseline outputs: the %s build failed (exit %d); freshness is unknown" % (label, done.returncode))
            return 2
    after = digests(paths)
    stale = [p for p in paths if before[p] != after[p]]
    if stale:
        print("baseline outputs STALE: %d of %d committed files do not rebuild identically:" % (len(stale), len(paths)))
        for path in stale:
            print("  changed  " + path)
        print("They are now rebuilt in the working tree; commit them with the input change.")
        return 1
    print("baseline outputs fresh: all %d committed files rebuild identically" % len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
