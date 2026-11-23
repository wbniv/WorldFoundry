"""The Aquarium tanks of wflevels/aquarium-menu.manifest in the real selector, preserving exact standalone payloads."""
from pathlib import Path
import subprocess
import sys

from level_menu_harness import read_menu, read_toc, SHELL_MENU, CDPACK

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import level_manifest  # noqa: E402

# The roster is wflevels/aquarium-menu.manifest and nothing else (plan 2026-11-21, Phase 2).
MANIFEST = level_manifest.read()
LEVELS = list(MANIFEST.ids)
TITLES = [e.menu_name for e in MANIFEST.entries]


def test_menu_matches_current_standalones_and_manifest(tmp_path):
    output = tmp_path / 'cd.iff'
    subprocess.run([str(CDPACK), str(SHELL_MENU), '--manifest',
                    str(ROOT/'wflevels/aquarium-menu.manifest'), '-o', str(output)], check=True)
    data = output.read_bytes()
    assert data == (ROOT/'wflevels/aquarium-menu-cd.iff').read_bytes()
    assert read_menu(data) == dict(version=1, levels=len(LEVELS), title=MANIFEST.title,
                                   prompt=MANIFEST.prompt, entries=list(enumerate(TITLES)))
    toc = read_toc(data)
    # SHEL, every manifest tank, MENU, then cdpack's UI font (docs/plans/2026-10-17-settings-editor-font.md).
    assert len(toc) == len(LEVELS) + 3 and toc[0][0] == b'SHEL' and toc[-2][0] == b'MENU' and toc[-1][0] == b'UIFT'
    shell_offset, shell_size = toc[0][1:]
    assert data[shell_offset+8:shell_offset+8+shell_size] == SHELL_MENU.read_bytes()
    for (_, offset, size), level in zip(toc[1:1+len(LEVELS)], LEVELS):
        assert data[offset:offset+size] == (ROOT/'wflevels'/(level+'-standalone.iff')).read_bytes()


def test_android_uses_selector_and_apple_keeps_direct_bundle():
    # The combined Aquarium app (android/screensaver, flavor aquarium) carries the selector bundle as menu-cd.iff;
    # the standalone android/app flavor that used to is retired (docs/plans/2026-11-22-one-aquarium-apk.md).
    asset = ROOT/'android/screensaver/src/aquarium/assets/menu-cd.iff'
    assert asset.is_symlink()
    assert asset.resolve() == (ROOT/'wflevels/aquarium-menu-cd.iff').resolve()
    assert all(t[0] != b'MENU' for t in read_toc((ROOT/'wflevels/aquarium-cd.iff').read_bytes()))


def test_both_apk_builds_use_the_single_eight_tank_menu_task():
    import yaml
    tasks=yaml.safe_load((ROOT/'Taskfile.yml').read_text())['tasks']
    for name in ['build-apk','build-apk-debug']:
        # The android/app aquarium flavor is retired, so these builds no longer need the menu bundle.
        assert 'build-cd-iff-aquarium-menu' not in tasks[name]['deps']
        assert not any('five-tank' in dep for dep in tasks[name]['deps'])
    assert 'aquarium-arowana-level' in tasks['build-cd-iff-aquarium-menu']['deps']
    assert 'aquarium-plants-level' in tasks['build-cd-iff-aquarium-menu']['deps']
    assert 'build-cd-iff-aquarium-five-tanks' not in tasks


def test_menu_build_includes_new_tiger_barb_task():
    import yaml
    tasks=yaml.safe_load((ROOT/'Taskfile.yml').read_text())['tasks']
    assert 'aquarium-tiger-barbs-level' in tasks['build-cd-iff-aquarium-menu']['deps']


def test_run_aquarium_menu_task_runs_the_shipped_bundle_with_the_android_flags():
    """Phase 1 of docs/plans/2026-11-21-aquarium-menu-and-screensaver-launch.md: the desktop twin of run-smb-menu."""
    import yaml
    task = yaml.safe_load((ROOT/'Taskfile.yml').read_text())['tasks']['run-aquarium-menu']
    assert task['deps'] == ['ensure-build', 'build-cd-iff-aquarium-menu']
    script = '\n'.join(str(c) for c in task['cmds'])
    assert 'wflevels/aquarium-menu-cd.iff build-aquarium-menu/cd.iff' in script
    assert 'wflevels/aquarium-wf_args.txt' in script
    assert (ROOT/'wflevels/aquarium-wf_args.txt').is_file()
    assert 'set -euo pipefail' in script


def test_aquarium_menu_lists_every_tank_and_picks_the_third(tmp_path_factory):
    """The menu logic (host build, no display) reads the real bundle, lists the tanks in manifest order and picks one."""
    from level_menu_harness import build_host, run_host, states
    host = build_host(tmp_path_factory.mktemp('aquarium-menu-host'))
    bundle = ROOT/'wflevels/aquarium-menu-cd.iff'
    out = run_host(host, [f'bundle {bundle}', 'autopick'])
    assert out[:2] == ['TITLE WF Aquarium', 'PROMPT Choose a tank']
    assert out[2:2+len(TITLES)] == [f'ENTRY {i} {i} {t}' for i, t in enumerate(TITLES)]
    assert out[2+len(TITLES):] == [f'BUNDLE ok levels={len(LEVELS)} entries={len(TITLES)}', 'AUTO -1']
    down, a = 0x1000, 0x1
    s = states(run_host(host, [f'bundle {bundle}', 'menu 0', 'input 0 0', f'input {down:x} 16', 'input 0 32',
                               f'input {down:x} 48', 'input 0 64', f'input {a:x} 80', f'input {a:x} 200', 'input 0 216']))
    assert (s[-1]['done'], s[-1]['level']) == (1, 2), 'the third tank is TOC level 2 (Betta)'


def test_screensaver_roster_is_the_manifest_and_missing_directory_is_named(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('ss_builder', ROOT/'scripts/build-aquarium-screensaver-levels.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert list(builder.TANKS) == LEVELS
    builder.check_roster(builder.TANKS)
    import pytest
    with pytest.raises(ValueError, match='aquarium_no_such_tank'):
        builder.check_roster((*builder.TANKS, 'aquarium_no_such_tank'))
