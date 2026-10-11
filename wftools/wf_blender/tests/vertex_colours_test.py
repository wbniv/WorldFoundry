"""Round-trip test for opt-in vertex colours and the Gouraud material flag.

Run: blender --background --python-exit-code 1 --python wftools/wf_blender/tests/vertex_colours_test.py
"""
import importlib.util
import os
import struct
import sys
import tempfile
import types

import bpy

# wf_core is the compiled Rust extension; the mesh writer under test never calls it.
sys.modules.setdefault("wf_core", types.ModuleType("wf_core"))

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("export_level", os.path.join(HERE, "..", "export_level.py"))
export_level = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_level)

VERTEX = 24    # sizeof(Vertex3DOnDisk): u, v, colour, x, y, z
FAILURES = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + detail if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def make(name, attr=None, opt_in=False, gouraud=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    if gouraud:
        mat["wf_gouraud"] = True
    mesh.materials.append(mat)
    if attr:
        kind, domain, linear = attr
        a = mesh.color_attributes.new("ao", kind, domain)
        for i, d in enumerate(a.data):
            d.color = (linear, linear, linear, 1.0)
    obj = bpy.data.objects.new(name, mesh)
    if opt_in:
        obj["wf_vertex_colors"] = True
    bpy.context.scene.collection.objects.link(obj)
    return obj


def export(obj):
    path = os.path.join(tempfile.mkdtemp(), obj.name + ".iff")
    check(obj.name + " writes", export_level._write_mesh_iff(obj, path))
    data = open(path, "rb").read()
    assert data[:4] == b"MODL", data[:4]
    return export_level._read_iff_chunks(data[8:8 + struct.unpack_from("<I", data, 4)[0]])


def colours(chunks):
    v = chunks["VRTX"]
    return {struct.unpack_from("<I", v, i * VERTEX + 8)[0] for i in range(len(v) // VERTEX)}


plain = export(make("plain"))
check("no attribute: constant white", colours(plain) == {0xFFFFFF})

ignored = export(make("ignored", attr=("FLOAT_COLOR", "CORNER", 0.2)))
check("attribute without opt-in is ignored", ignored["VRTX"] == plain["VRTX"])

mid = export_level._srgb_byte(0.5)
check("float 0.5 linear encodes to display space", mid == 188, str(mid))
for label, attr in (("float corner", ("FLOAT_COLOR", "CORNER", 0.5)),
                    ("float point", ("FLOAT_COLOR", "POINT", 0.5)),
                    ("byte corner", ("BYTE_COLOR", "CORNER", 0.5))):
    got = colours(export(make("c_" + label.replace(" ", "_"), attr=attr, opt_in=True)))
    expected = {(mid << 16) | (mid << 8) | mid}
    check(label + " exports", got == expected, f"{got} != {expected}")

flat = export(make("flat_mat"))
gour = export(make("gour_mat", gouraud=True))
flags = lambda c: struct.unpack_from("<I", c["MATL"], 0)[0]
check("wf_gouraud sets flag 1 and keeps the rest", flags(gour) == flags(flat) | 1,
      f"{flags(gour):#x} vs {flags(flat):#x}")

sys.exit(1 if FAILURES else 0)
