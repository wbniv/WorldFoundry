#!/usr/bin/env python3
"""Read-only inventory of tracked standalone MODL face winding.

Geometry scores are review clues, never migration decisions. In particular,
open sheets and intentional interior surfaces cannot be classified by volume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


def chunks(data: bytes, start: int, end: int, *, allow_unaligned: bool = False):
    def header_at(pos: int) -> bool:
        if pos + 8 > end:
            return False
        tag = data[pos:pos + 4]
        if not tag.strip(b"\0 ") or any(
                byte not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ \0"
                for byte in tag):
            return False
        size = struct.unpack_from("<I", data, pos + 4)[0]
        return pos + 8 + size <= end

    at = start
    while at < end:
        if at + 8 > end:
            if all(byte == 0 for byte in data[at:end]):
                break
            raise ValueError(f"truncated chunk header at {at}")
        tag = data[at : at + 4]
        size = struct.unpack_from("<I", data, at + 4)[0]
        body = at + 8
        stop = body + size
        aligned = (stop + 3) & ~3
        # Some historical packed GAME bundles put the next chunk immediately
        # after an odd-sized SHEL payload; model chunks remain 4-byte aligned.
        nxt = stop if allow_unaligned and header_at(stop) else aligned
        if stop > end or nxt > end:
            raise ValueError(f"invalid {tag!r} chunk size at {at}")
        yield tag, at, body, stop
        at = nxt


WRAPPERS = {b"GAME", b"LVAS", b"PERM", b"OADL", b"TYPE", b"UDM\0",
            b"IFFC"} | {f"L{i}".encode().ljust(4, b"\0") for i in range(10)} \
           | {f"RM{i}".encode().ljust(4, b"\0") for i in range(5)}


def find_models(data: bytes, start: int = 0, end: int | None = None,
                *, allow_unaligned: bool = False):
    """Walk IFF chunk boundaries; ASS records prefix their nested asset with an ID."""
    if end is None:
        end = len(data)
    for tag, header, body, stop in chunks(
            data, start, end, allow_unaligned=allow_unaligned):
        if tag == b"MODL":
            yield header, data[header:((stop + 3) & ~3)]
        elif tag in WRAPPERS:
            yield from find_models(data, body, stop,
                                   allow_unaligned=(tag == b"GAME"))
        elif tag == b"ASS\0" and body + 12 <= stop:
            # An ASS payload starts with a 4-byte asset ID, then one IFF chunk.
            asset_start = body + 4
            if data[asset_start:asset_start + 4] == b"MODL":
                yield from find_models(data, asset_start, stop)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def inspect_model(data: bytes):
    if data[:4] != b"MODL":
        raise ValueError("not a standalone MODL")
    size = struct.unpack_from("<I", data, 4)[0]
    if size + 8 > len(data):
        raise ValueError("truncated MODL")
    parts = {tag: data[a:b] for tag, _, a, b in chunks(data, 8, size + 8)}
    vb, fb = parts.get(b"VRTX", b""), parts.get(b"FACE", b"")
    mb = parts.get(b"MATL", b"")
    if not vb or len(vb) % 24 or not fb or len(fb) % 8:
        raise ValueError("invalid VRTX or FACE length")
    if mb and len(mb) % 264:
        raise ValueError("invalid MATL length")
    verts = [struct.unpack_from("<iii", vb, at + 12)
             for at in range(0, len(vb), 24)]
    vert_keys = [(*xyz, *struct.unpack_from("<ii", vb, at))
                 for at, xyz in zip(range(0, len(vb), 24), verts)]
    faces = [struct.unpack_from("<hhhh", fb, at)
             for at in range(0, len(fb), 8)]
    geometry_hash = hashlib.sha256(
        json.dumps({"positions": verts,
                    "triangles": [face[:3] for face in faces]},
                   separators=(",", ":")).encode()).hexdigest()
    if any(min(a, b, c) < 0 or max(a, b, c) >= len(verts)
           for a, b, c, _ in faces):
        raise ValueError("FACE index out of range")
    # Weld identical positions for topological clues: UV seams split VRTX rows.
    welded = {p: i for i, p in enumerate(sorted(set(verts)))}
    edges = Counter()
    material_faces = Counter()
    volume6 = 0
    zero_area = 0
    normal_sum = [0, 0, 0]
    centre2 = tuple(min(p[i] for p in verts) + max(p[i] for p in verts)
                    for i in range(3))
    radial = Counter()
    for a, b, c, mat in faces:
        material_faces[mat] += 1
        pa, pb, pc = verts[a], verts[b], verts[c]
        ab, ac = sub(pb, pa), sub(pc, pa)
        n = cross(ab, ac)  # Blender's proposed normal before normalization.
        if n == (0, 0, 0):
            zero_area += 1
        direction6 = tuple(2 * (pa[i] + pb[i] + pc[i]) - 3 * centre2[i]
                           for i in range(3))
        radial_score = dot(n, direction6)
        radial["outward" if radial_score > 0 else
               "inward" if radial_score < 0 else "tangent"] += 1
        for i in range(3):
            normal_sum[i] += n[i]
        volume6 += dot(pa, cross(pb, pc))
        wa, wb, wc = welded[pa], welded[pb], welded[pc]
        for x, y in ((wa, wb), (wb, wc), (wc, wa)):
            edges[tuple(sorted((x, y)))] += 1
    edge_counts = Counter(edges.values())
    return {
        "vertices": len(verts), "faces": len(faces),
        "geometry_sha256": geometry_hash,
        "sorted_vertex_keys": vert_keys == sorted(vert_keys),
        "sorted_face_rows": faces == sorted(faces),
        "materials": dict(sorted(material_faces.items())),
        "material_flags": [struct.unpack_from("<I", mb, at)[0]
                           for at in range(0, len(mb), 264)],
        "zero_area_faces": zero_area,
        "boundary_edges": edge_counts[1], "nonmanifold_edges": sum(
            count for uses, count in edge_counts.items() if uses > 2),
        "closed_after_position_weld": bool(edges) and set(edge_counts) == {2},
        "blender_signed_volume6": volume6,
        "blender_area_normal_sum": normal_sum,
        "blender_radial_face_counts": dict(radial),
        "decision": "unresolved",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    names = subprocess.check_output(["git", "ls-files", "*.iff"],
                                    cwd=root, text=True).splitlines()
    models = defaultdict(list)
    errors = []
    roots = Counter()
    for name in names:
        data = (root / name).read_bytes()
        roots[data[:4].decode("latin1")] += 1
        if data[:4] != b"MODL":
            continue
        digest = hashlib.sha256(data).hexdigest()
        models[digest].append(name)
    result = []
    for digest, paths in sorted(models.items(), key=lambda item: item[1][0]):
        try:
            info = inspect_model((root / paths[0]).read_bytes())
            result.append({"sha256": digest, "paths": paths, **info})
        except ValueError as exc:
            errors.append({"sha256": digest, "paths": paths, "error": str(exc)})
    references = defaultdict(list)
    embedded_bytes = {}
    container_errors = []
    for name in names:
        data = (root / name).read_bytes()
        if data[:4] not in WRAPPERS and data[:4] != b"MODL":
            continue
        try:
            for offset, model in find_models(data):
                digest = hashlib.sha256(model).hexdigest()
                references[digest].append({"path": name, "offset": offset})
                embedded_bytes.setdefault(digest, model)
        except ValueError as exc:
            container_errors.append({"path": name, "error": str(exc)})
    for row in result:
        row["references"] = references.pop(row["sha256"], [])
    unmatched = []
    for digest, refs in sorted(references.items(), key=lambda item: item[1][0]["path"]):
        try:
            unmatched.append({"sha256": digest, "paths": [],
                              "references": refs,
                              **inspect_model(embedded_bytes[digest])})
        except ValueError as exc:
            errors.append({"sha256": digest, "references": refs,
                           "error": str(exc)})
    report = {
        "base_revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                 cwd=root, text=True).strip(),
        "tracked_iff_files": len(names), "root_tags": dict(sorted(roots.items())),
        "standalone_modl_files": sum(len(paths) for paths in models.values()),
        "distinct_modl_hashes": len(models), "models": result, "errors": errors,
        "unmatched_embedded_models": unmatched,
        "container_errors": container_errors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(result)} models, {len(errors)} errors -> {args.out}")


if __name__ == "__main__":
    main()
