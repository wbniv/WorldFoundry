"""The baseline "Field types" owner: one settings field per touch-settings example.

docs/plans/2026-10-29-touch-settings-examples.json lists the 27 sensible type x showAs
cases. This module is the only place that says how each one is spelled as an OAS
descriptor. Labels come from the JSON's ``sample`` ("Label · value") and so do the
values, so the touch plan, its test and the baseline level cannot drift apart.

Field ids are part of the device contract (validators address fields by id): keep
them, and give a new example the next free id.

Plan: docs/plans/2026-10-31-baseline-settings-cleanup.md.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLES_PATH = ROOT / 'docs/plans/2026-10-29-touch-settings-examples.json'
EXAMPLES = {case['id']: case for case in json.loads(EXAMPLES_PATH.read_text())}

OWNER = 'FieldTypes'
TITLE = 'Field types'
# Its own schema, so the runtime-options consumer (schema "Settings") never sees it:
# Apply commits straight to the registry and the action row stays inert.
SCHEMA = 'FieldTypes'
POSITION = (2, -4, 1)
FIXED = 65536

SECTIONS = ['Numbers', 'Choices', 'Switches', 'Text', 'References', 'Actions']

# One row per example id, in form order: (field id, example id, section, descriptor).
# Descriptor keys: t (OAS type), show (SHOW_AS name), lo/hi (range), choices, pick
# (which choice the sample shows), group, help, readonly, rule, filter, length.
ROWS = [
    (1, 'int-number', 'Numbers', dict(t='INT32', show='NUMBER', lo=0, hi=86400)),
    (2, 'int-slider', 'Numbers', dict(t='INT32', show='SLIDER', lo=0)),
    (3, 'int-color', 'Numbers', dict(t='INT32', show='COLOR', lo=0, hi=0xFFFFFF)),
    (4, 'int-mailbox', 'Numbers', dict(t='INT32', show='MAILBOX', lo=0, hi=159)),
    (5, 'int-default', 'Numbers', dict(t='INT32', show='N_A', lo=0, hi=99)),
    (6, 'float-number', 'Numbers', dict(t='FIXED32', show='NUMBER', lo=0, hi=240)),
    (7, 'float-slider', 'Numbers', dict(t='FIXED32', show='SLIDER', lo=0, hi=1)),
    (22, 'int-readonly', 'Numbers', dict(t='INT32', show='NUMBER', lo=0, hi=99, readonly=True)),
    (25, 'int-help', 'Numbers', dict(t='INT32', show='NUMBER', lo=0, hi=100,
                                     help='How bright the lights are; 0 is off.')),
    (8, 'enum-default', 'Choices', dict(t='INT32', show='N_A', choices=['Calm', 'Lively', 'Stormy'])),
    (9, 'enum-number', 'Choices', dict(t='INT32', show='NUMBER', choices=['None', 'Speed', 'Flying', 'Shield'])),
    (10, 'enum-dropdown', 'Choices', dict(t='INT32', show='DROPMENU', choices=['Freshwater', 'Saltwater'])),
    (11, 'enum-radio', 'Choices', dict(t='INT32', show='RADIOBUTTONS', pick=0)),
    (12, 'enum-slider', 'Choices', dict(t='INT32', show='SLIDER', pick=1)),
    (13, 'enum-toggle', 'Choices', dict(t='INT32', show='TOGGLE', pick=0)),
    (14, 'enum-combo', 'Choices', dict(t='INT32', show='COMBOBOX', choices=['Staff', 'Sword', 'Bow'])),
    (23, 'enum-many', 'Choices', dict(t='INT32', show='RADIOBUTTONS',
                                      choices=['Choice %d' % i for i in range(1, 13)], pick=3)),
    (24, 'enum-long', 'Choices', dict(t='INT32', show='DROPMENU', choices=[
        'Along the northern wall, facing the glass',
        'In the middle of the tank, under the light',
        'Beside the filter intake, behind the rocks'])),
    (15, 'bool-checkbox', 'Switches', dict(t='INT32', show='CHECKBOX', lo=0, hi=1)),
    (16, 'bool-toggle', 'Switches', dict(t='INT32', show='TOGGLE', lo=0, hi=1)),
    (17, 'str-plain', 'Text', dict(t='STRING', show='N_A', length=32)),
    (18, 'str-uint32', 'Text', dict(t='STRING', show='NUMBER', length=11, rule='uint32-decimal')),
    (19, 'str-multiline', 'Text', dict(t='XDATA', show='TEXTEDITOR', multiline=True)),
    (20, 'str-filename', 'Text', dict(t='STRING', show='FILENAME', length=32, filter='*.png')),
    (21, 'ref-readonly', 'References', dict(t='OBJECT_REFERENCE', show='N_A', readonly=True)),
    # No descriptor: bindings.json "actions" (kind 9, and "spacer" is kind 10).
    (26, 'action', 'Actions', dict(action='action')),
    (27, 'spacer', 'Actions', dict(action='spacer')),
]

# Coverage gaps that are true of this owner on the current engine (settings-coverage.json).
GAPS = [
    'Field types action row "action" has no consumer: Host::apply returns false for an '
    'unregistered action (engine/runtime_property_host.cpp), so it is inert by design here.',
    'bool-toggle (INT32 0..1, SHOW_AS_TOGGLE, no choices) compiles to kind Int, not Bool: '
    'the normalizer only classifies SHOW_AS_CHECKBOX as Bool (wftools/wf_attr_schema).',
    'str-multiline is an XDATA TEXTEDITOR descriptor (kind Annotation, cooked as Str rule 2).',
]


def split_sample(case):
    """"Label · value" -> (label, value). Actions and spacers have no value."""
    label, _, value = case['sample'].partition(' · ')
    return label, value


def _number(text):
    return text.split()[0]


def rows():
    """Each row resolved against the JSON: label, group, value and descriptor fields."""
    out = []
    for field_id, example, section, d in ROWS:
        case = EXAMPLES[example]
        label, sample = split_sample(case)
        row = dict(id=field_id, key=example, section=section, case=case, group=None, help=d.get('help', ''),
                   readonly=d.get('readonly', False), rule=d.get('rule'), multiline=d.get('multiline', False))
        if 'action' in d:
            row.update(kind='action', action=d['action'], label='' if d['action'] == 'spacer' else case['sample'])
            out.append(row)
            continue
        if ' / ' in label:  # "Lighting / Intensity": a group heading, then the field.
            row['group'], label = label.split(' / ', 1)
        row.update(label=label, type=d['t'], show=d['show'])
        if 'choices' in d or 'pick' in d:
            choices = d.get('choices') or sample.split(' / ')
            if 'pick' in d:
                pick = d['pick']
            elif sample.endswith('…'):
                pick = next(i for i, c in enumerate(choices) if c.startswith(sample[:-1]))
            elif sample[:1].isdigit():  # "2 (Flying)": the numeric id, then its label.
                pick = int(_number(sample))
                assert choices[pick] == sample.split('(', 1)[1].rstrip(')'), example
            else:
                pick = choices.index(sample)
            row.update(kind='Enum', lo=0, hi=len(choices) - 1, default=pick, choices=choices,
                       initial=str(pick), display=choices[pick])
        elif d['t'] == 'INT32':
            if d['show'] == 'COLOR':
                value = int(sample.lstrip('#'), 16)
            elif d['show'] == 'CHECKBOX' or d['show'] == 'TOGGLE':
                value = {'On': 1, 'Off': 0}[sample]
            else:
                value = int(_number(sample))
            hi = d['hi'] if 'hi' in d else int(sample.split(' / ')[1])  # "65 / 100"
            row.update(kind='Int', lo=d['lo'], hi=hi, default=value, initial=str(value), display=sample)
        elif d['t'] == 'FIXED32':
            value = _number(sample)
            row.update(kind='Float', lo=d['lo'] * FIXED, hi=d['hi'] * FIXED, default=round(float(value) * FIXED),
                       initial=value, display=sample)
        elif d['t'] == 'XDATA':
            first = sample.rstrip('…')  # The sample shows the first line, cut short.
            row.update(kind='Annotation', initial=first + '\nSecond line', display=sample)
        elif d['t'] == 'STRING':
            row.update(kind='Str', length=d['length'], initial=sample, display=sample, filter=d.get('filter'))
        elif d['t'] == 'OBJECT_REFERENCE':
            row.update(kind='ObjRef', initial=sample, display=sample)
        else:
            raise ValueError('No descriptor spelling for ' + example)
        out.append(row)
    return out


def descriptor(row, types, shows):
    """One OAS descriptor line, in the same direct spelling settings_fixture.py uses."""
    q = lambda s: json.dumps(s, ensure_ascii=False)
    t = row['type']
    code, show = types.index(t), shows.index(row['show'])
    if t == 'STRING':
        lo, hi, default, length = 0, row['length'] - 1, 0, row['length']
    elif t == 'XDATA':
        lo, hi, default, length = 0, 10, 0, 80
    elif t == 'OBJECT_REFERENCE':
        lo, hi, default, length = 0, 10, 0, 12
    else:
        lo, hi, default, length = row['lo'], row['hi'], row['default'], 0
    choices = '|'.join(row.get('choices') or [])
    filt = '"Assets\\0' + row['filter'] + '\\0\\0"' if row.get('filter') else '""'
    return ('{' + ','.join([str(code), q(row['key']), str(lo), str(hi), str(default), str(length), q(choices),
                            str(show), '-1', '-1', q(row['help']), '{0,0,' + q(row['label']) + ',"1"}', filt]) + '},')


def oas(types, shows):
    """field-types.oas: six sheets in SECTIONS order; actions follow the last (empty) sheet."""
    lines = ['@* Generated by settings_fixture.py from field_types.py; do not hand-edit.',
             'TYPEHEADER(' + SCHEMA + ')']
    resolved = rows()
    for n, section in enumerate(SECTIONS):
        lines.append('PROPERTY_SHEET_HEADER(%s,%d)' % (section, 1 if n == 0 else 0))
        group = None
        for row in resolved:
            if row['section'] != section or row['kind'] == 'action':
                continue
            if row['group'] != group:
                if group is not None:
                    lines.append('GROUP_STOP()')
                group = row['group']
                if group is not None:
                    lines.append('GROUP_START(' + group + ')')
            lines.append(descriptor(row, types, shows))
        if group is not None:
            lines.append('GROUP_STOP()')
        lines.append('PROPERTY_SHEET_FOOTER')
    lines.append('TYPEFOOTER')
    return '\n'.join(lines) + '\n'


def bindings():
    """field-types-bindings.json: ids and initial values; the two actions after the fields."""
    fields, actions = {}, []
    for row in rows():
        if row['kind'] == 'action':
            actions.append(dict(id=row['id'], label=row['label'], action=row['action']))
            continue
        b = dict(id=row['id'])
        if row['kind'] in ('Float', 'Str', 'Annotation', 'ObjRef'):
            b['initial'] = row['initial']
        if row['readonly']:
            b['readonly'] = True
        if row['rule']:
            b['rule'] = row['rule']
        if row['multiline']:
            b['multiline'] = True
        if row['kind'] == 'Str':
            b['max_length'] = row['length'] - 1
        if row['kind'] == 'Annotation':
            b['max_length'] = 80
        fields[row['key']] = b
    return dict(version=1, owner=OWNER, title=TITLE, fields=fields, actions=actions)
