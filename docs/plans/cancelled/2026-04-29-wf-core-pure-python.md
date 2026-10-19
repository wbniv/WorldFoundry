# Plan: Pure-Python `wf_core` — eliminate the last native dependency

**Date:** 2026-04-29
**Status:** Cancelled — not proceeding. The asset browser (`wf_asset_browser/`) is already pure Python (no `wf_core` dependency). `wf_core.so` is only used by the level editor (`wf_blender/`), which is expected to have native deps and is not targeted for zero-native-dep packaging.
**Predecessor:** [docs/plans/2026-04-28-wf-asset-provider-pure-python.md](../2026-04-28-wf-asset-provider-pure-python.md) — eliminated `wf_asset_provider.so`. This plan eliminates `wf_core.so`, completing the "zero native dependencies" goal.

---

## Goal

Replace `wf_core.so` (a PyO3-compiled Rust extension) with a pure Python module `wf_core.py` that exposes the identical API. After this plan the Blender addon has **zero native dependencies** — no `.so` files, no maturin build step, no platform-specific wheels.

---

## What `wf_core.so` actually does

`wf_py/src/lib.rs` (355 lines) is a thin Python binding layer. All logic lives in five dependency crates that are themselves second-generation reimplementations of the original C/C++ tools. The canonical format references are:

- **`wfsource/source/oas/oad.h`** — `_oadHeader` and `_typeDescriptor` struct definitions, all `BUTTON_*` / `SHOW_AS_*` / `LEVELCONFLAG_*` constants
- **`wftools/oaddump/oad.cc`** — original C++ OAD parser (`QObjectAttributeData::Load`, `OAD_CHUNKID` constant)
- **`wftools/iffwrite/binary.cc`** + **`id.hp`** — IFF binary chunk format (FOURCC as ID class, LE size, 4-byte alignment, backpatch on exit)

The Rust crates exist as a reference for the Python API surface and enum detection logic, but `oad.h` is authoritative for field layout.

| Rust Crate | Job |
|---|---|
| `wf_oad` | Read `.oad` binary files → `OadFile` struct |
| `wf_attr_schema` | `OadFile` → typed `Schema` + `FieldDescriptor` list |
| `wf_attr_validate` | Range-check `values` dict against schema |
| `wf_attr_serialize` | Serialize/deserialize `values` ↔ `.iff.txt` text and binary `.iff` |
| `wf_iff` | IFF chunk read/write (used by serializer) |

All of this is straightforward data parsing, range arithmetic, and string formatting. None of it requires native performance. Python's `struct` module handles the binary layout; the IFF text parser already exists in `export_level.py`.

---

## The OAD binary format

Defined in `wfsource/source/oas/oad.h` (struct layout) and `wftools/oaddump/oad.cc` (parser and `OAD_CHUNKID`). Little-endian, `#pragma pack(1)`.

### Header — 80 bytes (`_oadHeader` from `oad.h`)
```
[4]  chunkId   i32 LE  — chunk ID (FOURCC) "OAD " — checked against OAD_CHUNKID = 'OAD ' in oad.cc
[4]  chunkSize i32
[68] name      NUL-terminated display name (e.g. "Actor")  — char name[72-4]
[4]  version   i32
```

### Entry (`_typeDescriptor`) — 1491 bytes, repeated until EOF
From `wfsource/source/oas/oad.h`, `#pragma pack(1)`:
```
[1]   type          buttonType (char)  — see BUTTON_* constants below
[64]  name          char[64]    NUL-terminated field key (e.g. "Speed")
[4]   min           int32
[4]   max           int32
[4]   def           int32
[2]   len           int16       byte width for binary serialization (string fields)
[512] string        char[512]   NUL-terminated; pipe-delimited enum items, label text, etc.
[1]   showAs        visualRepresentation (char)  — 0=N/A, 4=dropmenu, 5=radiobuttons, 6=hidden, 7=color, 8=checkbox
[2]   x             int16
[2]   y             int16
[128] helpMessage   char[128]   NUL-terminated help text
[255] (union)       max(xdata=201, pad=255) = 255 bytes
                      xdata: conversionAction(1) + bRequired(4) + displayName[64] + szEnableExpression[128] + rollUpLength(4)
                      pad:   char[255]
[512] lpstrFilter   char[512]   NUL-terminated file filter (e.g. "*.iff;*.bmp")
```

