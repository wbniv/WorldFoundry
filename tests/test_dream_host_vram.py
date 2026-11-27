"""The Dream host must give the engine the aquarium app's VRAM page.

2026-11-09 (W4 step 12, cast1): the Aquarium Dream with "Thai Reef" asserted
``w = 1024, Display::VRAMWidth = 1024`` in gfx/rmuv.hpi and showed the TV home
screen, because dream_host.cc passed no ``--vram-width`` and the engine default
is 1024, while the reef tanks carry 1024-wide textures. The aquarium game app
runs the same levels with ``wflevels/aquarium-wf_args.txt``.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'android/screensaver/src/main/cpp/dream_host.cc'
APP_ARGS = ROOT / 'wflevels/aquarium-wf_args.txt'
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
    # A level plays with every entry; the menu (kMenuLevel, -1) ends argv one early, before the level.
    counts = re.search(r'int argc = menu \? (\d+) : (\d+);', source)
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
    assert 'constexpr int kMenuLevel = -1;' in host
    assert re.search(r'const int levels = bundleLevelCount\(', host)
    assert re.search(r'if \(levels <= 0 \|\| level < kMenuLevel \|\| level >= levels\) \{', host)
    assert 'ANDROID_LOG_ERROR' in host
    # bundleLevelCount: the TOC less SHEL, a trailing UIFT and a MENU (cdpack's layout).
    for tag in ('"UIFT"', '"MENU"', '"SHEL"'):
        assert f'levelmenu::Tag({tag})' in host, tag


def test_menu_keeps_the_drawer_and_a_level_clears_it():
    host = HOST.read_text()
    assert 'menuMode.store(menu);' in host
    # The menu, in either pack, keeps the drawer; every level clears it.
    assert re.search(r'else if \(levelmenu::Drawer\(\)\) \{\s*levelmenu::SetDrawer\(nullptr\);', host)


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
    """The Aquarium Dream bundle keeps its 0..11 range; the clocks bundle counts the manifest's clocks."""
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
    Aquarium accepts exactly 0..11 with its 12 tanks (the Discus tank, 2026-11-22, appended as 11),
    and the clocks accept 0..n-1 and -1."""
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import level_manifest
    tanks = len(level_manifest.read(ROOT / 'wflevels/aquarium-menu.manifest').ids)
    assert tanks == 12, f'the Aquarium now has {tanks} tanks: its Dream range is 0..{tanks - 1}'
    clocks = level_manifest.read(ROOT / 'wflevels/clocks-menu.manifest').ids
    assert clocks and clocks[0] == 'minute_machine'
    host = HOST.read_text()
    assert re.search(r'level < kMenuLevel \|\| level >= levels', host)


CLOCKS_ARGS = ROOT / 'android/screensaver/src/clocks/assets/wf_args.txt'


def test_clocks_flavor_slot_fits_every_texture_page_in_its_bundle():
    """2026-11-21, cast1: Cuckoo Village's hillside art packs its textures into a 2048 x 1024 room page
    (wflevels/cuckoo_village/textile.flags: PAGEX=2048), and the Dream host's default 1024 x 1024 slot
    aborted the engine with "LoadTexture: 2048x1024 texture does not fit its 1024x1024 VRAM slot". The
    host reads the flavor's assets/wf_args.txt for the VRAM sizes (dream_host.cc: vramOverride), and the
    clocks flavor must ship a slot at least as wide as the widest page of a level in its roster."""
    flags = dict(re.findall(r'(\w+)=(\d+)', (ROOT / 'wflevels/cuckoo_village/textile.flags').read_text()))
    page_width = int(flags['PAGEX'])
    args = dict(VRAM.findall(CLOCKS_ARGS.read_text()))
    assert int(args['slot-width']) >= page_width, f'clocks slot {args} narrower than the {page_width} page'
    # The override must be wired: the host reads the file and replaces argv[1..6], and every other flavor
    # (no wf_args.txt) keeps the pinned defaults the tests above check.
    host = HOST.read_text()
    assert 'AAssetManager_open(assets, "wf_args.txt"' in host
    assert re.search(r'argv\[1 \+ i\] = overrides\[i\];', host)
    other = [p for p in (ROOT / 'android/screensaver/src').glob('*/assets/wf_args.txt') if p.parent.parent.name != 'clocks']
    assert other == [], f'a flavor other than clocks overrides the VRAM sizes: {other}'


def test_frame_profile_line_goes_before_the_level_and_no_flavor_ships_it():
    """2026-11-27 (candle flicker, verification step 0): the seahorse benchmark measures variant APKs whose only change is their assets,
    with `--frame-profile` added to assets/wf_args.txt. The Dream host read only the six VRAM lines of that file, so the Clocks flavor
    silently ran without the profile and no frame-profile lines reached wf.log. The host now passes a `--frame-profile` line through,
    as the first flag (the level index, a positional argument, stays last); no shipped flavor may carry it."""
    source = HOST.read_text()
    block = source[source.index('char frameProfile[] = "--frame-profile";'):source.index('__argc = argc;')]
    assert 'vramOverride(frameProfile' in block, 'the host does not look for --frame-profile in wf_args.txt'
    assert 'argv[1] = frameProfile;' in block and 'argv[++argc] = nullptr;' in block
    argv_decl = re.search(r'char\* argv\[\] = \{([^}]*)\};', source).group(1)
    assert argv_decl.replace(' ', '').endswith('nullptr,nullptr'), 'argv needs a spare slot for the inserted flag'
    for args in sorted((ROOT / 'android/screensaver/src').glob('*/assets/wf_args.txt')):
        assert '--frame-profile' not in args.read_text(), f'{args} ships --frame-profile'
