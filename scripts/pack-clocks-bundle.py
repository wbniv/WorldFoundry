#!/usr/bin/env python3
"""Pack every clock of wflevels/clocks-menu.manifest into the WF Clocks cd.iff and link it into the clocks flavor.

    python3 scripts/pack-clocks-bundle.py [-h] [--manifest PATH] [--output PATH] [--no-link]

The manifest is the roster: its `level` lines, in order, are the bundle's levels (the order is the
TOC index the Dream and the LEVEL extra start), and cdpack adds the MENU chunk the engine's chooser
reads. The shell is shell-menu.fth, so a run with no positional level shows the chooser. Every
manifest id needs wflevels/<id>-standalone.iff (Minute Machine: task minute-machine-level); a
missing one stops the pack with the ids named, never a bundle without them. Needs the cdpack tool
(cargo build --release in wftools/cdpack-rs, or point WF_CDPACK at one). Writes
wflevels/clocks-cd.iff and symlinks it as android/screensaver/src/clocks/assets/cd.iff.
Plan: docs/plans/2026-11-21-tide-harbour-clock.md, "The bundle and the chooser".
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import level_manifest  # noqa: E402

MANIFEST = ROOT / "wflevels/clocks-menu.manifest"
BUNDLE = ROOT / "wflevels/clocks-cd.iff"
ASSETS = ROOT / "android/screensaver/src/clocks/assets"
SHELL_MENU = ROOT / "wfsource/source/game/shell-menu.fth"


def missing_levels(manifest: Path) -> list[str]:
    """The manifest ids whose <id>-standalone.iff is not beside the manifest, in manifest order."""
    entries = level_manifest.read(manifest).entries
    return [e.id for e in entries if not (manifest.parent / e.file).is_file()]


def pack(manifest: Path, output: Path, cdpack: Path) -> None:
    """Check the roster, then cdpack it; ValueError names what is wrong."""
    missing = missing_levels(manifest)
    if missing:
        raise ValueError(f"{manifest} lists {', '.join(missing)} but no level is built for "
                         + ("it" if len(missing) == 1 else "them")
                         + f" (want {', '.join(m + level_manifest.SUFFIX for m in missing)} in {manifest.parent})")
    if not cdpack.exists():
        raise ValueError(f"cdpack not built: {cdpack} (cargo build --release in wftools/cdpack-rs, or set WF_CDPACK)")
    subprocess.run([str(cdpack), str(SHELL_MENU), "--manifest", str(manifest), "-o", str(output)],
                   cwd=ROOT, check=True)
    if b"UIFT" not in output.read_bytes()[:2048]:
        raise ValueError("cdpack is stale: rebuild wftools/cdpack-rs to include the UI font")


def link(bundle: Path, assets: Path = ASSETS) -> None:
    assets.mkdir(parents=True, exist_ok=True)
    target = assets / "cd.iff"
    if target.is_symlink() or target.exists():
        target.unlink()
    target.symlink_to(Path(os.path.relpath(bundle, assets)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=MANIFEST, help="default: %(default)s")
    parser.add_argument("--output", type=Path, default=BUNDLE, help="default: %(default)s")
    parser.add_argument("--no-link", action="store_true", help="do not link the bundle into the clocks flavor")
    args = parser.parse_args(argv)
    cdpack = Path(os.environ.get("WF_CDPACK", ROOT / "wftools/cdpack-rs/target/release/cdpack"))
    try:
        pack(args.manifest.resolve(), args.output.resolve(), cdpack)
    except ValueError as error:
        print(f"pack-clocks-bundle: {error}", file=sys.stderr)
        return 2
    if not args.no_link:
        link(args.output.resolve())
    print(f"clocks bundle: {args.output} ({', '.join(level_manifest.read(args.manifest).ids)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
