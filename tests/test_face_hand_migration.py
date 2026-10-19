"""Offline conversion boundaries and mirrored fin authoring regression checks."""

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from convert_face_hand import converted_model  # noqa: E402
sys.path.insert(0, str(ROOT / "wflevels/aquarium_tanks"))
from models import membrane  # noqa: E402


def chunk(tag, payload):
    return tag + struct.pack("<I", len(payload)) + payload + b"\0" * (-len(payload) % 4)


def test_converter_changes_only_selected_real_face_indices():
    # A texture name containing FACE is data, not a nested chunk.
    texture = chunk(b"MATL", b"not-a-chunk:FACE" + b"\xff" * 21)
    faces = struct.pack("<8h", 1, 2, 3, 7, 4, 5, 6, 9)
    model = chunk(b"MODL", texture + chunk(b"FACE", faces))
    expected = chunk(b"MODL", texture + chunk(
        b"FACE", struct.pack("<8h", 1, 2, 3, 7, 4, 6, 5, 9)))
    result, count = converted_model(
        model, {"action": "reverse_selected", "face_indices": [1]})
    assert result == expected
    assert count == 1
    assert converted_model(result, {"action": "reverse_selected",
                                    "face_indices": [1]})[0] == model


@pytest.mark.parametrize("body", [
    chunk(b"FACE", b"\0" * 7),
    chunk(b"FACE", b"\0" * 8) + chunk(b"FACE", b"\0" * 8),
    b"FACE" + struct.pack("<I", 80) + b"\0" * 8,
])
def test_converter_rejects_malformed_or_duplicate_face_chunks(body):
    with pytest.raises(ValueError):
        converted_model(chunk(b"MODL", body), {"action": "reverse_all"})


@pytest.mark.parametrize("sign", [1, -1])
def test_mirrored_membrane_shells_are_blender_outward(sign):
    mesh = membrane("fin", [(1, 0), (0, sign), (-1, 0)], "fin")
    volume6 = 0
    for face in mesh.faces:
        p = mesh.vertices[face[0]]
        for i in range(1, len(face) - 1):
            q, r = mesh.vertices[face[i]], mesh.vertices[face[i + 1]]
            cross = (q[1]*r[2]-q[2]*r[1], q[2]*r[0]-q[0]*r[2],
                     q[0]*r[1]-q[1]*r[0])
            volume6 += sum(p[k]*cross[k] for k in range(3))
    assert volume6 > 0
