#!/usr/bin/env python3
"""Rebuild every committed level with two levcomp builds and compare the .lvl bytes.

    scripts/levcomp-level-parity.py --base-levcomp OLD --base-oad OLD_OAS_DIR \
        --new-levcomp NEW [--new-oad wfsource/source/oas] [--rev HEAD]

Every tracked ``wflevels/**/*.lev`` is read at ``--rev`` (so other people's
uncommitted edits to a source don't count), compiled with iffcomp, then with
each levcomp against its own schema directory. For each level it reports:

* ``identical``: the two .lvl files are byte-identical;
* ``levelobj-append +N``: they differ only because the Level Object payload
  grew by N bytes at its end (fields appended to levelobj.oas). Every other
  object header and payload, the path, channel and room records and the common
  area are compared with the file offsets taken out, and must match;
* ``DIFFERENT``: anything else, with the first differing section.

It also says whether the base build reproduces the level's committed .lvl,
when there is one. Exit status is 1 when any level is DIFFERENT or fails to
build. Run it in the container (scripts/in-linux-container.sh).
"""
from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEVELOBJ_KIND = 15      # Actor::LevelObj_KIND (objects.lc order)
OBJ_HEADER = 68         # sizeof(_ObjectOnDisk); OADSize is the int16 at 66


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True).stdout


def mesh_dir_for(level_dir: Path) -> Path:
    """The MESH_DIR of wflevels/<level>/mesh.flags, as build_level_binary.sh reads it."""
    flags = level_dir / "mesh.flags"
    if flags.exists():
        for line in flags.read_text().splitlines():
            line = line.strip()
            if line.startswith("MESH_DIR="):
                return (level_dir / line.split("=", 1)[1].strip().strip('"')).resolve()
    return level_dir


def compile_lvl(iffcomp: Path, levcomp: Path, oad: Path, lev_text: bytes, level_dir: Path,
                work: Path) -> bytes:
    work.mkdir(parents=True, exist_ok=True)
    (work / "level.lev").write_bytes(lev_text)
    subprocess.run([str(iffcomp), "-binary", f"-o={work / 'level.lev.bin'}", str(work / "level.lev")],
                   check=True, cwd=work, capture_output=True)
    subprocess.run([str(levcomp), "level.lev.bin", str(oad / "objects.lc"), "level.lvl", str(oad),
                    "--mesh-dir", str(mesh_dir_for(level_dir)), "--iff-txt", "level.iff.txt",
                    "--textile-ini", "level.ini"], check=True, cwd=work, capture_output=True)
    return (work / "level.lvl").read_bytes()


def sections(lvl: bytes) -> dict:
    """Split a .lvl into position-independent parts (file offsets removed)."""
    h = struct.unpack_from("<13i", lvl, 0)
    _, n_obj, obj_off, n_path, path_off, n_ch, ch_off, _, _, n_room, room_off, common_len, common_off = h
    objects = []
    for i in range(n_obj):
        at = struct.unpack_from("<i", lvl, obj_off + 4 * i)[0]
        kind = struct.unpack_from("<h", lvl, at)[0]
        size = struct.unpack_from("<h", lvl, at + 66)[0]
        objects.append((kind, lvl[at:at + 66], lvl[at + OBJ_HEADER:at + OBJ_HEADER + size]))

    def table(count: int, off: int, end: int) -> tuple:
        if count == 0:
            return ((), lvl[off:end])
        offs = struct.unpack_from(f"<{count}i", lvl, off)
        base = off + 4 * count
        return (tuple(o - base for o in offs), lvl[base:end])

    return {
        "version": h[0],
        "objects": objects,
        "paths": table(n_path, path_off, ch_off),
        "channels": table(n_ch, ch_off, room_off),
        "rooms": table(n_room, room_off, common_off),
        "common": lvl[common_off:common_off + common_len],
    }


def classify(base: bytes, new: bytes) -> str:
    if base == new:
        return "identical"
    a, b = sections(base), sections(new)
    for key in ("version", "paths", "channels", "rooms", "common"):
        if a[key] != b[key]:
            return f"DIFFERENT ({key})"
    if len(a["objects"]) != len(b["objects"]):
        return "DIFFERENT (object count)"
    growth = set()
    for i, ((ka, ha, pa), (kb, hb, pb)) in enumerate(zip(a["objects"], b["objects"])):
        if ka != kb or ha != hb:
            return f"DIFFERENT (object {i} header)"
        if pa == pb:
            continue
        if ka != LEVELOBJ_KIND or len(pb) <= len(pa) or pb[:len(pa)] != pa:
            return f"DIFFERENT (object {i} payload)"
        growth.add(len(pb) - len(pa))
    if len(growth) != 1:
        return "DIFFERENT (unexplained)"
    return f"levelobj-append +{growth.pop()}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-levcomp", type=Path, required=True)
    ap.add_argument("--base-oad", type=Path, required=True, help="schema dir for the base build")
    ap.add_argument("--new-levcomp", type=Path, required=True)
    ap.add_argument("--new-oad", type=Path, default=REPO / "wfsource" / "source" / "oas")
    ap.add_argument("--iffcomp", type=Path, required=True)
    ap.add_argument("--rev", default="HEAD", help="git revision the .lev sources are read at")
    ap.add_argument("--keep", type=Path, help="keep the work tree here instead of a temp dir")
    args = ap.parse_args()

    # Mode 120000 entries are symlinks to another level's .lev; that level is compiled anyway.
    levs = []
    for entry in git("ls-files", "-s", "-z", "--", "wflevels").decode().split("\0"):
        if entry.endswith(".lev") and not entry.startswith("120000"):
            levs.append(entry.split("\t", 1)[1])
    work_root = args.keep or Path(tempfile.mkdtemp(prefix="levcomp-parity-"))
    counts: dict[str, int] = {}
    failed = False
    for rel in sorted(levs):
        level_dir = (REPO / rel).parent
        text = git("show", f"{args.rev}:{rel}")
        work = work_root / rel.replace("/", "__")
        try:
            base = compile_lvl(args.iffcomp, args.base_levcomp, args.base_oad, text, level_dir, work / "base")
            new = compile_lvl(args.iffcomp, args.new_levcomp, args.new_oad, text, level_dir, work / "new")
        except subprocess.CalledProcessError as e:
            print(f"{rel:62s} BUILD FAILED: {e.stderr.decode(errors='replace').strip()[-200:]}")
            failed = True
            counts["BUILD FAILED"] = counts.get("BUILD FAILED", 0) + 1
            continue
        verdict = classify(base, new)
        committed_rel = rel[:-4] + ".lvl"
        try:
            committed = git("show", f"{args.rev}:{committed_rel}")
            vs = "base == committed .lvl" if committed == base else "base != committed .lvl"
        except subprocess.CalledProcessError:
            vs = "no committed .lvl"
        print(f"{rel:62s} {verdict:24s} {vs}")
        bucket = verdict.split(" (")[0]
        counts[bucket] = counts.get(bucket, 0) + 1
        failed |= verdict.startswith("DIFFERENT")
    if not args.keep:
        shutil.rmtree(work_root, ignore_errors=True)
    print("summary:", ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
