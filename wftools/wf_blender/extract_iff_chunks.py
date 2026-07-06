"""
Extract named chunk payloads from a WF level .iff file.

Usage:
  python extract_iff_chunks.py <input.iff> <outdir> [CHUNK1 CHUNK2 ...]

Writes <outdir>/<CHUNK>.bin for each requested FOURCC found inside the
top-level LVAS container.  Default chunks: ASMP PERM RM0 RM1 RM2 RM3 RM4.

IFF on-disk layout (iffcomp-rs / iffcomp format):
  [4] FOURCC  — big-endian u32
  [4] size    — little-endian u32 (payload bytes, NOT including header or pad)
  [N] payload
  [0-3] zero-pad to 4-byte boundary (not counted in size)
"""

import struct
import sys
import os


def fourcc_str(b: bytes) -> str:
    return b.decode("latin-1").rstrip("\x00").rstrip()


def read_chunk_header(data: bytes, pos: int):
    if pos + 8 > len(data):
        return None
    fourcc = data[pos:pos+4]
    size = struct.unpack_from("<I", data, pos+4)[0]
    payload_start = pos + 8
    payload_end = payload_start + size
    aligned_end = (payload_end + 3) & ~3
    return fourcc, size, payload_start, payload_end, aligned_end


def find_lvas(data: bytes, start: int, end: int) -> tuple[int, int] | None:
    """Recursively search for LVAS within data[start:end]. Returns (payload_start, payload_end)."""
    pos = start
    while pos < end:
        hdr = read_chunk_header(data, pos)
        if hdr is None:
            break
        fourcc, size, payload_start, payload_end, aligned_end = hdr
        name = fourcc_str(fourcc)
        if name == "LVAS":
            return payload_start, payload_end
        if name == "ALGN":
            pos = aligned_end
            continue
        # Recurse into any non-leaf chunk (try it as a container)
        result = find_lvas(data, payload_start, payload_end)
        if result:
            return result
        pos = aligned_end
    return None


def extract_chunks(data: bytes, targets: set[str]) -> dict[str, bytes]:
    results = {}

    lvas = find_lvas(data, 0, len(data))
    if lvas is None:
        raise ValueError("LVAS chunk not found in file")
    lvas_payload_start, lvas_payload_end = lvas

    pos = lvas_payload_start
    while pos < lvas_payload_end:
        hdr = read_chunk_header(data, pos)
        if hdr is None:
            break
        fourcc, size, payload_start, payload_end, aligned_end = hdr
        name = fourcc_str(fourcc)
        if name in targets:
            results[name] = data[payload_start:payload_end]
        pos = aligned_end

    return results


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    in_path = args[0]
    out_dir = args[1]
    chunks = set(args[2:]) if len(args) > 2 else {"ASMP", "PERM", "RM0", "RM1", "RM2", "RM3", "RM4"}

    data = open(in_path, "rb").read()
    os.makedirs(out_dir, exist_ok=True)

    found = extract_chunks(data, chunks)
    for name, payload in found.items():
        out_path = os.path.join(out_dir, f"{name}.bin")
        with open(out_path, "wb") as f:
            f.write(payload)
        print(f"  {name}: {len(payload)} bytes → {out_path}")

    missing = chunks - set(found)
    if missing:
        print(f"WARNING: not found: {', '.join(sorted(missing))}", file=sys.stderr)


if __name__ == "__main__":
    main()