### ButtonType constants
```python
BT_FIXED16        = 0   # Float (fixed-point 16.16), fp_scale=65536
BT_FIXED32        = 1   # Float (fixed-point 16.16), fp_scale=65536
BT_INT8           = 2   # Int, byte_width=1
BT_INT16          = 3   # Int, byte_width=2
BT_INT32          = 4   # Int, byte_width=4
BT_STRING         = 5   # Str, variable-length
BT_OBJECT_REF     = 6   # ObjRef
BT_FILENAME       = 7   # FileRef
BT_PROPERTY_SHEET = 8   # Section (collapsible rollup header)

# --- Type-level boolean flags (no data, presence is the signal) ---
# The level converter queries these via ContainsButtonType() — their *presence*
# in the .oad schema is a boolean property of the object type. No bytes are
# written for them in .lev or .iff output. Collect into schema.flags.
BT_NO_INSTANCES   = 9   # prevents adding instances; checked in level.cc
BT_NO_MESH        = 10  # suppresses mesh reference; checked in level.cc
BT_SINGLE_INST    = 11  # only one instance allowed
BT_TEMPLATE       = 12  # object goes on template list, not level (Generator source pool)

# --- Common-block section markers ---
# COMMONBLOCK begins a section whose fields are serialised into _CommonBlock.
# ENDCOMMON closes it. The level converter tracks isInCommonBlock between them.
BT_COMMON_BLOCK   = 17  # opens common block; itself occupies 4 bytes in binary
BT_END_COMMON     = 18  # closes common block

BT_GROUP_START    = 25  # Group (non-collapsible sub-box in UI)
BT_GROUP_STOP     = 26  # GroupEnd
# 13-16, 19-24 — camera/light/room/mesh extract flags — no Blender relevance, ignore
```

---

## Implementation

### New file: `wftools/wf_blender/wf_core.py`

One file, ~400 lines, replacing all five Rust crates. Divided into four sections:

#### Section 1: OAD reader

Struct layout directly from `wfsource/source/oas/oad.h` with `#pragma pack(1)` (no padding):

```python
import struct, os
from dataclasses import dataclass, field
from typing import Optional

# _oadHeader from oad.h: chunkId(4) + chunkSize(4) + name[68](68) + version(4) = 80 bytes
_OAD_HEADER = struct.Struct("<ii68si")
# _typeDescriptor from oad.h with #pragma pack(1): 1+64+4+4+4+2+512+1+2+2+128+255+512 = 1491 bytes
_OAD_ENTRY  = struct.Struct("<b64siiih512sbhh128s255s512s")

HEADER_SIZE = _OAD_HEADER.size   # 80
ENTRY_SIZE  = _OAD_ENTRY.size    # 1491

OAD_CHUNK_ID = b'OAD '  # FOURCC chunk identifier — see OAD_CHUNKID in wftools/oaddump/oad.cc

def _cstr(b: bytes) -> str:
    return b.split(b'\x00', 1)[0].decode('latin-1')

def _load_oad(path: str) -> tuple[str, list[dict]]:
    data = open(path, 'rb').read()
    chunk_id, chunk_size, name_b, version = _OAD_HEADER.unpack_from(data, 0)
    # chunkId field stores the FOURCC as a 32-bit int; compare bytes directly
    if data[0:4] != OAD_CHUNK_ID:
        raise ValueError(f"not an OAD file: bad chunk ID {data[0:4]!r}")
    schema_name = _cstr(name_b)
    entries = []
    pos = HEADER_SIZE
    while pos + ENTRY_SIZE <= len(data):
        (btype, name_b, mn, mx, df, blen, string_b,
         show_as, x, y, help_b, xdata, filter_b) = _OAD_ENTRY.unpack_from(data, pos)
        entries.append({
            'type': btype, 'name': _cstr(name_b),
            'min': mn, 'max': mx, 'default': df, 'len': blen,
            'string': _cstr(string_b), 'show_as': show_as,
            'help': _cstr(help_b), 'filter': _cstr(filter_b),
        })
        pos += ENTRY_SIZE
    return schema_name, entries
```

