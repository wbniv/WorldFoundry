World Foundry level import / export operators.

  WF_OT_import_level  — read a .lev text IFF → populate Blender scene
  WF_OT_export_level  — write Blender scene → .lev text IFF

.lev format (text IFF):

  { 'LVL'
      { 'OBJ'
          { 'NAME' "objname" }
          { 'VEC3' { 'NAME' "Position" }             { 'DATA' x y z } }
          { 'EULR' { 'NAME' "Orientation" }           { 'DATA' a b c } }
          { 'BOX3' { 'NAME' "Global Bounding Box" }   { 'DATA' x0 y0 z0 x1 y1 z1 } }
          { 'STR'  { 'NAME' "Class Name" }            { 'DATA' "typename" } }
          { 'I32'  { 'NAME' "field" } { 'DATA' 0l }  { 'STR' "0" } }
          { 'FX32' { 'NAME' "field" } { 'DATA' 0.0(1.15.16) } { 'STR' "0.0" } }
          { 'STR'  { 'NAME' "field" } { 'DATA' "val" } }
      }
      ...
  }

Coordinate transform (Blender Z-up ↔ WF Y-up):
  export: wf_x = bl_x,  wf_y = bl_z,  wf_z = -bl_y
  import: bl_x = wf_x,  bl_y = -wf_z, bl_z = wf_y
"""

import math
import os
import re
import struct

import bpy
import bmesh
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

import wf_core

# ── helpers shared with operators.py ─────────────────────────────────────────

SCHEMA_PATH_KEY = "wf_schema_path"


def _prop_key(field_key: str) -> str:
    return f"wf_{field_key}"


def _seed_defaults(obj, schema):
    for field in schema.fields():
        if field.kind == "Section":
            sk = f"wf__open_{field.key}"
            if sk not in obj:
                obj[sk] = bool(field.default_raw)
            continue
        if field.kind in ("Group", "GroupEnd", "Skip", "Annotation"):
            continue
        if field.show_as == 6:
            continue
        key = _prop_key(field.key)
        if key in obj:
            continue
        if field.kind == "Float":
            obj[key] = field.default_display
        elif field.kind == "Bool":
            obj[key] = int(bool(field.default_raw))
        elif field.kind == "Enum":
            items = field.enum_items()
            idx = field.default_raw
            obj[key] = items[idx] if 0 <= idx < len(items) else (items[0] if items else "")
        elif field.kind in ("Str", "ObjRef", "FileRef"):
            obj[key] = ""
        else:
            obj[key] = field.default_raw


def _collect_values(obj, schema) -> dict:
    values = {}
    for field in schema.visible_fields():
        key = _prop_key(field.key)
        val = obj.get(key)
        if val is not None:
            values[field.key] = val
    return values


# ── text IFF parser ───────────────────────────────────────────────────────────

def _strip_line_comments(text: str) -> str:
    """Remove // comments that are not inside quoted strings."""
    result = []
    for line in text.splitlines():
        out = []
        in_str = False
        i = 0
        while i < len(line):
            c = line[i]
            if c == '"':
                in_str = not in_str
                out.append(c)
            elif not in_str and line[i:i+2] == '//':
                break
            else:
                out.append(c)
            i += 1
        result.append(''.join(out))
    return '\n'.join(result)


def _tokenize(text: str):
    """Yield tokens: '{', '}', ('str', value), ('tag', value), ('num', value), ('word', value)."""
    text = _strip_line_comments(text)
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in ' \t\n\r':
            i += 1
        elif c == '{':
            yield ('{',)
            i += 1
        elif c == '}':
            yield ('}',)
            i += 1
        elif c == "'":
            # FOURCC tag: 'ABCD'
            j = i + 1
            while j < n and text[j] != "'":
                j += 1
            yield ('tag', text[i+1:j])
            i = j + 1
        elif c == '"':
            # Quoted string
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == '\\' and j + 1 < n:
                    buf.append(text[j+1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            yield ('str', ''.join(buf))
            i = j + 1
        elif c in '-0123456789.' or (c == '-' and i + 1 < n and text[i+1].isdigit()):
            # Number (possibly with (1.15.16) suffix and/or trailing 'l')
            j = i
            while j < n and (text[j] in '-0123456789.eE+' or
                              (text[j] == '(' and '.' in text[j:j+10])):
                if text[j] == '(':
                    k = text.find(')', j)
                    j = k + 1 if k >= 0 else j + 1
                else:
                    j += 1
            # eat optional trailing 'l'
            if j < n and text[j] == 'l':
                j += 1
            raw = text[i:j]
            # strip (1.15.16) suffix to get the float
            raw_clean = re.sub(r'\([^)]*\)', '', raw).rstrip('l').strip()
            try:
                yield ('num', float(raw_clean))
            except ValueError:
                yield ('word', raw)
            i = j
        elif c.isalpha() or c == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j] in '_'):
                j += 1
            yield ('word', text[i:j])
            i = j
        else:
            i += 1


class _Parser:
    def __init__(self, tokens):
        self._toks = list(tokens)
        self._pos = 0

    def _peek(self):
        return self._toks[self._pos] if self._pos < len(self._toks) else None

    def _next(self):
        t = self._toks[self._pos]
        self._pos += 1
        return t

    def parse_chunk(self):
        """Parse { 'TAG' ... } → {'tag': str, 'children': list, 'scalars': list}"""
        t = self._next()
        assert t == ('{',), f"expected {{ got {t}"
        tag_tok = self._next()
        assert tag_tok[0] == 'tag', f"expected tag, got {tag_tok}"
        tag = tag_tok[1]
        children = []
        scalars = []
        while True:
            p = self._peek()
            if p is None or p == ('}',):
                break
            if p == ('{',):
                children.append(self.parse_chunk())
            elif p[0] in ('str', 'num', 'word'):
                scalars.append(self._next())
            else:
                self._next()  # skip unexpected
        close = self._next()
        assert close == ('}',), f"expected }} got {close}"
        return {'tag': tag, 'children': children, 'scalars': scalars}

    def parse_top(self):
        chunks = []
        while self._peek() is not None:
            if self._peek() == ('{',):
                chunks.append(self.parse_chunk())
            else:
                self._next()
        return chunks


def _parse_lev(text: str):
    tokens = _tokenize(text)
    parser = _Parser(tokens)
    top = parser.parse_top()
    # find LVL chunk
    for chunk in top:
        if chunk['tag'].strip() == 'LVL':
            return chunk
    return top[0] if top else None


