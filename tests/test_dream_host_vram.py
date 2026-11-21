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
    argc = re.search(r'__argc = (\d+);', source)
    start = re.search(r'HALStart\((\d+), argv', source)
    return argv, int(argc.group(1)), int(start.group(1))


def test_dream_host_vram_matches_aquarium_app():
    argv, _, _ = host_argv()
    host = dict(VRAM.findall(' '.join(argv)))
    app = dict(VRAM.findall(APP_ARGS.read_text()))
    assert host == app, f'Dream host VRAM {host} differs from the aquarium app {app}'


def test_dream_host_argc_counts_argv():
    argv, argc, start = host_argv()
    assert argc == start == len(argv), (argc, start, argv)


def test_dream_host_level_index_is_decimal_and_covers_every_tank():
    """The level index is the positional argument. One ASCII digit ('0' + level) turned tank 10
    (Sea Stars) into ':' = 0, so the Dream played the Clownfish tank on cast1 (2026-11-20)."""
    import re
    host = HOST.read_text()
    assert "'0' + level" not in host and '"0" + level' not in host
    assert re.search(r'snprintf\(arg1,\s*sizeof arg1,\s*"%d",\s*int\(level\)\)', host)
    java = (HOST.parents[1] / 'java/org/worldfoundry/screensaver/TankChoice.java').read_text()
    ids = re.search(r'IDS = \{(.*?)\};', java, re.S).group(1)
    tanks = len(re.findall(r'"aquarium[a-z_]*"', ids))
    guard = re.search(r'level < 0 \|\| level > (\d+)', host)
    assert guard and int(guard.group(1)) == tanks - 1, (guard and guard.group(1), tanks)
