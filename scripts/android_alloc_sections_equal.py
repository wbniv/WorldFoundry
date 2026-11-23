#!/usr/bin/env python3
"""Compare the loaded sections of two ELF shared objects, byte for byte.

Used to prove an Android library did not change when only names did
(finding-your-way docs/plans/2026-11-08-ios-touch-parity.md, layer 1b:
hal/android/touch_controls.h became an alias of hal/touch_controls.h, and the
local symbols' mangled names went from androidtouch:: to wftouch::).

Every section with SHF_ALLOC (what the loader maps: code, read-only data,
data, dynamic tables) is compared by name, address, size and contents, except
.note.gnu.build-id, which hashes the whole file and so changes whenever
.symtab or the debug sections do. Non-allocated sections (.symtab, .strtab,
.debug_*, .comment) are listed but not compared.

Pure Python, ELF32 and ELF64 little-endian. Exit 0 when identical.
Usage: android_alloc_sections_equal.py BASE.so HEAD.so
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

SHF_ALLOC = 0x2
SHT_NOBITS = 8
IGNORED = {".note.gnu.build-id"}


def sections(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[5] != 1:
        raise SystemExit(f"{path}: not a little-endian ELF file")
    is64 = data[4] == 2
    if is64:
        shoff, = struct.unpack_from("<Q", data, 0x28)
        shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
        fmt = "<IIQQQQIIQQ"
    else:
        shoff, = struct.unpack_from("<I", data, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x2E)
        fmt = "<IIIIIIIIII"
    hdrs = [struct.unpack_from(fmt, data, shoff + i * shentsize) for i in range(shnum)]
    strtab = hdrs[shstrndx]
    stroff = strtab[4]

    def name(off: int) -> str:
        end = data.index(b"\0", stroff + off)
        return data[stroff + off:end].decode()

    out = {}
    for h in hdrs[1:]:
        sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = h[:6]
        body = b"" if sh_type == SHT_NOBITS else data[sh_offset:sh_offset + sh_size]
        out[name(sh_name)] = {"alloc": bool(sh_flags & SHF_ALLOC), "addr": sh_addr, "size": sh_size,
                              "sha": hashlib.sha256(body).hexdigest()[:16]}
    return out


def compare(base: Path, head: Path) -> int:
    a, b = sections(base), sections(head)
    alloc = sorted({n for n, s in a.items() if s["alloc"]} | {n for n, s in b.items() if s["alloc"]},
                   key=lambda n: (a.get(n) or b.get(n))["addr"])
    differ = 0
    print(f"base {base} ({base.stat().st_size} bytes)\nhead {head} ({head.stat().st_size} bytes)")
    print("loaded sections (SHF_ALLOC):")
    for n in alloc:
        sa, sb = a.get(n), b.get(n)
        if n in IGNORED:
            print(f"  {n:24} ignored (hashes the whole file)")
            continue
        same = sa is not None and sb is not None and (sa["addr"], sa["size"], sa["sha"]) == (sb["addr"], sb["size"], sb["sha"])
        differ += 0 if same else 1
        fmt = lambda s: "missing" if s is None else f"addr 0x{s['addr']:x} size {s['size']} sha256 {s['sha']}"
        print(f"  {n:24} {'identical' if same else 'DIFFERENT'}  {fmt(sa)}" + ("" if same else f"  vs  {fmt(sb)}"))
    other = sorted(n for n in set(a) | set(b) if not ((a.get(n) or b.get(n))["alloc"]))
    changed = [n for n in other if (a.get(n) or {}).get("sha") != (b.get(n) or {}).get("sha")]
    print(f"not loaded, not compared: {', '.join(other)}")
    print(f"  of which changed: {', '.join(changed) or 'none'}")
    print(f"RESULT: {'IDENTICAL' if not differ else f'{differ} loaded section(s) differ'}")
    return 0 if not differ else 1


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    return compare(Path(argv[0]), Path(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