def _child_by_tag(chunk, tag):
    for c in chunk['children']:
        if c['tag'].strip() == tag:
            return c
    return None


def _children_by_tag(chunk, tag):
    return [c for c in chunk['children'] if c['tag'].strip() == tag]


def _data_scalars(chunk):
    data = _child_by_tag(chunk, 'DATA')
    if data:
        return [t[1] for t in data['scalars'] if t[0] in ('num', 'str', 'word')]
    return []


def _name_value(chunk):
    """Return the DATA or STR content of a named chunk."""
    name_chunk = _child_by_tag(chunk, 'NAME')
    if name_chunk is None:
        return None, None
    name = name_chunk['scalars'][0][1] if name_chunk['scalars'] else ''
    data = _data_scalars(chunk)
    if not data:
        # some STR chunks use a nested STR instead of DATA
        str_chunk = _child_by_tag(chunk, 'STR')
        if str_chunk and str_chunk['scalars']:
            data = [str_chunk['scalars'][0][1]]
        elif str_chunk and str_chunk.get('children'):
            pass
    return name, data


# ── coordinate transform ──────────────────────────────────────────────────────

def wf_to_bl(wf_x, wf_y, wf_z):
    """WF Y-up → Blender Z-up."""
    return (wf_x, -wf_z, wf_y)


def bl_to_wf(bl_x, bl_y, bl_z):
    """Blender Z-up → WF Y-up."""
    return (bl_x, bl_z, -bl_y)


# ── binary mesh reader ────────────────────────────────────────────────────────
#
# Parses a MODL .iff file and returns (vertices, faces, uvs).
#
# On-disk structs (all little-endian):
#   Vertex3DOnDisk  [24 bytes]: fixed32 u, v;  uint32 color;  fixed32 x, y, z
#   _TriFaceOnDisk  [ 8 bytes]: int16 v1, v2, v3, materialIndex
#
# fixed32 is 1.15.16 — divide raw int32 by 65536.0 to get float.

_FIXED32_SCALE = 1.0 / 65536.0
_VERTEX_SIZE   = 24   # sizeof(Vertex3DOnDisk)
_FACE_SIZE     =  8   # sizeof(_TriFaceOnDisk)


def _read_iff_chunks(data: bytes) -> dict:
    """Parse flat IFF children from a payload blob → {tag: bytes}."""
    chunks = {}
    off = 0
    while off + 8 <= len(data):
        tag  = data[off:off+4].decode('ascii', errors='replace').rstrip('\x00')
        size = struct.unpack_from('<I', data, off + 4)[0]
        off += 8
        payload = data[off:off + size]
        chunks[tag] = payload
        off += size
        if size % 4:
            off += 4 - (size % 4)
    return chunks


def _load_mesh_iff(filepath: str):
    """
    Load a World Foundry MODL .iff and return (verts, faces, uvs) ready for Blender.

    verts — list of (x, y, z) in Blender space (Z-up)
    faces — list of (v1, v2, v3) int indices
    uvs   — list of (u, v) per vertex (parallel to verts)
    Returns None if the file cannot be parsed.
    """
    try:
        data = open(filepath, 'rb').read()
    except OSError:
        return None

    if len(data) < 8:
        return None

    # Outer MODL wrapper
    outer_tag  = data[0:4].decode('ascii', errors='replace').rstrip('\x00')
    outer_size = struct.unpack_from('<I', data, 4)[0]
    if outer_tag != 'MODL':
        return None

    inner = data[8:8 + outer_size]
    chunks = _read_iff_chunks(inner)

    vrtx_data = chunks.get('VRTX', b'')
    face_data  = chunks.get('FACE', b'')
    matl_data  = chunks.get('MATL', b'')

    if not vrtx_data or not face_data:
        return None

    n_verts = len(vrtx_data) // _VERTEX_SIZE
    n_faces = len(face_data) // _FACE_SIZE

    verts = []
    uvs   = []
    for i in range(n_verts):
        base = i * _VERTEX_SIZE
        u_raw, v_raw = struct.unpack_from('<ii', vrtx_data, base)
        # skip color (4 bytes at base+8)
        x_raw, y_raw, z_raw = struct.unpack_from('<iii', vrtx_data, base + 12)
        wf_x = x_raw * _FIXED32_SCALE
        wf_y = y_raw * _FIXED32_SCALE
        wf_z = z_raw * _FIXED32_SCALE
        # WF Y-up → Blender Z-up
        verts.append(wf_to_bl(wf_x, wf_y, wf_z))
        uvs.append((u_raw * _FIXED32_SCALE, v_raw * _FIXED32_SCALE))

    faces          = []
    face_mat_idxs  = []
    for i in range(n_faces):
        base = i * _FACE_SIZE
        v1, v2, v3, mat_idx = struct.unpack_from('<hhhh', face_data, base)
        faces.append((v1, v2, v3))
        face_mat_idxs.append(mat_idx)

    _MATL_SIZE = 264  # sizeof(_MaterialOnDisk) = 4+4+256
    n_mats   = len(matl_data) // _MATL_SIZE
    materials = []
    for i in range(n_mats):
        base = i * _MATL_SIZE
        flags, color = struct.unpack_from('<iI', matl_data, base)
        tex = matl_data[base+8:base+264].split(b'\x00')[0].decode('ascii', errors='replace')
        materials.append({'flags': flags, 'color': color, 'tex': tex})

    return verts, faces, uvs, face_mat_idxs, materials


