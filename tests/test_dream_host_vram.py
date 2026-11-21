"""The Dream host must give the engine the aquarium app's VRAM page.

2026-11-09 (W4 step 12, cast1): the Aquarium Dream with "Thai Reef" asserted
``w = 1024, Display::VRAMWidth = 1024`` in gfx/rmuv.hpi and showed the TV home
screen, because dream_host.cc passed no ``--vram-width`` and the engine default
is 1024, while the reef tanks carry 1024-wide textures. The aquarium game app
runs the same levels with ``android/app/src/aquarium/assets/wf_args.txt``.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'android/screensaver/src/main/cpp/dream_host.cc'
APP_ARGS = ROOT / 'android/app/src/aquarium/assets/wf_args.txt'
VRAM = re.compile(r'--vram-(width|height|slot-width|slot-height|perm-width|perm-height)=(\d+)')


def host_argv():
    source = HOST.read_text()
    names = re.search(r'char\* argv\[\] = \{([^}]*)\};', source)
    assert names, 'dream_host.cc: argv array not found'
    entries = [n.strip() for n in names.group(1).split(',') if n.strip() != 'nullptr']
    strings = dict(re.findall(r'char (\w+)\[\] = "([^"]*)";', source))
    # The level index is formatted at run time into a sized buffer (`char arg1[12];`).
    strings.update({n: '0' for n in re.findall(r'char (\w+)\[\d+\];', source)})
    argv = [strings[n] for n in entries]
    # A level plays with every entry; kShowMenu (-1) ends argv one early, before the level.
    counts = re.search(r'const int argc = level == kShowMenu \? (\d+) : (\d+);', source)
    assert counts, 'dream_host.cc: the menu/level argc choice not found'
    assert re.search(r'argv\[argc\] = nullptr;', source)
    assert re.search(r'__argc = argc;', source) and re.search(r'HALStart\(argc, argv', source)
    return argv, int(counts.group(1)), int(counts.group(2))


def test_dream_host_vram_matches_aquarium_app():
    argv, _, _ = host_argv()
    host = dict(VRAM.findall(' '.join(argv)))
    app = dict(VRAM.findall(APP_ARGS.read_text()))
    assert host == app, f'Dream host VRAM {host} differs from the aquarium app {app}'


def test_dream_host_argument_lists_for_a_level_and_for_the_menu():
    """docs/plans/2026-11-21-tide-harbour-clock.md: nativeRun(-1) leaves out the positional level so a
    shell-menu.fth bundle shows the chooser; any other index is the last argument, every flag kept."""
    argv, menu_argc, level_argc = host_argv()
    flags = ['wf_dream', '--vram-slot-width=1024', '--vram-slot-height=1024', '--vram-perm-width=1024',
             '--vram-perm-height=1024', '--vram-width=2048', '--vram-height=2048', '--no-fps']
    assert argv == flags + ['0'], argv              # '0' stands for the formatted level index
    assert level_argc == len(argv)
    assert menu_argc == len(argv) - 1 and argv[:menu_argc] == flags


def test_dream_host_level_index_is_decimal_and_bounded_by_the_bundle():
    """The level index is the positional argument. One ASCII digit ('0' + level) turned tank 10
    (Sea Stars) into ':' = 0, so the Dream played the Clownfish tank on cast1 (2026-11-20). The upper
    bound is the APK's own cd.iff (it was the Aquarium's hard-coded 10, which TankChoice.IDS once
    pinned); an index outside it, or below -1, is logged and starts nothing."""
    host = HOST.read_text()
    assert "'0' + level" not in host and '"0" + level' not in host
    assert re.search(r'snprintf\(arg1,\s*sizeof arg1,\s*"%d",\s*int\(level\)\)', host)
    assert 'level > 10' not in host
    assert 'constexpr int kShowMenu = -1;' in host
    assert re.search(r'const int levels = bundleLevelCount\(', host)
    assert re.search(r'if \(levels <= 0 \|\| level < kShowMenu \|\| level >= levels\) \{', host)
    assert 'ANDROID_LOG_ERROR' in host
    # bundleLevelCount: the TOC less SHEL, a trailing UIFT and a MENU (cdpack's layout).
    for tag in ('"UIFT"', '"MENU"', '"SHEL"'):
        assert f'levelmenu::Tag({tag})' in host, tag


def test_menu_keeps_the_drawer_and_a_level_clears_it():
    host = HOST.read_text()
    assert 'showMenu.store(level == kShowMenu);' in host
    assert 'if (!showMenu.load() && levelmenu::Drawer()) levelmenu::SetDrawer(nullptr);' in host


def toc_level_count(path):
    """bundleLevelCount's rule, in Python, on a real cd.iff."""
    import struct
    data = Path(path).read_bytes()[:2048]
    assert data[:4] == b'GAME' and data[8:12] == b'TOC\0'
    size = struct.unpack_from('<I', data, 12)[0]
    tags = [data[o:o + 4] for o in range(16, 16 + size, 12)]
    if tags and tags[-1] == b'UIFT':
        tags.pop()
    if tags and tags[-1] == b'MENU':
        tags.pop()
    assert tags[0] == b'SHEL'
    return len(tags) - 1


def test_bundle_level_count_rule_on_the_built_bundles():
    """The Aquarium Dream bundle keeps its 0..10 range; the clocks bundle counts the manifest's clocks."""
    import pytest
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import level_manifest
    checked = 0
    for name, manifest in [('aquarium-screensaver-cd.iff', 'aquarium-menu.manifest'),
                           ('clocks-cd.iff', 'clocks-menu.manifest')]:
        bundle = ROOT / 'wflevels' / name
        if bundle.is_file():
            assert toc_level_count(bundle) == len(level_manifest.read(ROOT / 'wflevels' / manifest).ids), name
            checked += 1
    if not checked:
        pytest.skip('no Dream bundle built')


def test_aquarium_and_clocks_ranges_from_their_manifests():
    """The bound is each APK's cd.iff length, which is its manifest's level count (the Aquarium Dream
    bundle packs aquarium-menu.manifest's tanks in order; WF Clocks packs clocks-menu.manifest). So the
    Aquarium keeps exactly the old 0..10 while it has 11 tanks, and the clocks accept 0..n-1 and -1."""
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import level_manifest
    tanks = len(level_manifest.read(ROOT / 'wflevels/aquarium-menu.manifest').ids)
    assert tanks == 11, f'the Aquarium now has {tanks} tanks: its Dream range is 0..{tanks - 1}'
    clocks = level_manifest.read(ROOT / 'wflevels/clocks-menu.manifest').ids
    assert clocks and clocks[0] == 'minute_machine'
    host = HOST.read_text()
    assert re.search(r'level < kShowMenu \|\| level >= levels', host)
