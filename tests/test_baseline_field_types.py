"""The baseline's two settings owners: Field types (one field per touch-settings example)
and Runtime settings (the runtime and load-time sheets), standing on one spot.

docs/plans/2026-10-31-baseline-settings-cleanup.md. The checks run on the source
(field_types.py), on the generated bindings, on the catalog cooked into the committed
level, and through the engine's own registry, host and runtime-options code.
"""
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'wflevels/baseline'
sys.path.insert(0, str(BASE))
import field_types  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY = load('baseline_verify', BASE / 'verify.py')
COOKER = load('baseline_cooker', ROOT / 'scripts/build-object-properties.py')
TOUCH = load('touch_examples_test', ROOT / 'tests/test_touch_settings_plan_examples.py')
CASES = json.loads(field_types.EXAMPLES_PATH.read_text())
IDS = json.loads((BASE / 'actor-map.json').read_text())['indices']
RUNTIME_SHEETS = ['Runtime Options', 'Level Memory', 'Level Behavior']


def level_owners():
    level = (ROOT / 'wflevels/baseline-standalone.iff').read_bytes()
    offset = level.rfind(b'RPRP')
    size, = struct.unpack_from('<I', level, offset + 4)
    return VERIFY.catalog_rows(level[offset + 8:offset + 8 + size])


def check_source(rows):
    """field_types.ROWS against the examples JSON: one row per id, nothing else."""
    keys = [r['key'] for r in rows]
    assert len(keys) == len(set(keys))
    assert sorted(keys) == sorted(c['id'] for c in CASES)
    ids = [r['id'] for r in rows]
    assert len(ids) == len(set(ids)) and all(1 <= i < 1000 for i in ids)  # clear of runtime/memory ids


def check_bindings(bindings):
    keys = list(bindings['fields']) + [a['action'] for a in bindings['actions']]
    assert sorted(keys) == sorted(c['id'] for c in CASES)
    assert bindings['owner'] == 'FieldTypes' and bindings['title'] == 'Field types'


def check_catalog(owners):
    """The cooked catalog: owners, sheets and rows."""
    assert [(o['owner'], o['schema'], o['title']) for o in owners] == [
        (IDS['FieldTypes'], 'FieldTypes', 'Field types'), (IDS['RuntimeSettings'], 'Settings', 'Runtime settings')]
    types, runtime = owners
    assert sorted(r['key'] for r in types['rows']) == sorted(c['id'] for c in CASES)
    assert types['sheets'] == field_types.SECTIONS
    assert not any(r['key'].startswith(('runtime_', 'memory_')) for r in types['rows'])
    assert not set(types['sheets']) & set(RUNTIME_SHEETS)
    assert runtime['sheets'] == RUNTIME_SHEETS and len(runtime['rows']) == 85


def test_field_ids_are_the_27_examples():
    assert len(CASES) == 27
    check_source(field_types.rows())
    check_bindings(json.loads((BASE / 'field-types-bindings.json').read_text()))
    check_catalog(level_owners())


def test_generated_sources_match_field_types_py():
    """field-types.oas/-bindings.json are generated output, not hand edits."""
    import settings_fixture
    assert (BASE / 'field-types.oas').read_text() == field_types.oas(settings_fixture.TYPES, settings_fixture.SHOW)
    assert json.loads((BASE / 'field-types-bindings.json').read_text()) == field_types.bindings()


def test_every_required_type_showas_pair_is_in_the_level():
    """Every pair the touch plan requires has a row, compiled with that showAs code."""
    covered = {(EXAMPLE['type'], EXAMPLE['showAs']) for EXAMPLE in (r['case'] for r in field_types.rows())}
    assert TOUCH.REQUIRED_PAIRS <= covered
    assert covered == {(c['type'], c['showAs']) for c in CASES}
    schema = json.loads(subprocess.check_output(
        [ROOT / 'wftools/wf_attr_edit/target/release/catalog', BASE / 'field-types.oad'], text=True))
    compiled = {f['key']: f for f in schema['fields']}
    # Normalizer kind per JSON type (its first word, or the whole type when it names two).
    kinds = {'Int': {'Int'}, 'Float': {'Float'}, 'Enum': {'Enum'}, 'Bool': {'Bool', 'Int'}, 'Str': {'Str'},
             'Str / Annotation': {'Annotation'}, 'FileRef / ObjRef': {'ObjRef'}}
    for row in field_types.rows():
        if row['kind'] == 'action':
            continue
        f = compiled[row['key']]
        show = int(re.search(r'\((\d+)\)', row['case']['showAs']).group(1))
        assert f['show'] == show, row['key']
        assert f['label'] == row['label'], row['key']
        family = row['case']['type'] if row['case']['type'] in kinds else row['case']['type'].split()[0]
        assert f['kind'] in kinds[family], (row['key'], f['kind'])
    # Bool + CHECKBOX is a Bool; Bool + TOGGLE compiles to Int (recorded gap in field_types.GAPS).
    assert compiled['bool-checkbox']['kind'] == 'Bool' and compiled['bool-toggle']['kind'] == 'Int'


