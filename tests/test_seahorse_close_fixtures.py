"""Benchmark fixtures preserve baked geometry and the existing crawl trajectory."""
import importlib.util
import json
import sys
from pathlib import Path
import pytest
import test_species_movement as movement
from test_species_movement import vm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('close_fixture', ROOT / 'scripts/build-seahorse-close-variants.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_baked_slots_and_fail_closed():
    level = (ROOT / 'wflevels/aquarium_plants-standalone.iff').read_bytes()
    sources = fixture.scripts((ROOT / 'wflevels/aquarium_plants/aquarium_plants.lev').read_text())
    for view in ('wide-idle', 'close-idle', 'close-crawl'):
        patched, slots = fixture.patch_level(level, sources, view)
        assert len(patched) == len(level)
        cursor = 0
        for slot in sorted(slots, key=lambda s: s['offset']):
            start, end = slot['offset'], slot['offset'] + slot['size']
            assert patched[cursor:start] == level[cursor:start]
            assert patched[end] == 0
            cursor = end
        assert patched[cursor:] == level[cursor:]
    with pytest.raises(ValueError):
        fixture.patch_level(level + sources['Player'].encode() + b'\0', sources, 'close-idle')
    with pytest.raises(ValueError):
        fixture.patch_script(sources['Player'].replace(fixture.HELD, ''), 'close-crawl')


def test_held_right_matches_existing_controller(vm, tmp_path, monkeypatch):
    prefix = 'prop 4 2 1\nreset 0 -.85 .865\n'
    reference = vm('plants', prefix + 'step 1500 8192 .05\n')
    here = ROOT / 'wflevels/aquarium_plants'
    original = (here / 'aquarium_plants.lev').read_text()
    sources = fixture.scripts(original)
    target = tmp_path / 'wflevels/aquarium_plants'
    target.mkdir(parents=True)
    (target / 'actor-map.json').write_bytes((here / 'actor-map.json').read_bytes())
    monkeypatch.setattr(movement, 'ROOT', tmp_path)
    for view in ('close-idle', 'close-crawl'):
        text = original
        for source in sources.values():
            text = text.replace(json.dumps(source), json.dumps(fixture.patch_script(source, view)))
        (target / 'aquarium_plants.lev').write_text(text)
        rows = vm('plants', prefix + 'step 1500 0 .05\n')
        for i, row in enumerate(rows):
            if view == 'close-crawl':
                for key in ('x', 'y', 'z', 'vx', 'vy', 'vz'):
                    assert row[key] == pytest.approx(reference[i][key], abs=1e-7)
            else:
                assert row['x'] == pytest.approx(0, abs=1e-7)
        if view == 'close-crawl':
            assert rows[-1]['x'] > .9