#### Section 2: Schema + Field objects (mirrors `wf_attr_schema`)

```python
@dataclass
class Field:
    key: str; label: str; kind: str; help: str; group: str
    min_raw: int; max_raw: int; default_raw: int
    default_display: float; min_display: float; max_display: float
    fp_scale: float; byte_width: int; show_as: int
    _enum_items: list = field(default_factory=list)
    class_tag: str = ""; file_filter: str = ""

    def enum_items(self): return list(self._enum_items)

@dataclass
class Schema:
    name: str
    fields: list  # list[Field]

    def visible_fields(self):
        return [f for f in self.fields if f.kind not in ('Skip',) and f.show_as != 6]

def load_schema(path: str) -> Schema:
    schema_name, entries = _load_oad(path)
    fields = []
    for e in entries:
        bt = e['type']
        # map ButtonType → kind string
        if bt in (0, 1):         # FIXED16/FIXED32
            kind, fp_scale, bw = 'Float', 65536.0, e['len'] or 4
        elif bt == 2:            kind, fp_scale, bw = 'Int', 0.0, 1
        elif bt == 3:            kind, fp_scale, bw = 'Int', 0.0, 2
        elif bt == 4:            kind, fp_scale, bw = 'Int', 0.0, 4
        elif bt == 5:            kind, fp_scale, bw = 'Str', 0.0, e['len']
        elif bt == 6:            kind, fp_scale, bw = 'ObjRef', 0.0, 0
        elif bt == 7:            kind, fp_scale, bw = 'FileRef', 0.0, 0
        elif bt == 8:            kind, fp_scale, bw = 'Section', 0.0, 0
        elif bt == 25:           kind, fp_scale, bw = 'Group', 0.0, 0
        elif bt == 26:           kind, fp_scale, bw = 'GroupEnd', 0.0, 0
        else:                    kind, fp_scale, bw = 'Skip', 0.0, 0

        scale = fp_scale if fp_scale > 0 else 1.0
        fields.append(Field(
            key=e['name'], label=e['name'], kind=kind,
            help=e['help'], group='',
            min_raw=e['min'], max_raw=e['max'], default_raw=e['default'],
            default_display=e['default'] / scale if fp_scale else float(e['default']),
            min_display=e['min'] / scale if fp_scale else float(e['min']),
            max_display=e['max'] / scale if fp_scale else float(e['max']),
            fp_scale=fp_scale, byte_width=bw, show_as=e['show_as'],
            _enum_items=e['string'].split('|') if kind == 'Str' and '|' in e['string'] else
                        [x.strip() for x in e['string'].split('|')] if kind == 'Int' else [],
            class_tag=e['string'] if kind == 'ObjRef' else '',
            file_filter=e['filter'] if kind == 'FileRef' else '',
        ))
    return Schema(name=schema_name, fields=fields)
```

> **Note on Enum detection:** the Rust `wf_attr_schema` uses the `string` field contents (pipe-delimited list) combined with `show_as` in (4, 5, 6) to identify Enum fields. The current Python draft uses Int + pipe-delimited string as the Enum heuristic — cross-check against a few `.oad` files during bring-up.

#### Section 3: Validation (mirrors `wf_attr_validate`)

```python
@dataclass
class ValidationIssue:
    key: str; message: str; is_error: bool

def validate(schema: Schema, values: dict) -> list[ValidationIssue]:
    issues = []
    for f in schema.visible_fields():
        v = values.get(f.key)
        if v is None or f.kind in ('Section', 'Group', 'GroupEnd', 'Skip', 'Str',
                                    'ObjRef', 'FileRef', 'Annotation'):
            continue
        if f.kind == 'Float':
            raw = int(round(float(v) * f.fp_scale))
        elif f.kind == 'Enum':
            raw = f._enum_items.index(v) if v in f._enum_items else 0
        else:
            raw = int(v)
        if f.min_raw != f.max_raw:   # 0==0 means unbounded in some OADs
            if raw < f.min_raw:
                issues.append(ValidationIssue(f.key, f"below minimum {f.min_display}", True))
            elif raw > f.max_raw:
                issues.append(ValidationIssue(f.key, f"above maximum {f.max_display}", True))
    return issues
```

