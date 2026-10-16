#!/usr/bin/env python3
"""Read-only shell-level winding evidence from the migration's original revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from audit_face_hand import chunks, cross, dot


def inspect(data):
    end = 8 + struct.unpack_from("<I", data, 4)[0]
    parts = {tag: data[a:b] for tag, _, a, b in chunks(data, 8, end)}
    vb, fb = parts[b"VRTX"], parts[b"FACE"]
    verts = [struct.unpack_from("<iii", vb, i + 12)
             for i in range(0, len(vb), 24)]
    faces = [struct.unpack_from("<hhhh", fb, i)[:3]
             for i in range(0, len(fb), 8)]
    parents = list(range(len(faces)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    edges = defaultdict(list)
    oriented = Counter()
    for i, face in enumerate(faces):
        a, b, c = [verts[v] for v in face]
        oriented[min((a, b, c), (b, c, a), (c, a, b))] += 1
        for x, y in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((x, y)))].append((i, x < y))
    for uses in edges.values():
        for (i, _), (j, _) in zip(uses, uses[1:]):
            parents[find(j)] = find(i)
    groups = defaultdict(list)
    for i in range(len(faces)):
        groups[find(i)].append(i)
    components = []
    for group in groups.values():
        selected = set(group)
        used_edges = [uses for uses in edges.values() if uses[0][0] in selected]
        closed = bool(used_edges) and all(len(uses) == 2 for uses in used_edges)
        consistent = all(len(uses) != 2 or uses[0][1] != uses[1][1]
                         for uses in used_edges)
        volume = sum(dot(verts[a], cross(verts[b], verts[c]))
                     for i in group for a, b, c in [faces[i]])
        components.append({"face_indices": group, "faces": len(group),
                           "closed": closed, "consistent": consistent,
                           "blender_volume6": volume})
    paired = 0
    for (a, b, c), count in oriented.items():
        reverse = min((a, c, b), (c, b, a), (b, a, c))
        paired += min(count, oriented[reverse])
    return {"opposite_paired_faces": paired, "components": components}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    inv = json.loads(args.inventory.read_text())
    cache, result = {}, {}
    for row in inv["models"] + inv["unmatched_embedded_models"]:
        model = None
        for ref in row["references"]:
            name = ref["path"]
            if name not in cache:
                cache[name] = subprocess.check_output(
                    ["git", "show", f"{inv['base_revision']}:{name}"], cwd=root)
            original = cache[name]
            at = ref["offset"]
            if original[at:at + 4] != b"MODL":
                continue  # A tracked symlink's Git blob contains its target path.
            size = struct.unpack_from("<I", original, at + 4)[0]
            candidate = original[at:(at + 8 + size + 3) & ~3]
            if hashlib.sha256(candidate).hexdigest() == row["sha256"]:
                model = candidate
                break
        if model is None:
            raise SystemExit(f"original model not found: {row['sha256']}")
        result[row["sha256"]] = inspect(model)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    mixed = sum(len({c["blender_volume6"] > 0 for c in r["components"]
                     if c["closed"] and c["consistent"] and c["blender_volume6"]}) > 1
                for r in result.values())
    print(f"{len(result)} models inspected; {mixed} have mixed closed-shell signs "
          f"-> {args.out}")


if __name__ == "__main__":
    main()
