"""data.py — the data sheet behind the clownfish biomechanics poster (plan Phase A).

Every number the poster prints is one row here: quantity, value, unit, status chip, source keys
and, for the game's own numbers, the code symbol it is READ FROM at build time. Nothing in an
"ours" row is typed in twice: the value is computed from `wflevels/aquarium/aquarium_constants.py`
or `wflevels/aquarium/clownfish.py`, so a changed constant changes the poster on the next build.

Status chips (the honest part):
  verified       the source's own page was opened and the number is on it (SOURCES[..]['opened'])
  unverified     widely cited or from a summary; nobody opened a source
  ours           a game tunable or our own maths, not biology
  other-species  measured in another species; used only as a hint

The chip of a row that points at a code symbol must agree with the label in that symbol's
comment (verified / unverified / ours / hint). `code_labels()` reads the comment and
`label_problems()` lists every disagreement; make_poster.py refuses to build with any, and
tests/test_poster_clownfish_biomechanics.py fails on them. A verified label is never
inherited from a neighbouring line: it has to be on the symbol's own line.

Plan: docs/plans/2026-09-30-clownfish-biomechanics-poster.md
Run `python3 data.py` to print the resolved sheet; `-h` for usage.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AQ = REPO / 'wflevels' / 'aquarium'
DATA_DATE = '2026-09-30'          # ISO; the poster prints it with non-breaking hyphens
NB = ' '                     # non-breaking space between a number and its unit

STATUSES = ('verified', 'unverified', 'ours', 'other-species')
STATUS_TEXT = {'verified': 'verified', 'unverified': 'unverified', 'ours': 'ours',
               'other-species': 'other species'}

# ── Sources ──────────────────────────────────────────────────────────────────
# `opened` = someone opened the source's own page and checked the number (the brief's list).
# URLs are only ones already in the repo (the poster plan, the aquarium plan); `url: None`
# means the repo has none, and the poster prints the citation as text with a "link missing" marker.
SOURCES = {
    'S1': dict(
        cite='Knight 2014, JEB 217:2224, summarising Nudds, John, Keen & Shiels 2014, JEB 217:2244–2249',
        title='Swimming fish stick to same Strouhal number',
        url='https://journals.biologists.com/jeb/article/217/13/2224/12210/Swimming-fish-stick-to-same-Strouhal-number',
        opened=True, backs='Strouhal window 0.2–0.4 in fish; trout 0.19–0.22'),
    'S2': dict(
        cite='Nudds, John, Keen & Shiels 2014, JEB 217:2244–2249 (the primary paper behind S1; seen only through S1)',
        title=None, url=None, opened=False, backs='the study S1 summarises'),
    'S3': dict(
        cite='Wu, Yang & Zeng 2007, JEB 210(12):2181–2191',
        title='Kinematics, hydrodynamics and energetic advantages of burst-and-coast swimming of koi carps',
        url='https://journals.biologists.com/jeb/article/210/12/2181/16867/Kinematics-hydrodynamics-and-energetic-advantages',
        opened=True, backs='burst-and-coast is a real gait (koi); burst drag ≈ 4 × coast drag; ≈ 45 % energy saved; no single burst duration'),
    'S4': dict(
        cite='Marcoux & Korsmeyer 2019, JEB 222(4)',
        title='Energetics and behavior of coral reef fishes during oscillatory swimming in a simulated wave surge',
        url='https://journals.biologists.com/jeb/article/222/4/jeb191791/20856/Energetics-and-behavior-of-coral-reef-fishes',
        opened=True, backs='A. ocellaris pectoral beat 2.4 → 4.6 /s, measured in an oscillating surge (0–29 cm/s), not steady swimming'),
    'S5': dict(
        cite='Hale, Day, Thorsen & Westneat 2006, JEB 209(19):3708–3718',
        title='Pectoral fin coordination and gait transitions in steadily swimming juvenile reef fishes',
        url='https://journals.biologists.com/jeb/article/209/19/3708/16341/Pectoral-fin-coordination-and-gait-transitions-in',
        opened=True, backs='damselfish, 12 species, no clownfish: gait switch at 1.87–4.95 BL/s (a hint only)'),
    'S6': dict(
        cite='Li, Ashraf, François, Kolomenskiy, Lechenault, Godoy-Diana & Thiria 2021, Commun. Biol. 4:40',
        title=None,
        url='https://arxiv.org/abs/2002.09176',
        opened=False, backs='fish keep the cycle constant and change the burst share (as reported, not opened)'),
    'S7': dict(
        cite='Domenici & Blake 1997, The kinematics and performance of fish fast-start swimming',
        title=None,
        url='https://www.researchgate.net/publication/13904905_The_Kinematics_and_Performance_of_Fish_Fast-Start_Swimming',
        opened=False, backs='turning angle, turning radius, C-start and S-start definitions'),
    'S8': dict(
        cite='Tu & Terzopoulos 1994, Artificial Fishes: Physics, Locomotion, Perception, Behavior',
        title=None,
        url='https://faculty.cc.gatech.edu/~turk/bio_sim/articles/fish_terzopoulos.pdf',
        opened=False, backs='the layering idea only: motor (kinematic wave) under steering (behaviour)'),
    'S9': dict(
        cite='A ≈ 0.2 L and λ ≈ L: widely cited; no primary source was identified or opened',
        title=None, url=None, opened=False, backs='tail excursion and wavelength'),
}
GAME = 'game'   # the source key of an "ours" row: the game's own code, not a paper


# ── Reading the game's code ──────────────────────────────────────────────────
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_MODS = {}


def modules():
    """(aquarium_constants, clownfish) loaded by path under private names (a second
    `aquarium_constants` on sys.path, the Phase 1 spike's, cannot shadow them)."""
    if not _MODS:
        _MODS['aquarium_constants'] = _load('_poster_aquarium_constants', AQ / 'aquarium_constants.py')
        _MODS['clownfish'] = _load('_poster_clownfish', AQ / 'clownfish.py')
    return _MODS['aquarium_constants'], _MODS['clownfish']


def harness_dt():
    """The engine tick, from run_aquarium_checks.py `DT = 0.05  # -rate20` (parsed, not imported:
    that module drives the whole engine harness)."""
    text = (AQ / 'run_aquarium_checks.py').read_text(encoding='utf-8')
    m = re.search(r'^DT\s*=\s*([0-9.]+)', text, re.M)
    if not m:
        raise RuntimeError('run_aquarium_checks.py has no `DT = ...` line')
    return float(m.group(1))


def constants():
    """Namespace of everything the rows and the diagrams read from the game."""
    C, F = modules()
    fish = F.Clownfish()
    L = C.L_M
    rig = F.RigState(fish)
    rig.speed = C.SWIM_SPEED
    k = SimpleNamespace(C=C, F=F, fish=fish, T=fish.T, L=L, V=C.SWIM_SPEED, rig=rig, dt=harness_dt())
    k.V_bl = C.SWIM_SPEED / L                                   # cruise, body lengths per second
    k.a_over_l = fish.T['fish-tail-app'] / L                    # A / L (peak-to-peak)
    k.st = fish.T['fish-strouhal']
    k.f_cruise = rig.tail_hz()                                  # the rig's own tail_hz() at cruise
    k.f_cap = fish.T['fish-tail-hz-max']
    k.tick_hz = 1.0 / k.dt
    k.dart_bl = C.DART_SPEED / L
    k.st_dart = k.f_cap * fish.T['fish-tail-app'] / C.DART_SPEED   # St the cap leaves during a dart
    k.uturn_r = C.SWIM_SPEED / (2 * math.pi * C.YAW_WMAX)       # R = V / omega at the yaw-rate cap
    return k


# ── Labels in the code's comments ────────────────────────────────────────────
_LABEL_RES = (('unverified', re.compile(r'\bunverified\b')),
              ('verified', re.compile(r'(?<!un)\bverified\b')),
              ('ours', re.compile(r'\bours\b')),
              ('other-species', re.compile(r'\bhint\b')))
INHERIT_LINES = 8     # a label-less line inherits the nearest labelled line above it in its
                      # blank-line-delimited run, at most this far up (never a `verified`)


def _labels_in(text):
    return {name for name, rx in _LABEL_RES if rx.search(text)}


def _find_line(lines, symbol):
    """Index of the line that defines `symbol`: a `NAME = ...` (or `A, B, C = ...`) assignment,
    or a `('fish-name', ...)` TUNABLES tuple."""
    if symbol.startswith('fish-'):
        needle = f"('{symbol}',"
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith(needle):
                return i
        return None
    for i, ln in enumerate(lines):
        m = re.match(r'^([A-Z_][A-Z0-9_, ]*?)\s*=[^=]', ln)
        if m and symbol in [s.strip() for s in m.group(1).split(',')]:
            return i
    return None


def code_labels(module, symbol):
    """Labels the game's own comments give `symbol`: {'labels': set, 'how': str, 'line': int}.
    'own' = on the symbol's line; 'inherited Ln' = from the nearest labelled line above, in the
    same blank-line-delimited block (never `verified`); 'none' = no label at all."""
    path = AQ / f'{module}.py'
    lines = path.read_text(encoding='utf-8').splitlines()
    i = _find_line(lines, symbol)
    if i is None:
        raise KeyError(f'{module}.py has no definition of {symbol}')
    own = _labels_in(lines[i])
    if own:
        return dict(labels=own, how='own', line=i + 1, file=path.name)
    j = i - 1
    while j >= 0 and lines[j].strip() and i - j <= INHERIT_LINES:
        got = _labels_in(lines[j]) - {'verified'}
        if got:
            return dict(labels=got, how=f'inherited L{j + 1}', line=i + 1, file=path.name)
        j -= 1
    return dict(labels=set(), how='none', line=i + 1, file=path.name)


# ── The rows ─────────────────────────────────────────────────────────────────
def _g(x, nd=4):
    """Trimmed number: 3.048, 0.5, 10, 0.0015."""
    return f'{x:.{nd}g}' if abs(x) < 1000 else f'{x:.0f}'


def _u(x, unit, nd=4):
    return f'{_g(x, nd)}{NB}{unit}'


def _row(id, group, quantity, status, sources, value=None, unit='', disp=None, symbol=None,
         factor=1.0, note='', poster_only=False):
    # factor: value == getattr(symbol) * factor (a unit change); None = derived from several symbols
    return dict(id=id, group=group, quantity=quantity, status=status, sources=list(sources),
                value=value, unit=unit, disp=disp, symbol=symbol, factor=factor, note=note,
                poster_only=poster_only)


def rows(k):
    """The data sheet. `k` is constants(): every callable/number below comes from the game's code
    unless the row is verified/unverified from a paper (then the value is the paper's)."""
    C, T = k.C, k.T
    Tn = lambda n: T[n]
    AC = 'aquarium_constants.'
    CF = 'clownfish.TUNABLES:'
    G = [GAME]
    R = []
    add = R.append

    # -- scale
    add(_row('length', 'Scale', 'Body length L', 'ours', G, C.FISH_LEN, 'in',
             f'{_u(C.FISH_LEN, "in")} ({_u(C.FISH_LEN * 2.54, "cm", 2)})', AC + 'FISH_LEN',
             note='an ocellaris as authored in the level; 0.889 m at ×10'))
    add(_row('world_scale', 'Scale', 'Level scale, space', 'ours', G, C.WORLD_SCALE, '×',
             f'×{_g(C.WORLD_SCALE)}', AC + 'WORLD_SCALE', note='space ×10, time real'))
    add(_row('cruise', 'Scale', 'Cruise speed V', 'ours', G, C.SWIM_SPEED, 'm/s', _u(C.SWIM_SPEED, 'm/s'),
             AC + 'SWIM_SPEED', note=f'= {_u(k.V_bl, "BL/s", 3)}; Phase 1: 12 in/s × scale'))
    # -- tail and Strouhal
    add(_row('st_window', 'Tail', 'Strouhal, fish', 'verified', ['S1'], (0.2, 0.4), '',
             '0.2–0.4', CF + 'fish-strouhal', factor=None, note='label reference only: the code comment on fish-strouhal labels this window verified'))
    add(_row('st_trout', 'Tail', 'Strouhal, trout', 'verified', ['S1'], (0.19, 0.22), '',
             '0.19 → 0.22', note='rainbow trout, rising with speed'))
    add(_row('st_game', 'Tail', 'Strouhal, game', 'ours', G, k.st, '', _g(k.st),
             CF + 'fish-strouhal', note='0.3, the middle of the verified window'))
    add(_row('a_over_l', 'Tail', 'Tail excursion A/L', 'unverified', ['S9'], k.a_over_l, '',
             f'{_g(k.a_over_l, 2)} peak to peak', CF + 'fish-tail-app', factor=1.0 / k.L,
             note='A = 0.2 L is widely cited; the code labels it unverified'))
    add(_row('wavelength', 'Tail', 'Wavelength λ/L', 'unverified', ['S9'], 1.0, '', '≈ 1',
             note='widely cited; the rig only swings a tail hinge and does not use it', poster_only=True))
    add(_row('envelope', 'Tail', 'Envelope A(s)', 'ours', G, None, '',
             '0.1 + 0.9 s²', note='poster illustration only: the rig has a tail hinge, not a wave; A(s) = (A/2)·(0.1 + 0.9 s²)',
             poster_only=True))
    add(_row('f_cruise', 'Tail', 'Tail beat at V', 'ours', G, k.f_cruise, 'Hz',
             _u(k.f_cruise, 'Hz', 3), 'clownfish.RigState.tail_hz', factor=None, note='f = St·U/A at V, from the rig itself'))
    add(_row('f_cap', 'Tail', 'Tail-beat cap', 'ours', G, k.f_cap, 'Hz', _u(k.f_cap, 'Hz'),
             CF + 'fish-tail-hz-max', note='kept under the Nyquist rate at 20 ticks/s'))
    add(_row('tick', 'Tail', 'Engine tick rate', 'ours', G, k.tick_hz, 'ticks/s',
             _u(k.tick_hz, 'ticks/s'), 'run_aquarium_checks.DT',
             factor=None, note='-rate20; value = 1 / DT; the Nyquist rate is half of it'))
    add(_row('st_dart', 'Tail', 'St in a dart', 'ours', G, k.st_dart, '',
             _g(k.st_dart, 2), CF + 'fish-tail-hz-max', factor=None, note='6 Hz × A / dart speed: below the fish window, knowingly'))
    add(_row('dart_speed', 'Tail', 'Dart speed', 'ours', G, C.DART_SPEED, 'm/s',
             _u(C.DART_SPEED, 'm/s'), AC + 'DART_SPEED', note=f'= {_u(k.dart_bl, "BL/s", 3)}'))
    # -- gait
    add(_row('cd_ratio', 'Gait', 'Drag burst : coast', 'verified', ['S3'], 4.0, '', '≈ 4 : 1 (koi)',
             note='Cd 0.242 against 0.060, koi carp'))
    add(_row('energy', 'Gait', 'Energy saved (koi)', 'verified', ['S3'], 45.0, '%',
             f'≈ 45{NB}%', note='nearly 45 % against steady swimming, koi carp'))
    add(_row('const_cycle', 'Gait', 'Constant cycle idea', 'unverified', ['S6'], None, '',
             'qualitative', note='cycle kept constant, burst share sets speed: as reported for Li et al. 2021; not opened'))
    add(_row('cycle', 'Gait', 'Gait cycle', 'ours', G, C.GAIT_CYCLE, 's', _u(C.GAIT_CYCLE, 's'),
             AC + 'GAIT_CYCLE', note='the code comment says "unverified; ours"'))
    add(_row('duty', 'Gait', 'Burst share', 'ours', G, C.GAIT_DUTY * 100, '%',
             _u(C.GAIT_DUTY * 100, '%'), AC + 'GAIT_DUTY', factor=100.0))
    add(_row('burst_v', 'Gait', 'Burst speed target', 'ours', G, C.BURST_SPEED, 'm/s',
             f'{_u(C.BURST_SPEED, "m/s")} ({_g(C.BURST_SPEED / C.SWIM_SPEED, 4)}{NB}V)', AC + 'BURST_SPEED',
             note='solved so the cycle mean is V'))
    add(_row('tau_a', 'Gait', 'Burst rise τ', 'ours', G, C.TAU_ACCEL, 's', _u(C.TAU_ACCEL, 's'),
             AC + 'TAU_ACCEL'))
    add(_row('tau_c', 'Gait', 'Coast decay τ', 'ours', G, C.TAU_COAST, 's', _u(C.TAU_COAST, 's'),
             AC + 'TAU_COAST'))
    add(_row('tau_g', 'Gait', 'Glide τ (released)', 'ours', G, C.TAU_GLIDE, 's', _u(C.TAU_GLIDE, 's'),
             AC + 'TAU_GLIDE'))
    # -- pectorals
    add(_row('pec_lo', 'Pectorals', 'Pectoral beat, slow', 'verified', ['S4'], Tn('fish-pec-idle-hz'),
             'Hz', _u(Tn('fish-pec-idle-hz'), 'Hz'), CF + 'fish-pec-idle-hz',
             note='A. ocellaris, beats per second in an oscillating surge, not steady swimming'))
    add(_row('pec_hi', 'Pectorals', 'Pectoral beat, fast', 'verified', ['S4'], Tn('fish-pec-hz-hi'),
             'Hz', _u(Tn('fish-pec-hz-hi'), 'Hz'), CF + 'fish-pec-hz-hi',
             note='A. ocellaris, beats per second in an oscillating surge, not steady swimming'))
    add(_row('pec_vhi', 'Pectorals', 'Speed at fast beat', 'ours', G, Tn('fish-pec-v-hi'), 'm/s',
             f'{_u(Tn("fish-pec-v-hi"), "m/s")} ({_g(Tn("fish-pec-v-hi") / C.SWIM_SPEED, 2)}{NB}V)', CF + 'fish-pec-v-hi'))
    add(_row('pec_alt', 'Pectorals', 'Alternating below', 'other-species', ['S5'], Tn('fish-pec-sync-lo'),
             'm/s', f'{_u(Tn("fish-pec-sync-lo"), "m/s")} ({_g(Tn("fish-pec-sync-lo") / C.SWIM_SPEED, 2)}{NB}V)',
             CF + 'fish-pec-sync-lo', note='game threshold set from a damselfish hint, not measured in a clownfish'))
    add(_row('pec_sync', 'Pectorals', 'Synchronous above', 'other-species', ['S5'], Tn('fish-pec-sync-hi'),
             'm/s', f'{_u(Tn("fish-pec-sync-hi"), "m/s")} ({_g(Tn("fish-pec-sync-hi") / C.SWIM_SPEED, 2)}{NB}V)',
             CF + 'fish-pec-sync-hi', note='game threshold set from a damselfish hint, not measured in a clownfish'))
    add(_row('hale', 'Pectorals', 'Damselfish switch', 'other-species', ['S5'], (1.87, 4.95),
             'BL/s', f'1.87–4.95{NB}BL/s', note='12 damselfish species, no clownfish among them'))
    # -- steering
    add(_row('yaw_wn', 'Steering', 'Yaw ω', 'ours', G, C.YAW_WN, 'rad/s', _u(C.YAW_WN, 'rad/s'), AC + 'YAW_WN'))
    add(_row('yaw_zeta', 'Steering', 'Yaw ζ', 'ours', G, C.YAW_ZETA, '', _g(C.YAW_ZETA), AC + 'YAW_ZETA'))
    add(_row('yaw_wmax', 'Steering', 'Yaw rate cap', 'ours', G, C.YAW_WMAX, 'rev/s', _u(C.YAW_WMAX, 'rev/s'),
             AC + 'YAW_WMAX', note='about 180° in 0.5 s'))
    add(_row('pitch_wn', 'Steering', 'Pitch ω', 'ours', G, C.PITCH_WN, 'rad/s', _u(C.PITCH_WN, 'rad/s'), AC + 'PITCH_WN'))
    add(_row('pitch_zeta', 'Steering', 'Pitch ζ', 'ours', G, C.PITCH_ZETA, '', _g(C.PITCH_ZETA), AC + 'PITCH_ZETA'))
    add(_row('pitch_wmax', 'Steering', 'Pitch rate cap', 'ours', G, C.PITCH_WMAX, 'rev/s', _u(C.PITCH_WMAX, 'rev/s'),
             AC + 'PITCH_WMAX', note='144°/s'))
    add(_row('pitch_max', 'Steering', 'Pitch limit', 'ours', G, C.PITCH_MAX * 360, '°',
             _u(C.PITCH_MAX * 360, '°'), AC + 'PITCH_MAX', factor=360.0, note='Up or Down alone'))
    add(_row('pitch_diag', 'Steering', 'Pitch limit, diag.', 'ours', G, C.PITCH_DIAG * 360, '°',
             _u(C.PITCH_DIAG * 360, '°'), AC + 'PITCH_DIAG', factor=360.0, note='with a sideways key held too'))
    add(_row('bank_max', 'Steering', 'Bank at full yaw', 'ours', G, C.BANK_MAX * 360, '°',
             _u(C.BANK_MAX * 360, '°'), AC + 'BANK_MAX', factor=360.0))
    add(_row('turn_dip', 'Steering', 'Burst dip in turns', 'ours', G, C.TURN_DIP * 100, '%',
             f'up to {_u(C.TURN_DIP * 100, "%")}', AC + 'TURN_DIP', factor=100.0))
    add(_row('tau_wall', 'Steering', 'Wall easing time', 'ours', G, C.TAU_WALL, 's', _u(C.TAU_WALL, 's'), AC + 'TAU_WALL'))
    add(_row('uturn', 'Steering', 'U-turn radius R', 'ours', G, k.uturn_r, 'm',
             f'≈ 0.4{NB}m ({_g(k.uturn_r, 2)})', 'aquarium_constants.SWIM_SPEED / YAW_WMAX', factor=None,
             note='a game measurement (aquarium plan, Phase 4), not biology; R = V / (2π·ω) = 0.39 m; no clownfish turn radius was found'))
    add(_row('bend', 'Steering', 'C-bend gain', 'ours', G, Tn('fish-bend'), 's', _u(Tn('fish-bend'), 's'),
             CF + 'fish-bend', note='tail yaw per unit of yaw rate'))
    add(_row('counter', 'Steering', 'Body recoil share', 'ours', G, Tn('fish-counter-yaw') * 100, '%',
             _u(Tn('fish-counter-yaw') * 100, '%'), CF + 'fish-counter-yaw', factor=100.0, note='share of tail yaw fed back into the body heading'))
    add(_row('tail_env', 'Steering', 'Tail envelope time', 'ours', G, Tn('fish-tail-env-t'), 's',
             _u(Tn('fish-tail-env-t'), 's'), CF + 'fish-tail-env-t'))
    # -- definitions
    add(_row('cstart', 'Method', 'C-start stages', 'unverified', ['S7'], None, '', 'definitions',
             note='not opened; the plan called it verified, the brief does not'))
    add(_row('layering', 'Method', 'Layering idea', 'unverified', ['S8'], None, '', 'idea only',
             note='motor under steering; not opened; used for the idea, never for a number'))
    return R


def resolve(k=None):
    """Rows with `disp` filled in, the code label for every symbol row, and the source cites."""
    k = k or constants()
    out = []
    for r in rows(k):
        r = dict(r)
        if r['disp'] is None:
            r['disp'] = 'n/a' if r['value'] is None else f"{_g(r['value'])}{NB + r['unit'] if r['unit'] else ''}"
        r['sources_cite'] = [SOURCES[s]['cite'] if s in SOURCES else 'the game\'s code' for s in r['sources']]
        r['code'] = None
        sym = r['symbol']
        if sym:
            mod, _, name = sym.partition(':') if ':' in sym else (None, None, None)
            if mod == 'clownfish.TUNABLES':
                r['code'] = code_labels('clownfish', name)
            elif sym.startswith('aquarium_constants.'):
                name = sym.split('.', 1)[1].split(' ')[0]
                r['code'] = code_labels('aquarium_constants', name)
            elif sym == 'clownfish.RigState.tail_hz':
                r['code'] = code_labels('clownfish', 'fish-strouhal')    # its inputs' labels
            elif sym.startswith('run_aquarium_checks.'):
                r['code'] = None                                        # a harness constant, no chip label
        out.append(r)
    return out


def label_problems(resolved):
    """Every row whose chip disagrees with the code comment. Empty list = data sheet and code agree.
    A row with a code symbol and NO label in the code must say so (`note` contains 'label missing')
    — and can only be `ours`."""
    bad = []
    for r in resolved:
        if r['status'] not in STATUSES:
            bad.append(f"{r['id']}: status {r['status']!r} is not one of {STATUSES}")
        if not r['sources']:
            bad.append(f"{r['id']}: no source")
        if r['status'] == 'verified':
            for s in r['sources']:
                if s not in SOURCES or not SOURCES[s]['opened']:
                    bad.append(f"{r['id']}: verified, but source {s} was not opened")
        if r['status'] == 'ours' and GAME not in r['sources']:
            bad.append(f"{r['id']}: ours, but its source is not the game's code")
        if r['status'] == 'ours' and not (r['symbol'] or r['poster_only']):
            bad.append(f"{r['id']}: ours, but neither a code symbol nor poster_only")
        c = r['code']
        if c is None:
            continue
        if c['labels']:
            if r['status'] not in c['labels']:
                bad.append(f"{r['id']}: chip {r['status']!r} but {c['file']}:{c['line']} says {sorted(c['labels'])} ({c['how']})")
        elif r['status'] != 'ours':
            bad.append(f"{r['id']}: chip {r['status']!r} but {c['file']}:{c['line']} has no label at all")
    return bad


def unlabelled(resolved):
    """Symbol rows whose definition carries no verified/unverified/ours/hint label in the code
    (reported to the orchestrator; the poster chips them `ours`)."""
    return [(r['id'], r['symbol'], f"{r['code']['file']}:{r['code']['line']}") for r in resolved
            if r['code'] is not None and not r['code']['labels']]


def to_json(resolved):
    """Machine-readable form (ASCII hyphens in dates and ids; NBSP kept only in `disp`)."""
    keep = ('id', 'group', 'quantity', 'status', 'sources', 'value', 'unit', 'disp', 'symbol', 'factor',
            'note', 'poster_only')
    rowsj = []
    for r in resolved:
        d = {k: r[k] for k in keep}
        d['value'] = list(d['value']) if isinstance(d['value'], tuple) else d['value']
        d['code_label'] = None if r['code'] is None else dict(
            labels=sorted(r['code']['labels']), how=r['code']['how'], at=f"{r['code']['file']}:{r['code']['line']}")
        rowsj.append(d)
    srcs = {k: dict(v, url=v['url']) for k, v in SOURCES.items()}
    return json.dumps(dict(date=DATA_DATE, statuses=list(STATUSES), sources=srcs, rows=rowsj),
                      ensure_ascii=False, indent=1) + '\n'


if __name__ == '__main__':
    if any(a in ('-h', '--help') for a in sys.argv[1:]):
        print(__doc__)
        sys.exit(0)
    res = resolve()
    for r in res:
        cl = '' if r['code'] is None else f"  [{','.join(sorted(r['code']['labels'])) or 'no label'}: {r['code']['how']}]"
        print(f"{r['id']:<12} {r['status']:<14} {r['disp']:<40} {r['quantity']}{cl}")
    probs = label_problems(res)
    print('\nlabel problems:', probs or 'none')
    print('symbol rows with no label in the code:', unlabelled(res))