#### Section 4: Serialization (mirrors `wf_attr_serialize` + `wf_iff`)

**Text export/import** reuses the tokenizer already in `export_level.py` — import it from there or copy the relevant 80 lines. The text format is the same iffcomp `.iff.txt` that `export_level.py` already parses for round-tripping.

**Binary export/import** — IFF chunk read/write is already in `extract_iff_chunks.py` (which handles `read_chunk_header`, FOURCC, LE size, alignment). Reuse that logic.

```python
def export_iff_txt(schema: Schema, values: dict) -> str:
    fourcc = (schema.name[:4].upper() + '    ')[:4]
    lines = [f"{{ '{fourcc}'"]
    for f in schema.visible_fields():
        if f.kind in ('Section', 'Group', 'GroupEnd', 'Skip'): continue
        v = values.get(f.key, f.default_raw)
        if f.kind == 'Float':
            raw = int(round(float(v) * f.fp_scale))
            lines.append(f"  {{ 'FX32' {{ 'NAME' \"{f.key}\" }} {{ 'DATA' {v:.6f}(1.15.16) }} {{ 'STR' \"{v:.6f}\" }} }}")
        elif f.kind in ('Int', 'Bool'):
            lines.append(f"  {{ 'I32'  {{ 'NAME' \"{f.key}\" }} {{ 'DATA' {int(v)}l }} {{ 'STR' \"{v}\" }} }}")
        elif f.kind == 'Enum':
            idx = f._enum_items.index(v) if v in f._enum_items else 0
            lines.append(f"  {{ 'I32'  {{ 'NAME' \"{f.key}\" }} {{ 'DATA' {idx}l }} {{ 'STR' \"{v}\" }} }}")
        elif f.kind in ('Str', 'ObjRef', 'FileRef'):
            lines.append(f"  {{ 'STR'  {{ 'NAME' \"{f.key}\" }} {{ 'DATA' \"{v}\" }} }}")
    lines.append("}")
    return '\n'.join(lines) + '\n'

def export_iff(schema: Schema, values: dict) -> bytes:
    # pack fields sequentially, LE, per byte_width
    payload = b''
    for f in schema.visible_fields():
        if f.kind in ('Section', 'Group', 'GroupEnd', 'Skip', 'Annotation'): continue
        v = values.get(f.key, f.default_raw)
        w = max(f.byte_width, 4) if f.kind != 'Str' else f.byte_width
        if f.kind == 'Float':
            raw = int(round(float(v) * f.fp_scale)) & 0xFFFFFFFF
            payload += struct.pack('<I', raw)
        elif f.kind == 'Enum':
            idx = f._enum_items.index(v) if v in f._enum_items else 0
            payload += struct.pack('<i', idx)
        elif f.kind in ('Int', 'Bool'):
            payload += struct.pack('<i', int(v))
        elif f.kind in ('Str', 'ObjRef', 'FileRef'):
            s = str(v).encode('latin-1') + b'\x00'
            payload += s[:w] if w else s
    # IFF chunk wrapper: FOURCC (BE u32) + size (LE u32) + payload
    fourcc_bytes = (schema.name[:4].upper() + '    ')[:4].encode('ascii')
    fourcc_int = struct.unpack('>I', fourcc_bytes)[0]
    return struct.pack('<II', fourcc_int, len(payload)) + payload

def import_iff_txt(schema: Schema, text: str) -> dict:
    # Reuse export_level._tokenize / _parse_level or a minimal inline parser.
    # The .iff.txt format for OAD values matches what export_iff_txt produces:
    # { 'I32' { 'NAME' "key" } { 'DATA' value } }
    # Parse NAME + DATA pairs from the top-level chunk body.
    from .export_level import _tokenize  # reuse existing tokenizer
    values = {}
    tokens = list(_tokenize(text))
    # walk tokens looking for { 'I32'/'FX32'/'STR' { 'NAME' "k" } { 'DATA' v } }
    ...  # ~40 lines
    return values

def import_iff(schema: Schema, data: bytes) -> dict:
    # strip 8-byte IFF header, then read fields in schema order
    payload = data[8:]
    pos = 0; values = {}
    for f in schema.visible_fields():
        if f.kind in ('Section', 'Group', 'GroupEnd', 'Skip', 'Annotation'): continue
        w = max(f.byte_width, 4)
        if pos + w > len(payload): break
        if f.kind == 'Float':
            raw = struct.unpack_from('<I', payload, pos)[0]
            values[f.key] = raw / f.fp_scale
        elif f.kind == 'Enum':
            idx = struct.unpack_from('<i', payload, pos)[0]
            values[f.key] = f._enum_items[idx] if 0 <= idx < len(f._enum_items) else ''
        elif f.kind in ('Int', 'Bool'):
            values[f.key] = struct.unpack_from('<i', payload, pos)[0]
        elif f.kind in ('Str', 'ObjRef', 'FileRef'):
            end = payload.find(b'\x00', pos, pos + (w or 512))
            values[f.key] = payload[pos:end].decode('latin-1') if end >= 0 else ''
        pos += w
    return values
```

