#!/usr/bin/env python3
"""Compare a rebuilt tree with a commit: list every tracked file the rebuild changed.

Usage: scripts/level-outputs-compare.py [-h] --repo DIR --ref REF --tree DIR
                                        [--regenerate CMD] -- PATHSPEC...

For every file REF tracks under PATHSPEC (the files `git archive` exports), hash the file of the
same path in --tree as a Git blob and compare it with REF's blob. A file that
differs is stale: REF's inputs no longer produce it. Files the rebuild created
and REF does not track (gitignored intermediates) are not compared.

Exit 0 when every tracked file is identical; 1 when any is stale or missing,
printing the list and --regenerate, the one command that rebuilds them.
Called by scripts/aquarium-levels.sh check; tests/test_level_outputs_check.py
covers it.
"""
import argparse
import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tracked(repo: str, ref: str, pathspecs: list[str]) -> dict[str, str]:
    """{path: blob id} of REF's files under PATHSPECS (glob magic allowed, as in git archive)."""
    names = subprocess.run(["git", "-C", repo, "archive", "--format=tar", ref, "--", *pathspecs],
                           capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(names)) as tar:
        wanted = {m.name for m in tar if m.isfile()}  # symlinks are not build outputs
    out = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "-z", "--full-tree", ref],
                         capture_output=True, check=True).stdout
    files = {}
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        name = path.decode()
        if name in wanted:
            files[name] = meta.split()[2].decode()
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--tree", required=True, type=Path)
    ap.add_argument("--regenerate", default="task aquarium-regenerate")
    ap.add_argument("pathspecs", nargs="+")
    a = ap.parse_args()
    files = tracked(a.repo, a.ref, a.pathspecs)
    stale, missing = [], []
    for path, oid in sorted(files.items()):
        p = a.tree / path
        if not p.is_file():
            missing.append(path)
        elif blob_id(p.read_bytes()) != oid:
            stale.append(path)
    short = subprocess.run(["git", "-C", a.repo, "rev-parse", "--short=12", a.ref],
                           capture_output=True, text=True, check=True).stdout.strip()
    if not stale and not missing:
        print(f"level outputs fresh: all {len(files)} tracked files rebuild identically from {short}")
        return 0
    print(f"level outputs STALE: {len(stale) + len(missing)} of {len(files)} tracked files "
          f"do not rebuild identically from {short}:")
    for path in stale:
        print(f"  changed  {path}")
    for path in missing:
        print(f"  missing  {path}")
    print(f"Regenerate them with `{a.regenerate}`, then commit the changed files.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
