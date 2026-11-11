#!/usr/bin/env python3
"""Generate a provider capabilities asset from an actor OAD."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class CatalogError(ValueError):
    pass


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
        raise CatalogError(f"hidden field {key} cannot be exposed")
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


def capabilities_oad(oad, inherited, actor, type_name, title, excluded=()):
    """Build one provider owner from the same actor descriptor used at runtime."""
    prefix = inherited.read_bytes()
    if len(prefix) < 80 or (len(prefix) - 80) % 1491:
        raise CatalogError("invalid inherited OAD")
    first = (len(prefix) - 80) // 1491
    normalized = json.loads(subprocess.check_output(
        [str(ROOT/'wftools/wf_attr_edit/target/release/catalog'), str(oad)], text=True))
    kinds = {'Int': 0, 'Float': 1, 'Enum': 2, 'Bool': 4}
    settings = []
    for field in normalized['fields']:
        if field['index'] < first or field['key'] in excluded or field['kind'] not in kinds or field['show'] == 6:
            continue
        kind = kinds[field['kind']]
        initial = _number(field['default'], field['scale']) if kind == 1 else str(field['default'])
        record = (field['index'], kind, field['show'], not field['live'], 0,
                  field['min'], field['max'], field['scale'], field['width'], 256,
                  field['key'], field['label'], field['help'], field['group'], field['choices'], initial)
        setting = _field(record)
        if setting is not None:
            settings.append(setting)
    return {'schema': 2, 'objects': [{'owner': actor, 'type': type_name, 'title': title, 'settings': settings}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--oad", type=Path, required=True)
    parser.add_argument("--inherited-oad", type=Path)
    parser.add_argument("--actor-map", type=Path)
    parser.add_argument("--actor-name")
    parser.add_argument("--type")
    parser.add_argument("--title")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not all((args.inherited_oad, args.actor_map, args.actor_name, args.type, args.title)):
        parser.error("--oad requires --inherited-oad, --actor-map, --actor-name, --type and --title")
    actor = json.loads(args.actor_map.read_text())['indices'][args.actor_name]
    document = capabilities_oad(args.oad, args.inherited_oad, actor, args.type, args.title, args.exclude)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(args.out.suffix + ".tmp")
    temporary.write_text(json.dumps(document, separators=(",", ":")) + "\n")
    temporary.replace(args.out)
    print(f"Settings capabilities: {len(document['objects'])} owner(s) in {args.out}")


if __name__ == "__main__":
    main()
