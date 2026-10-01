"""Shared harness for the level-menu tests (docs/plans/2026-10-01-level-menu-selector.md).

Builds wfsource/source/game/level_menu.cc with its host main (level_menu_host.cc, -DWF_LEVEL_MENU_HOST) using the host
C++ compiler, AddressSanitizer and UBSan, and runs it on a list of stdin commands. Also: the bundle recipes, cdpack, and
a small reader for the GAME/TOC/MENU layout. No device, no display, no third-party Python packages (PIL only to render).
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GAME = REPO / "wfsource" / "source" / "game"
LEVELS = REPO / "wflevels"
CDPACK_DIR = REPO / "wftools" / "cdpack-rs"
CDPACK = CDPACK_DIR / "target" / "release" / "cdpack"
SHELL = GAME / "shell.fth"
SHELL_MENU = GAME / "shell-menu.fth"
SMB_MANIFEST = LEVELS / "smb-menu.manifest"
SMB_MENU_BUNDLE = LEVELS / "smb-menu-cd.iff"
SMB_LEVELS = [f"smb_w1_{n}-standalone.iff" for n in (1, 2, 3, 4)]

# Every tracked bundle built without a manifest, with its recipe (Taskfile.yml build-cd-iff*): shell.fth + these levels.
PLAIN_BUNDLES = {
    "wfsource/source/game/cd.iff": SMB_LEVELS + ["snowgoons-standalone.iff", "qbert_practice-standalone.iff",
                                                  "marble-madness-3d-astra-standalone.iff"],
    "wflevels/smb-cd.iff": SMB_LEVELS,
    "wflevels/snowgoons-cd.iff": ["snowgoons-standalone.iff"],
    "wflevels/qbert-cd.iff": ["qbert_practice-standalone.iff"],
    "wflevels/aquarium-cd.iff": ["aquarium-standalone.iff"],
    "wflevels/condo-cd.iff": ["condo_639_640-standalone.iff"],
}


def cdpack_binary() -> Path:
    subprocess.run(["cargo", "build", "--release", "--quiet", "--manifest-path", str(CDPACK_DIR / "Cargo.toml")], check=True)
    return CDPACK


def cdpack(*args, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run([str(cdpack_binary()), *map(str, args)], capture_output=True, text=True, check=check)


def read_toc(data: bytes) -> list[tuple[bytes, int, int]]:
    """[(tag, offset, size), ...] from sector 0 of a bundle."""
    assert data[:4] == b"GAME" and data[8:12] == b"TOC\0", "not a GAME/TOC bundle"
    size = struct.unpack_from("<I", data, 12)[0]
    return [(data[o:o + 4], *struct.unpack_from("<II", data, o + 4)) for o in range(16, 16 + size, 12)]


def read_menu(data: bytes) -> dict:
    """The MENU chunk of a bundle (cdpack --manifest), decoded."""
    tag, off, size = read_toc(data)[-1]
    assert tag == b"MENU", f"last TOC entry is {tag!r}, not MENU"
    chunk = data[off:off + size]
    assert chunk[:4] == b"MENU" and struct.unpack_from("<I", chunk, 4)[0] + 8 == size
    version, levels, count = struct.unpack_from("<III", chunk, 8)
    at = 20
    def text():
        nonlocal at
        n = struct.unpack_from("<H", chunk, at)[0]
        s = chunk[at + 2:at + 2 + n].decode("ascii")
        at += 2 + n
        return s
    title, prompt = text(), text()
    entries = []
    for _ in range(count):
        level = struct.unpack_from("<I", chunk, at)[0]
        at += 4
        entries.append((level, text()))
    return {"version": version, "levels": levels, "title": title, "prompt": prompt, "entries": entries}


def build_host(out_dir: Path) -> Path:
    cxx = shutil.which(os.environ.get("CXX", "g++")) or shutil.which("c++")
    assert cxx, "no host C++ compiler"
    flags = ["-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]
    objs = []
    for src, extra in ((GAME / "level_menu.cc", []), (GAME / "level_menu_host.cc", ["-DWF_LEVEL_MENU_HOST"])):
        obj = out_dir / (src.name + ".o")
        subprocess.run([cxx, *flags, *extra, "-c", str(src), "-o", str(obj)], check=True)
        objs.append(str(obj))
    exe = out_dir / "level_menu_host"
    subprocess.run([cxx, "-fsanitize=address,undefined", *objs, "-o", str(exe)], check=True)
    return exe


def run_host(exe: Path, commands: list[str]) -> list[str]:
    """Feed the commands, return the output lines (the host exits at end of input)."""
    p = subprocess.run([str(exe)], input="\n".join(commands) + "\n", capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, f"host exited {p.returncode}: {p.stderr[-2000:]}"
    return p.stdout.splitlines()


def states(lines: list[str]) -> list[dict]:
    """The STATE lines as dicts of ints."""
    out = []
    for line in lines:
        if line.startswith("STATE "):
            out.append({k: int(v) for k, v in (kv.split("=") for kv in line.split()[1:])})
    return out


def rects(lines: list[str]) -> tuple[bool, list]:
    """The last RECTS block: (changed, [(x0, y0, x1, y1, (r, g, b, a)), ...])."""
    i = max(n for n, line in enumerate(lines) if line.startswith("RECTS "))
    count, changed = lines[i].split()[1], lines[i].split()[2] == "changed=1"
    out = []
    for line in lines[i + 1:i + 1 + int(count)]:
        _, x0, y0, x1, y1, c = line.split()
        c = int(c, 16)
        out.append((float(x0), float(y0), float(x1), float(y1), (c >> 24, (c >> 16) & 255, (c >> 8) & 255, c & 255)))
    return changed, out