def _make_blender_material(name: str, mat_info: dict, tex_path: str | None):
    """Create a Blender material with an optional Image Texture node."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]

    r = ((mat_info['color'] >> 16) & 0xFF) / 255.0
    g = ((mat_info['color'] >>  8) & 0xFF) / 255.0
    b = ( mat_info['color']        & 0xFF) / 255.0
    bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)

    if tex_path:
        img = bpy.data.images.get(os.path.basename(tex_path))
        if img is None:
            img = bpy.data.images.load(tex_path)
        tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = img
        uv_node = mat.node_tree.nodes.new('ShaderNodeUVMap')
        uv_node.uv_map = 'UVMap'
        nt = mat.node_tree
        nt.links.new(uv_node.outputs['UV'],       tex_node.inputs['Vector'])
        nt.links.new(tex_node.outputs['Color'],   bsdf.inputs['Base Color'])

    return mat


def _write_iff_chunk(tag: str, payload: bytes) -> bytes:
    """Serialize a single IFF chunk: 4-byte tag + LE size + payload + padding."""
    tag_bytes = tag.encode('ascii')[:4].ljust(4, b'\x00')
    size = len(payload)
    pad = (4 - size % 4) % 4
    return tag_bytes + struct.pack('<I', size) + payload + b'\x00' * pad


def _write_mesh_iff(blobj, filepath: str) -> bool:
    """
    Write a Blender mesh object as a World Foundry MODL binary .iff.

    Triangulates on the fly (does not modify the object).
    Applies Blender Z-up → WF Y-up coordinate transform.
    Returns True on success.
    """
    import bmesh as _bmesh
    mesh = blobj.data
    if mesh is None or not hasattr(mesh, 'vertices'):
        return False

    # Triangulate into a temporary bmesh
    bm = _bmesh.new()
    bm.from_mesh(mesh)
    _bmesh.ops.triangulate(bm, faces=bm.faces)

    uv_layer = bm.loops.layers.uv.active

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Split vertices at UV seams: each unique (orig_vi, u_fixed, v_fixed) gets
    # its own VRTX entry.  This is necessary because VRTX stores one UV per
    # vertex — without splitting, seam edges pick up the wrong UV from whichever
    # loop was visited first.
    split_verts = []          # list of (co, u, v)
    split_map   = {}          # (orig_vi, u_key, v_key) → new_vi

    face_triples = []         # list of (new_v1, new_v2, new_v3, mat_idx)

    for face in bm.faces:
        tri = []
        for loop in face.loops:
            orig_vi = loop.vert.index
            if uv_layer:
                u = loop[uv_layer].uv.x
                v = loop[uv_layer].uv.y
            else:
                u, v = 0.0, 0.0
            # Quantise to fixed-point to avoid spurious splits from float noise
            u_key = int(round(u * 65536))
            v_key = int(round(v * 65536))
            key = (orig_vi, u_key, v_key)
            if key not in split_map:
                split_map[key] = len(split_verts)
                split_verts.append((bm.verts[orig_vi].co.copy(), u, v))
            tri.append(split_map[key])
        face_triples.append((tri[0], tri[1], tri[2], face.material_index))

    # Build VRTX payload
    vrtx = bytearray()
    for co, u, v in split_verts:
        wf_x, wf_y, wf_z = bl_to_wf(co.x, co.y, co.z)
        vrtx += struct.pack('<iiIiii',
                            int(u * 65536), int(v * 65536), 0xFFFFFF,
                            int(wf_x * 65536), int(wf_y * 65536), int(wf_z * 65536))

    # Build FACE payload
    face_data = bytearray()
    for v1, v2, v3, mat_idx in face_triples:
        face_data += struct.pack('<hhhh', v1, v2, v3, mat_idx)

    bm.free()

    # Build MATL payload from Blender material slots
    def _extract_mat_info(mat):
        flags = 0x00
        color = 0x00FFFFFF
        tex   = ""
        if mat is None or not mat.use_nodes:
            return flags, color, tex
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is None:
            return flags, color, tex
        base_input = bsdf.inputs.get('Base Color')
        if base_input and base_input.links:
            from_node = base_input.links[0].from_node
            if from_node.type == 'TEX_IMAGE' and from_node.image:
                tex = os.path.basename(from_node.image.filepath or from_node.image.name)
                flags = 0x02
        else:
            bc = base_input.default_value if base_input else None
            if bc:
                r = int(bc[0] * 255) & 0xFF
                g = int(bc[1] * 255) & 0xFF
                b = int(bc[2] * 255) & 0xFF
                color = (r << 16) | (g << 8) | b
        return flags, color, tex

    mats = blobj.data.materials if blobj.data and blobj.data.materials else []
    matl = b''
    if mats:
        for mat in mats:
            mat_flags, mat_color, mat_tex = _extract_mat_info(mat)
            tex_bytes = mat_tex.encode('ascii', errors='replace')[:255].ljust(256, b'\x00')
            matl += struct.pack('<iI', mat_flags, mat_color) + tex_bytes
    else:
        matl = struct.pack('<iI', 0, 0x00FFFFFF) + b'\x00' * 256

    # Assemble MODL
    inner = (
        _write_iff_chunk('VRTX', bytes(vrtx)) +
        _write_iff_chunk('MATL', matl) +
        _write_iff_chunk('FACE', bytes(face_data))
    )
    modl = _write_iff_chunk('MODL', inner)

    try:
        with open(filepath, 'wb') as f:
            f.write(modl)
        return True
    except OSError:
        return False


def _find_file_nocase(directory: str, filename: str) -> str | None:
    """Return the actual path for filename in directory, case-insensitively."""
    lower = filename.lower()
    try:
        for entry in os.listdir(directory):
            if entry.lower() == lower:
                return os.path.join(directory, entry)
    except OSError:
        pass
    return None


# ── OAD dir helpers ───────────────────────────────────────────────────────────

def _default_oad_dirs() -> list[str]:
    """Candidate OAD directories to search if none is explicitly set."""
    # TODO: replace this hardcoded path with an addon preference once Blender
    # allows opening a directory picker while a file-selector dialog is already
    # open (currently raises "Cannot activate a file selector dialog, one
    # already open").
    # TODO: replace with addon preference once Blender allows nested file pickers
    _HARDCODED_CANDIDATES = [
        "/home/will/WorldFoundry/wftools/wf_oad/tests/fixtures",
        "/home/will/SRC/WorldFoundry-wbniv/wftools/wf_oad/tests/fixtures",
        "/home/will/SRC/WorldFoundry/wftools/wf_oad/tests/fixtures",
    ]
    candidates = [p for p in _HARDCODED_CANDIDATES if os.path.isdir(p)]

    # Walk up from this file's location to find wf_oad/tests/fixtures/
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    for _ in range(6):
        fixtures = os.path.join(d, "wf_oad", "tests", "fixtures")
        if os.path.isdir(fixtures) and fixtures not in candidates:
            candidates.append(fixtures)
        oad = os.path.join(d, "levels.src", "oad")
        if os.path.isdir(oad) and oad not in candidates:
            candidates.append(oad)
        d = os.path.dirname(d)
    return candidates


def _find_oad(typename: str, oad_dir: str) -> str | None:
    """Return path to <typename>.oad, searching oad_dir then default locations."""
    lower = typename.lower()
    dirs = []
    if oad_dir and os.path.isdir(oad_dir):
        dirs.append(oad_dir)
    dirs.extend(_default_oad_dirs())
    for d in dirs:
        for fname in os.listdir(d):
            if fname.lower() == lower + '.oad':
                return os.path.join(d, fname)
    return None


# ── import operator ───────────────────────────────────────────────────────────

class WF_OT_import_level(bpy.types.Operator, ImportHelper):
    """Import a World Foundry .lev text IFF into the Blender scene"""
    bl_idname  = "wf.import_level"
    bl_label   = "Import WF Level (.lev)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".lev"
    filter_glob: StringProperty(default="*.lev", options={'HIDDEN'})

    oad_dir: StringProperty(
        name="OAD Directory",
        description="Directory containing .oad schema files",
        default="",
        subtype='DIR_PATH',
    )

    def invoke(self, context, event):
        # Pre-fill oad_dir from scene if set
        scene_oad = context.scene.get("wf_oad_dir", "")
        if scene_oad and not self.oad_dir:
            self.oad_dir = scene_oad
        return super().invoke(context, event)

    def execute(self, context):
        try:
            with open(self.filepath, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        except OSError as e:
            self.report({'ERROR'}, f"Cannot read file: {e}")
            return {'CANCELLED'}

        oad_dir = bpy.path.abspath(self.oad_dir) if self.oad_dir else ""

        # Save oad_dir to scene for next time
        if oad_dir:
            context.scene["wf_oad_dir"] = self.oad_dir

        lvl = _parse_lev(text)
        if lvl is None:
            self.report({'ERROR'}, "No LVL chunk found in file")
            return {'CANCELLED'}

        imported = 0
        skipped = 0

        for obj_chunk in _children_by_tag(lvl, 'OBJ'):
            name_chunk = _child_by_tag(obj_chunk, 'NAME')
            obj_name = name_chunk['scalars'][0][1] if (name_chunk and name_chunk['scalars']) else "wf_obj"

            # Position (VEC3)
            pos_wf = (0.0, 0.0, 0.0)
            vec3 = _child_by_tag(obj_chunk, 'VEC3')
            if vec3:
                d = _data_scalars(vec3)
                if len(d) >= 3:
                    pos_wf = (float(d[0]), float(d[1]), float(d[2]))

            # Bounding box (BOX3)
            bb_min_wf = (-0.5, -0.5, -0.5)
            bb_max_wf = ( 0.5,  0.5,  0.5)
            box3 = _child_by_tag(obj_chunk, 'BOX3')
            if box3:
                d = _data_scalars(box3)
                if len(d) >= 6:
                    bb_min_wf = (float(d[0]), float(d[1]), float(d[2]))
                    bb_max_wf = (float(d[3]), float(d[4]), float(d[5]))

            # Class Name (STR with NAME "Class Name")
            typename = None
            for str_chunk in _children_by_tag(obj_chunk, 'STR'):
                n, d = _name_value(str_chunk)
                if n == "Class Name" and d:
                    typename = str(d[0])
                    break

            if typename is None:
                skipped += 1
                continue

            # Mesh Name field — look for a non-empty FILE/STR chunk named "Mesh Name"
            mesh_name = ""
            for chunk in obj_chunk['children']:
                tag = chunk['tag'].strip()
                if tag not in ('FILE', 'STR'):
                    continue
                nc = _child_by_tag(chunk, 'NAME')
                if nc and nc['scalars'] and nc['scalars'][0][1] == 'Mesh Name':
                    sc = _child_by_tag(chunk, 'STR')
                    if sc and sc['scalars']:
                        mesh_name = str(sc['scalars'][0][1]).strip()
                    break

            # Try to load actual mesh geometry (case-insensitive filename match)
            mesh_geo = None
            if mesh_name:
                level_dir = os.path.dirname(self.filepath)
                mesh_path = _find_file_nocase(level_dir, mesh_name)
                if mesh_path:
                    mesh_geo = _load_mesh_iff(mesh_path)

            # Orientation (EULR) — WF a,b,c → Blender rotation_euler
            rot_wf = (0.0, 0.0, 0.0)
            eulr = _child_by_tag(obj_chunk, 'EULR')
            if eulr:
                d = _data_scalars(eulr)
                if len(d) >= 3:
                    rot_wf = (float(d[0]), float(d[1]), float(d[2]))

            # Derive Blender location from BB centre
            cx_wf = (bb_min_wf[0] + bb_max_wf[0]) * 0.5
            cy_wf = (bb_min_wf[1] + bb_max_wf[1]) * 0.5
            cz_wf = (bb_min_wf[2] + bb_max_wf[2]) * 0.5
            bl_loc = wf_to_bl(cx_wf, cy_wf, cz_wf)

            if mesh_geo:
                # Real mesh geometry — vertices already in Blender space
                verts, faces, uvs, face_mat_idxs, materials = mesh_geo
                mesh = bpy.data.meshes.new(obj_name)
                mesh.from_pydata(verts, [], faces)
                mesh.update()

                # UV layer
                if uvs:
                    uv_layer = mesh.uv_layers.new(name="UVMap")
                    for poly in mesh.polygons:
                        for li in poly.loop_indices:
                            vi = mesh.loops[li].vertex_index
                            uv_layer.data[li].uv = uvs[vi]

                blobj = bpy.data.objects.new(obj_name, mesh)
                blobj.location = bl_loc

                # Materials
                level_dir = os.path.dirname(self.filepath)
                for i, mat_info in enumerate(materials):
                    tex_path = None
                    if mat_info['tex']:
                        tex_path = _find_file_nocase(level_dir, mat_info['tex'])
                    mat_name = mat_info['tex'] or f"{obj_name}_mat{i}"
                    mat = _make_blender_material(mat_name, mat_info, tex_path)
                    blobj.data.materials.append(mat)

                # Per-face material index
                for poly in blobj.data.polygons:
                    if poly.index < len(face_mat_idxs):
                        poly.material_index = face_mat_idxs[poly.index]
            else:
                # Fallback: box sized to bounding box
                sx = bb_max_wf[0] - bb_min_wf[0]  # WF X → Blender X
                sy = bb_max_wf[2] - bb_min_wf[2]  # WF Z → Blender Y
                sz = bb_max_wf[1] - bb_min_wf[1]  # WF Y → Blender Z
                sx = max(sx, 0.01)
                sy = max(sy, 0.01)
                sz = max(sz, 0.01)

                mesh = bpy.data.meshes.new(obj_name)
                bm = bmesh.new()
                bmesh.ops.create_cube(bm, size=1.0)
                bm.to_mesh(mesh)
                bm.free()

                blobj = bpy.data.objects.new(obj_name, mesh)
                blobj.location = bl_loc
                blobj.scale = (sx, sy, sz)

            # Orientation: inverse of export mapping (rot.x, rot.z, -rot.y) → WF (a,b,c)
            # so import: bl_x=wf_a, bl_y=-wf_c, bl_z=wf_b
            blobj.rotation_euler = (rot_wf[0], -rot_wf[2], rot_wf[1])

            context.collection.objects.link(blobj)

            # Import PATH animation data (if present)
            try:
                _import_path_block(blobj, obj_chunk, context.scene)
            except Exception as e_path:
                self.report({'WARNING'}, f"{obj_name}: PATH import error: {e_path}")

            # Attach OAD schema
            oad_path = _find_oad(typename, oad_dir)
            if oad_path:
                blobj[SCHEMA_PATH_KEY] = oad_path
                try:
                    schema = wf_core.load_schema(oad_path)
                    _seed_defaults(blobj, schema)
                    # Populate field values from remaining chunks
                    _apply_field_chunks(blobj, schema, obj_chunk)
                except Exception as e:
                    self.report({'WARNING'}, f"{obj_name}: schema error: {e}")
            else:
                self.report({'WARNING'}, f"{obj_name}: no .oad for '{typename}'")

            imported += 1

        self.report({'INFO'}, f"Imported {imported} objects ({skipped} skipped)")
        return {'FINISHED'}


def _apply_field_chunks(blobj, schema, obj_chunk):
    """Populate wf_ custom properties from field chunks in an OBJ."""
    # Build a map from field name → field for quick lookup
    field_by_name = {}
    for field in schema.fields():
        field_by_name[field.label.lower()] = field
        field_by_name[field.key.lower()] = field

    skip_names = {"position", "orientation", "global bounding box", "class name"}

    for chunk in obj_chunk['children']:
        tag = chunk['tag'].strip()
        if tag not in ('I32', 'FX32', 'STR', 'F32'):
            continue
        name_chunk = _child_by_tag(chunk, 'NAME')
        if not name_chunk or not name_chunk['scalars']:
            continue
        field_name = str(name_chunk['scalars'][0][1])
        if field_name.lower() in skip_names:
            continue

        field = field_by_name.get(field_name.lower())
        if field is None:
            continue

        prop_key = _prop_key(field.key)
        data = _data_scalars(chunk)
        if not data and tag == 'STR':
            # XDATA/string fields store value in a nested STR child, not DATA
            str_child = _child_by_tag(chunk, 'STR')
            if str_child and str_child['scalars']:
                data = [str_child['scalars'][0][1]]
        if not data:
            continue
        val = data[0]

        if field.kind == "Int" or field.kind == "Bool":
            try:
                blobj[prop_key] = int(float(val))
            except (ValueError, TypeError):
                pass
        elif field.kind == "Float":
            try:
                blobj[prop_key] = float(val)
            except (ValueError, TypeError):
                pass
        elif field.kind == "Enum":
            try:
                idx = int(float(val))
                items = field.enum_items()
                if 0 <= idx < len(items):
                    blobj[prop_key] = items[idx]
            except (ValueError, TypeError):
                pass
        elif field.kind in ("Str", "ObjRef", "FileRef", "Skip", "Annotation"):
            blobj[prop_key] = str(val)


# ── export operator ───────────────────────────────────────────────────────────

class WF_OT_export_level(bpy.types.Operator, ExportHelper):
    """Export the Blender scene as a World Foundry .lev text IFF"""
    bl_idname  = "wf.export_level"
    bl_label   = "Export WF Level (.lev)"
    bl_options = {'REGISTER'}

    filename_ext = ".lev"
    filter_glob: StringProperty(default="*.lev", options={'HIDDEN'})

    def execute(self, context):
        objects = [o for o in context.scene.objects if o.get(SCHEMA_PATH_KEY)]
        if not objects:
            self.report({'WARNING'}, "No WF objects in scene (attach schemas first)")
            return {'CANCELLED'}

        lines = ["{ 'LVL' "]
        for obj in objects:
            schema_path = obj[SCHEMA_PATH_KEY]
            # derive type name: strip directory, extension
            typename = os.path.splitext(os.path.basename(bpy.path.abspath(schema_path)))[0]

            # Bounding box in world space (Blender coords)
            corners_bl = [obj.matrix_world @ obj.bound_box[i].to_4d().to_3d()
                          if hasattr(obj.bound_box[0], 'to_4d')
                          else _corner(obj, i)
                          for i in range(8)]

            bl_min = [min(c[i] for c in corners_bl) for i in range(3)]
            bl_max = [max(c[i] for c in corners_bl) for i in range(3)]

            # Transform bbox corners to WF space
            wf_min_x, wf_min_y_raw, wf_min_z = bl_to_wf(bl_min[0], bl_min[1], bl_min[2])
            wf_max_x, wf_max_y_raw, wf_max_z = bl_to_wf(bl_max[0], bl_max[1], bl_max[2])
            # After transform, Y and Z axes may be swapped/negated — take real min/max
            wf_bb_min = (
                min(wf_min_x, wf_max_x),
                min(wf_min_y_raw, wf_max_y_raw),
                min(wf_min_z, wf_max_z),
            )
            wf_bb_max = (
                max(wf_min_x, wf_max_x),
                max(wf_min_y_raw, wf_max_y_raw),
                max(wf_min_z, wf_max_z),
            )

            # Object position (world-space origin → WF)
            loc = obj.matrix_world.to_translation()
            wf_pos = bl_to_wf(loc.x, loc.y, loc.z)

            # Orientation: Euler from world rotation (ZXY ≈ WF a,b,c)
            rot = obj.matrix_world.to_euler('XYZ')
            wf_rot = (rot.x, rot.z, -rot.y)

            def fp(v):
                return f"{v:.16f}(1.15.16)"

            lines.append("\t{ 'OBJ' ")
            lines.append(f'\t\t{{ \'NAME\' "{obj.name}" }}')

            # PATH block — animation keyframes (max2lev/max2lev.cc:158-306)
            # Emitted before VEC3/EULR, matching the original .lev layout.
            path_lines = _emit_path_block(obj, fp)
            for pl in path_lines:
                lines.append("\t\t" + pl)

            lines.append(f"\t\t{{ 'VEC3' {{ 'NAME' \"Position\" }} {{ 'DATA' {fp(wf_pos[0])} {fp(wf_pos[1])} {fp(wf_pos[2])}  //x,y,z }} }}")
            lines.append(f"\t\t{{ 'EULR' {{ 'NAME' \"Orientation\" }} {{ 'DATA' {fp(wf_rot[0])} {fp(wf_rot[1])} {fp(wf_rot[2])}  //a,b,c }} }}")
            lines.append(
                f"\t\t{{ 'BOX3' {{ 'NAME' \"Global Bounding Box\" }} "
                f"{{ 'DATA' {fp(wf_bb_min[0])} {fp(wf_bb_min[1])} {fp(wf_bb_min[2])} "
                f"{fp(wf_bb_max[0])} {fp(wf_bb_max[1])} {fp(wf_bb_max[2])}  //min(x,y,z)-max(x,y,z) }} }}"
            )
            lines.append(f'\t\t{{ \'STR\' {{ \'NAME\' "Class Name" }} {{ \'DATA\' "{typename}" }} }}')

            # Mesh geometry — export .iff if object has a real mesh
            level_dir  = os.path.dirname(self.filepath)
            mesh_filename = ""
            model_type    = 0  # 0=None/Box
            if obj.data and obj.data.polygons:
                mesh_filename = obj.name + ".iff"
                mesh_out = os.path.join(level_dir, mesh_filename)
                if _write_mesh_iff(obj, mesh_out):
                    model_type = 1  # Mesh
                else:
                    self.report({'WARNING'}, f"{obj.name}: mesh export failed")
                    mesh_filename = ""

            lines.append(f'\t\t{{ \'FILE\' {{ \'NAME\' "Mesh Name" }} {{ \'STR\' "{mesh_filename}" }} }}')
            lines.append(f'\t\t{{ \'I32\'  {{ \'NAME\' "Model Type" }} {{ \'DATA\' {model_type}l }} {{ \'STR\' "{"Mesh" if model_type == 1 else "None"}" }} }}')

            # OAD fields — walk the schema and emit every stored property
            # as text-IFF chunks matching the .lev format that iff2lvl and
            # levcomp-rs consume.
            try:
                resolved = bpy.path.abspath(schema_path)
                schema = wf_core.load_schema(resolved)
                for fl in _emit_lev_fields(obj, schema, fp):
                    lines.append("\t\t" + fl)
            except Exception as e_oad:
                import traceback
                with open("/tmp/wf_export_errors.log", "a") as _ef:
                    _ef.write(f"[wf_export] {obj.name}: {e_oad}\n")
                    traceback.print_exc(file=_ef)
                self.report({'WARNING'}, f"{obj.name}: OAD export error: {e_oad}")

            # ── max2lev-injected specials ─────────────────────────────
            # These fields are NOT in the OAD schema — max2lev injects
            # them by reading 3DS Max scene data.  We do the Blender
            # equivalent here.

            # Light properties (max2lev/oadobj.cc:289-393)
            # Detect lights by class name since the importer creates them
            # as mesh/empty objects, not Blender LIGHT objects.
            is_light = typename.lower() == "light"
            if is_light:
                if obj.type == 'LIGHT' and obj.data:
                    r, g, b = obj.data.color[0], obj.data.color[1], obj.data.color[2]
                    lt = 1 if obj.data.type == 'POINT' else 0
                else:
                    # Imported as mesh/empty — use stored OAD values or defaults
                    r = float(obj.get(_prop_key("lightRed"), 1.0))
                    g = float(obj.get(_prop_key("lightGreen"), 1.0))
                    b = float(obj.get(_prop_key("lightBlue"), 1.0))
                    lt_raw = obj.get(_prop_key("lightType"), 0)
                    lt_map = {"directional": 0, "ambient": 1}
                    lt = lt_map.get(str(lt_raw).lower(), int(lt_raw) if str(lt_raw).isdigit() else 0)
                lines.append(f"\t\t{{ 'FX32' {{ 'NAME' \"lightRed\" }} {{ 'DATA' {fp(r)} }} {{ 'STR' \"{r:f}\" }} }}")
                lines.append(f"\t\t{{ 'FX32' {{ 'NAME' \"lightGreen\" }} {{ 'DATA' {fp(g)} }} {{ 'STR' \"{g:f}\" }} }}")
                lines.append(f"\t\t{{ 'FX32' {{ 'NAME' \"lightBlue\" }} {{ 'DATA' {fp(b)} }} {{ 'STR' \"{b:f}\" }} }}")
                lines.append(f"\t\t{{ 'I32' {{ 'NAME' \"lightType\" }} {{ 'DATA' {lt}l  //Directional|Ambient }} {{ 'STR' \"{'Ambient' if lt else 'Directional'}\" }} }}")

            # Slope plane coefficients (max2lev/oadobj.cc:410-480)
            if obj.data and hasattr(obj.data, 'polygons') and obj.data.polygons:
                mesh = obj.data
                nx, ny, nz = 0.0, 0.0, 0.0
                for poly in mesh.polygons:
                    nx += poly.normal.x
                    ny += poly.normal.y
                    nz += poly.normal.z
                n = len(mesh.polygons)
                if n > 0:
                    nx, ny, nz = nx/n, ny/n, nz/n
                    wf_a, wf_b, wf_c = bl_to_wf(nx, ny, nz)
                    loc = obj.matrix_world.to_translation()
                    wf_px, wf_py, wf_pz = bl_to_wf(loc.x, loc.y, loc.z)
                    wf_d = wf_a * wf_px + wf_b * wf_py + wf_c * wf_pz
                    lines.append(f"\t\t{{ 'FX32' {{ 'NAME' \"slopeA\" }} {{ 'DATA' {fp(wf_a)} }} {{ 'STR' \"{wf_a:f}\" }} }}")
                    lines.append(f"\t\t{{ 'FX32' {{ 'NAME' \"slopeB\" }} {{ 'DATA' {fp(wf_b)} }} {{ 'STR' \"{wf_b:f}\" }} }}")
                    lines.append(f"\t\t{{ 'FX32' {{ 'NAME' \"slopeC\" }} {{ 'DATA' {fp(wf_c)} }} {{ 'STR' \"{wf_c:f}\" }} }}")
                    lines.append(f"\t\t{{ 'FX32' {{ 'NAME' \"slopeD\" }} {{ 'DATA' {fp(wf_d)} }} {{ 'STR' \"{wf_d:f}\" }} }}")

            lines.append("\t}")

        lines.append("}")
        text = "\n".join(lines) + "\n"

        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(text)
        except OSError as e:
            self.report({'ERROR'}, f"Cannot write file: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {len(objects)} objects to {self.filepath}")
        return {'FINISHED'}


def _corner(obj, i):
    """Return world-space corner i of obj.bound_box."""
    from mathutils import Vector
    local = Vector(obj.bound_box[i])
    return obj.matrix_world @ local


def _import_path_block(blobj, obj_chunk, scene):
    """Parse a PATH sub-chunk from the .lev and create Blender keyframes.

    PATH layout:
      { 'PATH'
          { 'BPOS' x y z }
          { 'BROT' a b c w }
          { 'CHAN' { 'NAME' "position.x" } { 'TYPE' 0l } { 'RATE' t } { 'DIM' n } { 'DATA' t0 v0 t1 v1 ... } }
          ... (6 channels: position.x/y/z + rotation.a/b/c)
      }
    """
    path = _child_by_tag(obj_chunk, 'PATH')
    if not path:
        return

    fps = scene.render.fps / scene.render.fps_base

    # WF channel name → (Blender data_path, array_index, value transform)
    chan_map = {
        "position.x":  ("location", 0, lambda v: v),       # wf_x → bl_x
        "position.y":  ("location", 2, lambda v: v),       # wf_y → bl_z
        "position.z":  ("location", 1, lambda v: -v),      # wf_z → -bl_y
        "rotation.a":  ("rotation_euler", 0, lambda v: v),  # wf_a → bl_rx
        "rotation.b":  ("rotation_euler", 2, lambda v: v),  # wf_b → bl_rz
        "rotation.c":  ("rotation_euler", 1, lambda v: -v), # wf_c → -bl_ry
    }

    # Ensure the object has animation data
    if not blobj.animation_data:
        blobj.animation_data_create()
    action = bpy.data.actions.new(name=f"{blobj.name}_path")
    blobj.animation_data.action = action

    for chan_chunk in _children_by_tag(path, 'CHAN'):
        name_ch = _child_by_tag(chan_chunk, 'NAME')
        if not name_ch or not name_ch['scalars']:
            continue
        chan_name = str(name_ch['scalars'][0][1])

        mapping = chan_map.get(chan_name)
        if not mapping:
            continue
        bl_path, bl_idx, xform = mapping

        data_ch = _child_by_tag(chan_chunk, 'DATA')
        if not data_ch or not data_ch['scalars']:
            continue
        raw = [float(s[1]) for s in data_ch['scalars']]

        # DATA contains pairs: time0 value0 time1 value1 ...
        if len(raw) < 2:
            continue
        keys = [(raw[i], raw[i+1]) for i in range(0, len(raw)-1, 2)]

        fc = action.fcurves.new(data_path=bl_path, index=bl_idx)
        fc.keyframe_points.add(count=len(keys))
        for ki, (t, v) in enumerate(keys):
            frame = t * fps
            fc.keyframe_points[ki].co = (frame, xform(v))
            fc.keyframe_points[ki].interpolation = 'LINEAR'

    # Update the fcurves
    for fc in action.fcurves:
        fc.update()


def _emit_path_block(obj, fp) -> list[str]:
    """If the Blender object has animation keyframes, emit a PATH block
    with BPOS, BROT, and 6 CHAN chunks (position.x/y/z + rotation.a/b/c).

    Matches max2lev/max2lev.cc:158-306.  Returns empty list if no
    animation data exists on this object.
    """
    if not obj.animation_data or not obj.animation_data.action:
        return []

    action = obj.animation_data.action
    fcurves = action.fcurves
    if not fcurves:
        return []

    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base

    # Map Blender fcurve channels → WF channel names.
    # Blender:  location[0]=X, location[1]=Y, location[2]=Z
    #           rotation_euler[0]=X, [1]=Y, [2]=Z
    # WF .lev:  position.x/y/z  rotation.a/b/c
    # With coordinate transform: wf_x=bl_x, wf_y=bl_z, wf_z=-bl_y
    channel_map = [
        ("position.x",  "location", 0, lambda v: v),       # bl_x → wf_x
        ("position.y",  "location", 2, lambda v: v),       # bl_z → wf_y
        ("position.z",  "location", 1, lambda v: -v),      # -bl_y → wf_z
        ("rotation.a",  "rotation_euler", 0, lambda v: v),  # bl_rx → wf_a
        ("rotation.b",  "rotation_euler", 2, lambda v: v),  # bl_rz → wf_b
        ("rotation.c",  "rotation_euler", 1, lambda v: -v), # -bl_ry → wf_c
    ]

    chan_data = {}  # name → [(time, value), ...]
    for wf_name, bl_path, bl_idx, xform in channel_map:
        fc = fcurves.find(bl_path, index=bl_idx)
        if fc and fc.keyframe_points:
            keys = []
            for kp in fc.keyframe_points:
                t = kp.co.x / fps  # frame → seconds
                v = xform(kp.co.y)
                keys.append((t, v))
            chan_data[wf_name] = keys
        else:
            chan_data[wf_name] = [(0.0, 0.0)]  # constant zero

    if all(len(v) <= 1 and (not v or v[0][1] == 0.0) for v in chan_data.values()):
        return []  # no meaningful animation

    lines = ["{ 'PATH' "]
    # BPOS — base position (all zeros; the actual position comes from keyframes)
    lines.append(f"\t{{ 'BPOS' {fp(0.0)} {fp(0.0)} {fp(0.0)}  //basePosition }}")
    # BROT — base rotation as quaternion (identity: 0,0,0,1)
    lines.append(f"\t{{ 'BROT' {fp(0.0)} {fp(0.0)} {fp(0.0)} {fp(1.0)}  //baseRotation }}")

    for wf_name in ["position.x", "position.y", "position.z",
                     "rotation.a", "rotation.b", "rotation.c"]:
        keys = chan_data[wf_name]
        num_keys = len(keys)
        end_time = keys[-1][0] if keys else 0.0
        chan_type = 0 if num_keys > 1 else 1  # 0=LINEAR, 1=CONSTANT

        lines.append("\t{ 'CHAN' ")
        lines.append(f'\t\t{{ \'NAME\' "{wf_name}" }}')
        lines.append(f"\t\t{{ 'TYPE' {chan_type}l }}")
        lines.append(f"\t\t{{ 'RATE' {fp(end_time)} }}")
        lines.append(f"\t\t{{ 'DIM' {num_keys}l }}")

        data_parts = []
        for i, (t, v) in enumerate(keys):
            data_parts.append(f"{fp(t)} {fp(v)}  //#{i}")
        lines.append("\t\t{ 'DATA' " + "\n\t\t\t\t".join(data_parts) + " }")

        lines.append("\t}")

    lines.append("}")
    return lines


def _emit_lev_fields(obj, schema, fp) -> list[str]:
    """Walk every visible schema field and emit its value as a text-IFF
    chunk line matching the .lev format that iffcomp / levcomp-rs consume.

    Returns a list of single-line strings, one per field:
      { 'I32'  { 'NAME' "Mobility" } { 'DATA' 0l } { 'STR' "Anchored" } }
      { 'FX32' { 'NAME' "Mass" }     { 'DATA' 75.0(1.15.16) } { 'STR' "75.0" } }
      { 'STR'  { 'NAME' "Script" }   { 'STR' "write_mailbox(..." } }
    """
    lines = []
    for field in schema.fields():
        kind = field.kind
        if kind in ("Section", "Group", "GroupEnd"):
            continue
        key = _prop_key(field.key)
        val = obj.get(key)
        if val is None:
            continue
        # Skip hidden/structural fields UNLESS they carry a real value
        # (e.g. XDATA Script fields are marked kind="Skip" by the schema
        # but do hold script text that must round-trip).
        if kind == "Skip" and (val == "" or val == 0):
            continue
        if field.show_as == 6 and kind != "Skip":  # hidden non-content
            continue

        # max2lev (oadobj.cc:504) writes GetName() = the internal key,
        # NOT the display label.  The .lev reader (iff2lvl) and our own
        # importer match by key, so round-tripping requires the key.
        name = field.key

        if kind == "Int" or kind == "Bool":
            iv = int(val)
            items = field.enum_items() if hasattr(field, 'enum_items') else []
            if items:
                label = items[iv] if 0 <= iv < len(items) else str(iv)
                lines.append(
                    f"{{ 'I32' {{ 'NAME' \"{name}\" }} "
                    f"{{ 'DATA' {iv}l  //{_items_comment(items)} }} "
                    f"{{ 'STR' \"{label}\" }} }}")
            else:
                lines.append(
                    f"{{ 'I32' {{ 'NAME' \"{name}\" }} "
                    f"{{ 'DATA' {iv}l }} {{ 'STR' \"{iv}\" }} }}")

        elif kind == "Float":
            fv = float(val)
            lines.append(
                f"{{ 'FX32' {{ 'NAME' \"{name}\" }} "
                f"{{ 'DATA' {fp(fv)} }} {{ 'STR' \"{fv}\" }} }}")

        elif kind == "Enum":
            label = str(val)
            items = field.enum_items()
            idx = items.index(label) if label in items else 0
            # max2lev (oadobj.cc:555): SHOW_AS_DROPMENU (4) omits DATA,
            # writes only STR with the label.  All other showAs values
            # (RADIOBUTTONS=5, etc.) write DATA(index) + STR(label).
            if field.show_as == 4:
                lines.append(
                    f"{{ 'I32' {{ 'NAME' \"{name}\" }} "
                    f"{{ 'STR' \"{label}\" }} }}")
            else:
                lines.append(
                    f"{{ 'I32' {{ 'NAME' \"{name}\" }} "
                    f"{{ 'DATA' {idx}l  //{_items_comment(items)} }} "
                    f"{{ 'STR' \"{label}\" }} }}")

        elif kind == "Str" or kind == "Annotation":
            sv = str(val).replace('"', '\\"')
            lines.append(
                f"{{ 'STR' {{ 'NAME' \"{name}\" }} "
                f"{{ 'STR' \"{sv}\" }} }}")

        elif kind == "ObjRef":
            sv = str(val)
            lines.append(
                f"{{ 'STR' {{ 'NAME' \"{name}\" }} "
                f"{{ 'STR' \"{sv}\" }} }}")

        elif kind == "FileRef":
            sv = str(val)
            lines.append(
                f"{{ 'FILE' {{ 'NAME' \"{name}\" }} "
                f"{{ 'STR' \"{sv}\" }} }}")

        elif kind == "Skip":
            # XDATA fields (Script, Notes, etc.) — emit as STR with the
            # stored text value, matching max2lev's XDATA→'STR' mapping.
            sv = str(val).replace('"', '\\"')
            if sv:
                lines.append(
                    f"{{ 'STR' {{ 'NAME' \"{name}\" }} "
                    f"{{ 'STR' \"{sv}\" }} }}")

    return lines


def _items_comment(items):
    """Format enum items as a comment string: 'False|True'."""
    return '|'.join(items) if items else ''


def _extract_field_lines(oad_iff_txt: str) -> list[str]:
    """
    Pull the inner field chunk lines out of a TYPE-wrapped OAD iff.txt block.
    Strips the outer { 'TYPE' ... } wrapper and the NAME chunk.
    """
    lines = []
    depth = 0
    in_body = False
    skip_name = False

    for line in oad_iff_txt.splitlines():
        stripped = line.strip()
        if not in_body:
            # Wait for the opening { 'TYPE'
            if "TYPE" in stripped and stripped.startswith("{"):
                in_body = True
                depth = 1
                skip_name = True  # next top-level chunk is { 'NAME' ... }, skip it
            continue

        opens = stripped.count('{')
        closes = stripped.count('}')

        if depth == 1 and stripped.startswith("}"):
            break  # end of TYPE chunk

        if skip_name and depth == 1 and stripped.startswith("{") and "'NAME'" in stripped:
            # single-line NAME chunk — skip
            if closes >= opens:
                skip_name = False
                continue
            skip_name = False

        depth += opens - closes
        if depth >= 1:
            lines.append(line)

    return lines


# ── registration ──────────────────────────────────────────────────────────────

_CLASSES = [WF_OT_import_level, WF_OT_export_level]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