def test_labels_and_values_come_from_the_examples_json():
    for row in field_types.rows():
        label, value = field_types.split_sample(row['case'])
        if row['kind'] == 'action':
            assert row['label'] == ('' if row['key'] == 'spacer' else row['case']['sample'])
            continue
        assert (row['group'] + ' / ' + row['label'] if row['group'] else row['label']) == label
        if row['kind'] == 'Enum':
            choices, shown = row['choices'], row['display']
            # The sample names the chosen option, lists every option, counts them, gives
            # "id (label)", or cuts a long label short with an ellipsis.
            assert (value == shown or value.split(' / ') == choices or value == '%d choices' % len(choices)
                    or value == '%d (%s)' % (choices.index(shown), shown)
                    or (value.endswith('…') and shown.startswith(value[:-1]))), row['key']
        elif row['kind'] == 'Annotation':
            assert row['initial'].split('\n')[0] == value.rstrip('…'), row['key']
        else:
            assert row['display'] == value, row['key']


def test_runtime_settings_carries_exactly_the_three_sheets():
    source = (BASE / 'runtime-settings.oas').read_text()
    assert re.findall(r'PROPERTY_SHEET_HEADER\(([^,]+),', source) == RUNTIME_SHEETS
    assert 'TYPEHEADER(Settings)' in source  # the schema the runtime-options consumer serves
    bindings = json.loads((BASE / 'runtime-settings-bindings.json').read_text())
    assert bindings['owner'] == 'RuntimeSettings' and len(bindings['fields']) == 85
    assert not (BASE / 'settings.oas').exists() and not (BASE / 'settings-bindings.json').exists()


def test_the_two_owners_share_one_spot():
    """Same spot, so Pick in 3D shows one bracket and the "Objects here" list."""
    inventory = BASE / 'build/scene-inventory.json'  # written by every export (task baseline:build)
    if not inventory.exists():
        pytest.skip('no build/scene-inventory.json; run task baseline:build')
    config = [o for o in json.loads(inventory.read_text()) if o['collection'] == 'CONFIG' and o['schema'] == 'target.oad']
    assert [o['name'] for o in config] == ['FieldTypes', 'RuntimeSettings']
    assert config[0]['position'] == config[1]['position'] == list(map(float, field_types.POSITION))


def test_engine_registry_loads_both_owners_syncs_runtime_and_ignores_the_action(tmp_path):
    """The real registry/host/runtime-options code on the catalog cooked into the level."""
    level = (ROOT / 'wflevels/baseline-standalone.iff').read_bytes()
    offset = level.rfind(b'RPRP')
    size, = struct.unpack_from('<I', level, offset + 4)
    payload = tmp_path / 'baseline.rprp'
    payload.write_bytes(level[offset + 8:offset + 8 + size])
    exe = tmp_path / 'baseline-owners'
    subprocess.run(['c++', '-std=c++17', '-O1', '-I' + str(ROOT / 'engine'), str(ROOT / 'tests/baseline_owners_test.cpp'),
                    *[str(ROOT / 'engine' / n) for n in ['runtime_properties.cpp', 'runtime_property_form.cpp', 'runtime_property_host.cpp']],
                    str(ROOT / 'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'), '-ldl', '-lpthread', '-lm', '-o', str(exe)], check=True)
    out = subprocess.run([exe, payload, str(IDS['FieldTypes']), str(IDS['RuntimeSettings'])],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    values = {}
    for line in out.stdout.splitlines():
        if line.startswith('field %d ' % IDS['FieldTypes']):
            key = re.search(r' key=(\S+) ', line).group(1)
            values[key] = json.loads(line.split(' value=', 1)[1])
    for row in field_types.rows():
        if row['kind'] != 'action':
            assert values[row['key']] == row['initial'], row['key']
    assert 'editable %d %d' % (IDS['FieldTypes'], IDS['RuntimeSettings']) in out.stdout
    assert 'action-inert key=action' in out.stdout


# --- Mutation checks: the tests above must fail when the owners lose a field. ---

def test_source_check_fails_when_a_field_is_dropped(monkeypatch):
    for dropped in (field_types.ROWS[0], field_types.ROWS[-1]):  # a descriptor row, and the spacer
        monkeypatch.setattr(field_types, 'ROWS', [r for r in field_types.ROWS if r is not dropped])
        with pytest.raises(AssertionError):
            check_source(field_types.rows())
        with pytest.raises(AssertionError):
            check_bindings(field_types.bindings())


def test_catalog_check_fails_when_a_field_is_dropped():
    owners = level_owners()
    check_catalog(owners)
    bindings = json.loads((BASE / 'field-types-bindings.json').read_text())
    del bindings['fields']['enum-many']
    cooked = COOKER.catalog(BASE / 'field-types.oad', bindings, IDS['FieldTypes'])
    runtime = COOKER.catalog(BASE / 'runtime-settings.oad',
                             json.loads((BASE / 'runtime-settings-bindings.json').read_text()), IDS['RuntimeSettings'])
    with pytest.raises(AssertionError):
        check_catalog(VERIFY.catalog_rows(b'RP01' + struct.pack('<I', 2) + cooked[8:] + runtime[8:]))
