"""The snowgoons arena's floor and hedge tops face up in every tracked copy.

25a57d73 switched the engine to Blender's face normal, (v1-v0) x (v2-v0), and
migrated each stored model by a reviewed keep/reverse decision. The arena
(quadpatch01: a 481-vertex, 445-face ground sheet with hedge walls) was marked
`keep` on exterior-shell clues, so its normals flipped: all 283 horizontal faces
pointed down, and GL and Metal both culled the floor and hedges from the level
camera. The macOS frame gate caught it; nothing on Linux did. See
docs/diagnostics/metal-snowgoons-cull-2026-10-17/README.md.

This check needs no engine or display. The arena is found by its vertex
positions, which no face-order change alters, so it covers the source models,
the level bundles, the CD images and any future copy.
"""

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_face_hand import chunks, cross, find_models, sub  # noqa: E402

# sha256 of json.dumps(sorted(VRTX positions)), shared by the snowgoons-blender
# and the classic snowgoons variants (they differ only in materials).
ARENA_POSITIONS = "c58be937ff2822b0"
HORIZONTAL_FACES = 283   # 176 floor (material 5) + 107 hedge tops (material 1)


def _arena_models():
    names = subprocess.check_output(["git", "ls-files", "*.iff"], cwd=ROOT, text=True).splitlines()
    for name in names:
        path = ROOT / name
        if path.is_symlink():
            continue
        data = path.read_bytes()
        if b"MODL" not in data:
            continue
        try:
            models = list(find_models(data))
        except ValueError:
            continue
        for at, model in models:
            size = struct.unpack_from("<I", model, 4)[0]
            parts = {tag: model[a:b] for tag, _, a, b in chunks(model, 8, size + 8)}
            vrtx, face = parts.get(b"VRTX", b""), parts.get(b"FACE", b"")
            if len(vrtx) != 481 * 24 or len(face) != 445 * 8:
                continue
            verts = [struct.unpack_from("<iii", vrtx, o + 12) for o in range(0, len(vrtx), 24)]
            key = hashlib.sha256(json.dumps(sorted(verts)).encode()).hexdigest()
            if key.startswith(ARENA_POSITIONS):
                faces = [struct.unpack_from("<hhhh", face, o) for o in range(0, len(face), 8)]
                yield f"{name}@{at}", verts, faces


def test_arena_horizontal_faces_point_up_everywhere():
    found = list(_arena_models())
    # Two source models, the snowgoons-blender bundles and CDs, and the classic level.
    assert len(found) >= 13, f"expected every arena copy, found {[f[0] for f in found]}"
    for where, verts, faces in found:
        up = down = 0
        for a, b, c, _ in faces:
            n = cross(sub(verts[b], verts[a]), sub(verts[c], verts[a]))   # the engine's CalculateNormal
            if abs(n[2]) >= max(abs(n[0]), abs(n[1])):
                up += n[2] > 0
                down += n[2] < 0
        assert (up, down) == (HORIZONTAL_FACES, 0), (
            f"{where}: {down} of {up + down} horizontal arena faces point down; the floor is culled "
            "from above. Its migration decision must be reverse_all, not keep.")