---

## Bring-up notes

The main risk is **Enum detection**: the `BUTTON_STRING` + `show_as` + pipe-delimited `string` content combination is used to identify Enum fields. Cross-check against `wftools/oaddump` output on a few real `.oad` files (`actor.oad`, `room.oad`, `generator.oad`) to verify the Python mapping matches.

**Reference oracle:** the original C++ oaddump tool in `wftools/oaddump/`. Build it, then run:

```bash
# build (adjust Makefile flags as needed for your environment)
make -C wftools/oaddump
./wftools/oaddump/oaddump wfsource/source/oas/actor.oad
```

Expected: field list with `Type`, `Name`, `Min`, `Max`, `Default`, `ShowAs` for every entry. Compare field-by-field against `wf_core.py load_schema()` output.

The `oaddump.cc` parser (`QObjectAttributeData::Load`) is also useful to read alongside when debugging: it reads `sizeof(_oadHeader)` bytes then loops reading `sizeof(_typeDescriptor)` entries until stream EOF, which is exactly what `_load_oad()` replicates.

---

## Files Modified / Created

| Action | Path |
|---|---|
| **New** | `wftools/wf_blender/wf_core.py` — pure-Python replacement |
| Modify | `wftools/wf_blender/install.sh` — remove `wf_core.so` copy; add `wf_core.py` symlink |
| Modify | `wftools/wf_blender/__init__.py` — remove `.so` existence check; `import wf_core` now resolves to `wf_core.py` |
| Modify | `Taskfile.yml` — remove `blender-build` dep from `blender-install`; remove `blender-build` from `blender-package` |
| Modify | [docs/plans/2026-04-28-blender-addon-packaging.md](../2026-04-28-blender-addon-packaging.md) — update: no `wf_core.so`, no maturin build step |

The `wf_py/` Rust crate and all five dependency crates remain on disk — they're still used by other tools (`oaddump-rs`, test harnesses, etc.). We're only replacing the Blender-facing Python binding.

---

## Verification

1. `python3 -c "import sys; sys.path.insert(0,'wftools/wf_blender'); import wf_core; s = wf_core.load_schema('wfsource/source/oas/actor.oad'); print(s.name, len(s.fields), 'fields')"` — prints `Actor N fields`
2. Field-by-field diff against `oaddump-rs` output — types, defaults, ranges all match
3. Open Blender, enable addon (no `wf_core.so` in add-ons folder) — attaches schema, panel renders correctly
4. Round-trip: export `.iff.txt`, reimport — values survive unchanged
5. `task blender-package` — produced zip contains `wf_core.py`, no `.so` files
6. `task blender-install` — no maturin build step; installs in seconds
