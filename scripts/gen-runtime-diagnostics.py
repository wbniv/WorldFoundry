#!/usr/bin/env python3
"""Generate runtime diagnostics UI metadata from the engine option inventory."""
import json
from pathlib import Path
import sys
from runtime_options_inventory import inventory
from level_memory_settings import FIELDS

out = Path(sys.argv[1])
quote = lambda value: json.dumps(str(value), ensure_ascii=True)
lines = ['// Generated from runtime_options_inventory.py and level_memory_settings.py.']
for field in inventory():
    kind = field['value_type']
    numeric = kind in ('bool', 'int')
    low, high, initial = (1, 1000, '20') if kind == 'int' else (0, 1, '1' if field['id'] == 1000 else '0')
    help_text = ' / '.join(field['cli']) + '. ' + (field['reason'] or field['policy'] + '; apply through runtime consumer')
    lines.append('RUNTIME_FIELD(%d,%s,%s,%s,%s,%d,%d,%d,%s,%d)' % (
        field['id'], quote(field['key']), quote(field['label']), quote(field['group']), quote(help_text),
        4 if kind == 'bool' else 0 if numeric else 3, low if numeric else 0,
        high if numeric else 255, quote(initial if numeric else 'unavailable'), int(field['id'] != 1000)))
for ident, key, label, low, high in FIELDS:
    lines.append('MEMORY_FIELD(%d,%s,%s,%d,%d)' % (ident, quote('memory_'+key), quote(label), low, high))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text('\n'.join(lines) + '\n')
