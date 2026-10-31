#!/usr/bin/env python3
"""Pack the main cd.iff: shell.fth plus the levels of wflevels/main-cd.manifest, in that order.

This is `task build-cd-iff`. It replaces a hand-written list of levels in the Taskfile, so the
manifest is the only place a level is added. The bundle is a plain pack (no menu): the manifest's
paths go to cdpack as positional arguments, not through `cdpack --manifest`.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "wfsource/source/game/shell.fth"
OUTPUT = ROOT / "wfsource/source/game/cd.iff"
CDPACK = ROOT / "wftools/cdpack-rs/target/release/cdpack"


def manifest_module():
    spec = importlib.util.spec_from_file_location("cd_manifest", ROOT / "scripts/cd_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT, help="bundle to write (default: %(default)s)")
    args = parser.parse_args()
    if not CDPACK.is_file():
        sys.exit("cdpack is not built: cargo build --release --manifest-path wftools/cdpack-rs/Cargo.toml")
    levels = manifest_module().load()
    command = [str(CDPACK), str(SHELL)] + [str(level.path) for level in levels] + ["-o", str(args.output)]
    print("main cd.iff: %d levels from wflevels/main-cd.manifest" % len(levels))
    sys.exit(subprocess.run(command).returncode)


if __name__ == "__main__":
    main()
