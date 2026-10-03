"""Eight Aquarium tanks in the real selector, preserving exact standalone payloads."""
from pathlib import Path
import subprocess

from level_menu_harness import read_menu, read_toc, SHELL_MENU, CDPACK

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ['aquarium', 'aquarium_blue_shrimp', 'aquarium_betta',
          'aquarium_jellyfish', 'aquarium_lionfish', 'aquarium_plants', 'aquarium_arowana', 'aquarium_tiger_barbs']
TITLES = ['Clownfish & Sea Anemone', 'Blue Shrimp', 'Calm Betta', 'Jellyfish', 'Lionfish', 'Planted Tank', 'Asian Arowana', 'Tiger Barbs']


def test_menu_matches_current_standalones_and_manifest(tmp_path):
    output = tmp_path / 'cd.iff'
    subprocess.run([str(CDPACK), str(SHELL_MENU), '--manifest',
                    str(ROOT/'wflevels/aquarium-menu.manifest'), '-o', str(output)], check=True)
    data = output.read_bytes()
    assert data == (ROOT/'wflevels/aquarium-menu-cd.iff').read_bytes()
    assert read_menu(data) == dict(version=1, levels=8, title='WF Aquarium',
                                   prompt='Choose a tank', entries=list(enumerate(TITLES)))
    toc = read_toc(data)
    assert len(toc) == 10 and toc[0][0] == b'SHEL' and toc[-1][0] == b'MENU'
    shell_offset, shell_size = toc[0][1:]
    assert data[shell_offset+8:shell_offset+8+shell_size] == SHELL_MENU.read_bytes()
    for (_, offset, size), level in zip(toc[1:9], LEVELS):
        assert data[offset:offset+size] == (ROOT/'wflevels'/(level+'-standalone.iff')).read_bytes()


def test_android_uses_selector_and_apple_keeps_direct_bundle():
    asset = ROOT/'android/app/src/aquarium/assets/cd.iff'
    assert asset.is_symlink()
    assert asset.resolve() == (ROOT/'wflevels/aquarium-menu-cd.iff').resolve()
    assert read_toc((ROOT/'wflevels/aquarium-cd.iff').read_bytes())[-1][0] != b'MENU'


def test_both_apk_builds_use_the_single_eight_tank_menu_task():
    import yaml
    tasks=yaml.safe_load((ROOT/'Taskfile.yml').read_text())['tasks']
    for name in ['build-apk','build-apk-debug']:
        assert 'build-cd-iff-aquarium-menu' in tasks[name]['deps']
        assert not any('five-tank' in dep for dep in tasks[name]['deps'])
    assert 'aquarium-arowana-level' in tasks['build-cd-iff-aquarium-menu']['deps']
    assert 'aquarium-plants-level' in tasks['build-cd-iff-aquarium-menu']['deps']
    assert 'build-cd-iff-aquarium-five-tanks' not in tasks


def test_menu_build_includes_new_tiger_barb_task():
    import yaml
    tasks=yaml.safe_load((ROOT/'Taskfile.yml').read_text())['tasks']
    assert 'aquarium-tiger-barbs-level' in tasks['build-cd-iff-aquarium-menu']['deps']
