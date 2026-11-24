"""WF Clocks: wflevels/clocks-menu.manifest is the roster, and scripts/pack-clocks-bundle.py packs it.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md, "The bundle and the chooser" (D2 to D4): stable
ids, Minute Machine is level 0, a new clock is appended, and the TOC position is the index the
Dream and the LEVEL extra start. A manifest id with no level stops the pack, naming it.
"""
import importlib.util
from pathlib import Path
import sys

import pytest

from level_menu_harness import read_menu, read_toc, SHELL_MENU, cdpack_binary

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / 'wflevels'
MANIFEST_PATH = LEVELS / 'clocks-menu.manifest'
sys.path.insert(0, str(ROOT / 'scripts'))
import level_manifest  # noqa: E402

spec = importlib.util.spec_from_file_location('pack_clocks_bundle', ROOT / 'scripts/pack-clocks-bundle.py')
packer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)

MANIFEST = level_manifest.read(MANIFEST_PATH)


def test_manifest_names_the_package_and_starts_with_minute_machine():
    assert (MANIFEST.title, MANIFEST.prompt) == ('WF Clocks', 'Choose a clock')
    assert MANIFEST.ids[0] == 'minute_machine'      # D2: level 0, never renumbered


def test_roster_has_the_intended_browsing_order():
    assert list(MANIFEST.ids) == [
        'minute_machine', 'tide_harbour', 'train_loops', 'bamboo_tipper_pond',
        'triple_axis_tourbillon', 'cuckoo_village', 'moon_lantern', 'metronome_forest',
        'lighthouse', 'anamorphic_shards', 'hour_tree', 'corolla_gauge', 'dutch_cuckoo_village',
        'mirror_haze', 'globe_sun_ring', 'lava_lamp_digits',
    ]


def test_the_committed_bundle_holds_the_committed_levels():
    """Plan Q12: the clocks commit their built levels and bundle (task clocks-check proves they rebuild identically)."""
    data = (LEVELS / 'clocks-cd.iff').read_bytes()
    toc = read_toc(data)
    for (_, offset, size), clock in zip(toc[1:1 + len(MANIFEST.ids)], MANIFEST.ids):
        assert data[offset:offset + size] == (LEVELS / f'{clock}-standalone.iff').read_bytes(), clock
    assert read_menu(data)['entries'] == [(i, e.menu_name) for i, e in enumerate(MANIFEST.entries)]


def test_every_manifest_id_has_a_level_source():
    """Each clock is built from wflevels/<id>/build.sh (the standalone .iff itself is a build output)."""
    missing = [i for i in MANIFEST.ids if not (LEVELS / i / 'build.sh').is_file()]
    assert not missing, f'clocks-menu.manifest lists clocks with no wflevels/<id>/build.sh: {missing}'


def test_pack_script_defaults_to_the_clocks_manifest_and_flavor():
    assert packer.MANIFEST == MANIFEST_PATH
    assert packer.SHELL_MENU == SHELL_MENU
    assert packer.ASSETS == ROOT / 'android/screensaver/src/clocks/assets'


def test_unknown_id_stops_the_pack_naming_it(tmp_path, capsys):
    (tmp_path / 'real-standalone.iff').write_bytes(b'FORM')
    manifest = tmp_path / 'clocks-menu.manifest'
    manifest.write_text('title T\nprompt P\nlevel real-standalone.iff | Real\n'
                        'level no_such_clock-standalone.iff | Missing\n')
    assert packer.missing_levels(manifest) == ['no_such_clock']
    out = tmp_path / 'cd.iff'
    assert packer.main(['--manifest', str(manifest), '--output', str(out), '--no-link']) == 2
    assert 'no_such_clock' in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.skipif(bool(packer.missing_levels(MANIFEST_PATH)),
                    reason='build the clock levels first (task minute-machine-level, task tide-harbour-level)')
def test_bundle_toc_order_is_the_manifest_order(tmp_path, monkeypatch):
    monkeypatch.setenv('WF_CDPACK', str(cdpack_binary()))
    out = tmp_path / 'cd.iff'
    assert packer.main(['--output', str(out), '--no-link']) == 0
    data = out.read_bytes()
    toc = read_toc(data)
    ids = MANIFEST.ids
    # SHEL (shell-menu.fth), every clock in manifest order, MENU, then the UI font.
    assert len(toc) == len(ids) + 3
    assert (toc[0][0], toc[-2][0], toc[-1][0]) == (b'SHEL', b'MENU', b'UIFT')
    shell_offset, shell_size = toc[0][1:]
    assert data[shell_offset + 8:shell_offset + 8 + shell_size] == SHELL_MENU.read_bytes()
    for (_, offset, size), clock in zip(toc[1:1 + len(ids)], ids):
        assert data[offset:offset + size] == (LEVELS / f'{clock}-standalone.iff').read_bytes(), clock
    assert read_menu(data) == dict(version=1, levels=len(ids), title=MANIFEST.title, prompt=MANIFEST.prompt,
                                   entries=[(i, e.menu_name) for i, e in enumerate(MANIFEST.entries)])
