#!/usr/bin/env python3
"""Turn an OAD-derived RP01 settings catalog into a provider capabilities asset.

RP01 already records every owner, its type, and the fields compiled from its OAD.
Reading that catalog keeps multiple Settings objects distinct and avoids an
application-specific list of exposed fields.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import struct


class CatalogError(ValueError):
    pass


class Reader:
    def __init__(self, data):
        self.data = memoryview(data)
        self.pos = 0

    def take(self, length):
        if length < 0 or self.pos + length > len(self.data):
            raise CatalogError("truncated RP01 catalog")
        chunk = self.data[self.pos:self.pos + length]
        self.pos += length
        return chunk

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))

    def string(self):
        length, = self.unpack("<I")
        if length > 65536:
            raise CatalogError("oversized RP01 string")
        return bytes(self.take(length)).decode("utf-8")


def _number(raw, scale):
    if scale <= 0:
        raise CatalogError("fixed-point field has no scale")
    return str(Decimal(raw) / Decimal(scale))


def _field(record):
    (fid, kind, show, readonly, rule, low, high, scale, _width, max_length,
     key, label, help_text, group, choices, initial) = record
    if not 1 <= fid <= 32767 or kind in (9, 10):
        return None  # A sheet/group marker or an action, not a setting field.
    if show == 6:
        raise CatalogError(f"hidden field {key} should not be in RP01")
    setting = {"id": str(fid), "key": key, "label": label or key,
               "show": show, "value": initial, "readonly": bool(readonly)}
    if group:
        setting["group"] = group
    if help_text:
        setting["help"] = help_text
    if rule == 1:
        setting.update(type="integer", minimum="0", maximum="4294967295")
    elif show in (3, 8) and low == 0 and high == 1:
        setting.update(type="boolean", value="true" if initial in ("1", "true", "True") else "false")
    elif kind == 2 and choices:
        options = choices.split("|")
        if len(options) != high - low + 1:
            raise CatalogError(f"{key}: choice count does not match range")
        setting.update(type="choice", options=[{"id": str(low + i), "label": value}
                                               for i, value in enumerate(options)])
    elif kind == 4:
        setting.update(type="boolean", value="true" if initial in ("1", "true", "True") else "false")
    elif kind in (0, 2):
        setting.update(type="integer", minimum=str(low), maximum=str(high))
    elif kind == 1:
        setting.update(type="decimal", minimum=_number(low, scale), maximum=_number(high, scale))
    elif kind in (3, 8):
        setting.update(type="text", max_length=max_length or 256)
        if kind == 8:
            setting["readonly"] = True  # References cannot be safely changed through content call.
    else:
        raise CatalogError(f"{key}: unsupported field kind {kind}")
    if rule == 2:
        setting["multiline"] = True
    return setting


def capabilities(payload):
    reader = Reader(payload)
    if bytes(reader.take(4)) != b"RP01":
        raise CatalogError("missing RP01 header")
    count, = reader.unpack("<I")
    if not 1 <= count <= 64:
        raise CatalogError("invalid Settings owner count")
    objects = []
    seen_owners = set()
    for _ in range(count):
        owner, = reader.unpack("<I")
        type_name, title = reader.string(), reader.string()
        if owner in seen_owners or not 1 <= len(type_name) <= 96:
            raise CatalogError("duplicate owner or invalid catalog type")
        seen_owners.add(owner)
        field_count, = reader.unpack("<I")
        if field_count > 1024:
            raise CatalogError("oversized Settings field count")
        settings = []
        ids = set()
        for _ in range(field_count):
            head = reader.unpack("<IBBBBiiIII")
            strings = tuple(reader.string() for _ in range(6))
            entry = _field(head + strings)
            if entry is None:
                continue
            if entry["id"] in ids:
                raise CatalogError(f"{type_name}: duplicate field {entry['id']}")
            ids.add(entry["id"])
            settings.append(entry)
        objects.append({"owner": owner, "type": type_name, "title": title,
                        "settings": settings})
    if reader.pos != len(reader.data):
        raise CatalogError("trailing RP01 bytes")
    return {"schema": 2, "objects": objects}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rprp", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    document = capabilities(args.rprp.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(args.out.suffix + ".tmp")
    temporary.write_text(json.dumps(document, separators=(",", ":")) + "\n")
    temporary.replace(args.out)
    print(f"Settings capabilities: {len(document['objects'])} owner(s) in {args.out}")


if __name__ == "__main__":
    main()
