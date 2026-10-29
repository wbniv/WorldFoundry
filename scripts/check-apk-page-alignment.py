#!/usr/bin/env python3
"""Fail an APK build if any packaged ELF library cannot load on 16 KiB pages."""
import argparse
from pathlib import Path
import struct
import sys
import zipfile

PAGE = 16384
PT_LOAD = 1


def load_segments(data):
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] not in (1, 2) or data[5] not in (1, 2):
        raise ValueError("invalid ELF header")
    bits = data[4]
    order = "<" if data[5] == 1 else ">"
    if bits == 2:
        phoff, = struct.unpack_from(order + "Q", data, 32)
        entsize, count = struct.unpack_from(order + "HH", data, 54)
        minimum = 56
    else:
        phoff, = struct.unpack_from(order + "I", data, 28)
        entsize, count = struct.unpack_from(order + "HH", data, 42)
        minimum = 32
    if count == 0 or entsize < minimum or phoff + entsize * count > len(data):
        raise ValueError("invalid program header table")
    segments = []
    for i in range(count):
        at = phoff + i * entsize
        typ, = struct.unpack_from(order + "I", data, at)
        if typ != PT_LOAD:
            continue
        if bits == 2:
            offset, address = struct.unpack_from(order + "QQ", data, at + 8)
            align, = struct.unpack_from(order + "Q", data, at + 48)
        else:
            offset, address = struct.unpack_from(order + "II", data, at + 4)
            align, = struct.unpack_from(order + "I", data, at + 28)
        segments.append((offset, address, align))
    if not segments:
        raise ValueError("ELF has no LOAD segment")
    return segments


def check(apk):
    problems = []
    with zipfile.ZipFile(apk) as bundle:
        libraries = sorted(name for name in bundle.namelist()
                           if name.startswith("lib/") and name.endswith(".so"))
        if not libraries:
            problems.append("APK has no packaged native libraries")
        for name in libraries:
            try:
                segments = load_segments(bundle.read(name))
            except (ValueError, struct.error, zipfile.BadZipFile) as error:
                problems.append(f"{name}: {error}")
                continue
            for index, (offset, address, align) in enumerate(segments):
                if align < PAGE or (offset - address) % PAGE:
                    problems.append(f"{name}: LOAD {index} has align={align}, "
                                    f"offset={offset}, vaddr={address}; needs 16 KiB")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    try:
        problems = check(args.apk)
    except (OSError, zipfile.BadZipFile) as error:
        problems = [str(error)]
    if problems:
        for problem in problems:
            print(f"APK page alignment: {problem}", file=sys.stderr)
        return 1
    print(f"APK page alignment: PASS ({args.apk})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
