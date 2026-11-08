"""The reef's Forth layout (plan 2026-11-08 W5c): Fixed, or a seeded Random arrangement of the kit.

generate.py calls forth_layout() with the kit section it writes to actor-map.json and gets
back Forth source for the Director: data tables compiled into the dictionary at load (module
footprints, pivots, parks, site tables with precomputed clump orientations) and the words
that lay the reef out. Nothing here ray-casts; every surface was resolved at export (W5b).

Run-time contract (global user mailboxes; free in the original plan's allocation):
  860-863  ReefSettings poll (W5a): Layout, Rocks, Colonies, Seed
  870-873  the settings the current layout was built from; 874 = 1 once laid out
  875      the seed in use (Seed, or the one drawn for Seed 0)
  880+m    module m shown (m in kit order: left, arch, right, ledge, pillars, tall)
  886+m    module m pivot x;  892+m pivot y;  898+m heading (revolutions, 0 or 0.5)
  904+h    hero h displacement x from its Fixed pivot; 907+h displacement y (h = 0..2)
  910-999  scratch for the layout words
  200-205 / 210-218  visibility cells (W5b): modules / colony clumps
Heroes keep heading 0 (their backs are bare). Fillers take 0 or 1/2 revolution.

Geometry rules (world units; R0 report and W5b):
  * front row: the shown modules (with 4 or 5 rocks, all but the right hero), pivot y in
    [0.5, 0.6], footprints (0.85 x the rock's half width) spaced along x in [-5.6, 5.6] with
    seeded gaps of at least MIN_GAP; five rocks never fit one row of the 12-unit tank;
  * back row (4 or 5 rocks): the right hero (tall corals, no reactions), pivot y in
    [2.15, 2.2], centred behind the front fillers so its corals show above them;
  * with a hero collider's half depth of 0.75 the front faces stay at y >= -0.25, so the
    boxfish patrol lane (y about -0.5, x +-3.3, z 2.2-2.8) and its spawn stay clear;
  * everything stays inside the room box; unused modules and clumps wait parked and hidden.
"""
import math

MIN_GAP = .3
FRONT_SPAN = (-5.6, 5.6)
FRONT_Y = (.5, .6)
BACK_Y = (2.15, 2.2)
SAND_Z = .72
SITES_PER_MODULE = 16
COLONY_COUNTS = (1, 2, 3)      # clumps of each kind shown for Sparse, Normal, Dense
LINEAGE_REACH = 1.3            # a lineage member grows within this distance of its parent


def euler_for_normal(n):
    """WF Euler (a, b) in revolutions, with c = 0, that turns local +z onto n.
    Matrix34::ConstructEuler, row vectors: +z maps to (sin b cos a, -sin a, cos b cos a)."""
    nx, ny, nz = n
    a = math.asin(max(-1.0, min(1.0, -ny)))
    b = math.atan2(nx, nz)
    return (round((a / math.tau) % 1.0, 6), round((b / math.tau) % 1.0, 6))


def _num(v):
    return f'{v:.5f}'.rstrip('0').rstrip('.') if isinstance(v, float) else str(v)


def module_rows(kit_map, footprints):
    """One table row per module: fixed x, fixed y, footprint half width, half depth, park x,
    park y, park z, role (0 hero / 1 filler)."""
    rows = []
    for m in kit_map['modules']:
        hero = m['role'] == 'hero'
        base = m['pivot'] if hero else m['park']
        rows.append([base[0], base[1], footprints[m['name']], m['collider_box']['hi'][1],
                     (m['park'] or m['pivot'])[0], (m['park'] or m['pivot'])[1], (m['park'] or m['pivot'])[2],
                     0 if hero else 1])
    return rows


def site_rows(kit_map):
    rows = []
    for m in kit_map['modules']:
        sites = m['sites'][:SITES_PER_MODULE]
        assert len(sites) == SITES_PER_MODULE, m['name']
        for s in sites:
            p, n = s['p'], s['n']
            a0, b0 = euler_for_normal(n)
            a1, b1 = euler_for_normal((-n[0], -n[1], n[2]))
            rows.append([p[0], p[1], p[2], a0, b0, a1, b1])
    return rows


def _table(name, rows):
    cells = ' '.join(f'{_num(float(v))} ,j' for row in rows for v in row)
    # `here` first, then the data, then `constant`: a word header compiled between the two
    # would sit inside the table.
    return f'here {cells} constant {name}\n'


def forth_layout(kit_map, footprints, humbugs, write):
    """Forth source for the layout. `humbugs` = [(actor, authored y)] that follow the left
    hero's displacement; `write` = the generator's actor-mailbox write word name."""
    mods = kit_map['modules']
    heroes = [m for m in mods if m['role'] == 'hero']
    fillers = [m for m in mods if m['role'] == 'filler']
    nm, nh, nf = len(mods), len(heroes), len(fillers)
    assert [m['role'] for m in mods] == ['hero'] * nh + ['filler'] * nf
    clumps = kit_map['clumps']
    w = 'write-actor-mailbox'
    src = '\\ W5c reef layout (generated from actor-map.json "kit"; reef/layout.py)\n'
    src += _table('rf-mod', module_rows(kit_map, footprints))
    src += _table('rf-site', site_rows(kit_map))
    src += 'here ' + '0 ,j ' * (nm * SITES_PER_MODULE) + 'constant rf-used\n'
    src += 'here ' + ' '.join(f'{c["actor_index"]} ,j' for c in clumps) + ' constant rf-cactor\n'
    src += 'here ' + ' '.join(f'{c["cell"]} ,j' for c in clumps) + ' constant rf-ccell\n'
    # Cells are written with `,j` / `!j`, the fixed 5-byte form of zForth's variable cell
    # encoding (typed memory access is off in this build), and read back with `@`.
    src += (': rf@ ( addr i -- v ) 5 * + @ ;\n'
            ': rf! ( v addr i -- ) 5 * + !j ;\n'
            ': rf-mod@ ( m f -- v ) swap 8 * + rf-mod swap rf@ ;\n'
            ': rf-site@ ( s f -- v ) swap 7 * + rf-site swap rf@ ;\n'
            ': rf-rand ( -- u ) random 16777216 / ;\n'
            ': rf-between ( a b -- v ) over - rf-rand * + ;\n'
            ': rf-pick ( n -- k ) random swap mod ;\n'
            ': rf-show? ( m -- f ) 880 + tk@ ;\n')
    # Seed: Seed 0 draws one and keeps it while Seed stays 0; any other value repeats.
    src += (': rf-seed 863 tk@ dup 0 = if drop 875 tk@ 0 = 873 tk@ 0 <> | 874 tk@ 0 = | if random 1 max 875 tk! then 875 tk@'
            ' else dup 875 tk! then seed-random 16 0 do random drop loop ;\n')
    # (xorshift's first outputs after a small seed are nearly the same for neighbouring seeds,
    # so the layout discards 16 before drawing: seeds 11 and 12 then pick different modules.)
    # Choose the shown modules: heroes first while Rocks >= 3, then fillers.
    src += (f': rf-clear {nm} 0 do 0 i 880 + tk! loop ;\n'
            # pick k distinct modules from [first, first + count): ( k first count -- )
            ': rf-choose 912 tk! 911 tk! 910 tk!\n'
            '  910 tk@ 0 > if begin 912 tk@ rf-pick 911 tk@ + dup rf-show? if drop else 880 + 1 swap tk!'
            ' 910 tk@ 1 - 910 tk! then 910 tk@ 0 <= until then ;\n')
    src += (f': rf-modules 861 tk@ 1 max 5 min 913 tk! rf-clear\n'
            f'  913 tk@ 3 >= if {nh} 0 do 1 i 880 + tk! loop 913 tk@ 3 - {nh} {nf} rf-choose\n'
            f'  else 913 tk@ 0 {nh} rf-choose then ;\n')
    # Front row: shown heroes in a seeded order, seeded gaps, y jitter backwards only.
    # Front row: the shown modules except, with 4 or 5 rocks, the back hero; seeded order,
    # seeded gaps, y jitter backwards only. Fillers in front take heading 0 or 1/2.
    src += (f': rf-front? ( m -- f ) dup rf-show? swap 2 = 913 tk@ 4 >= & not & ;\n'
            f': rf-front 0 914 tk! 0 915 tk!\n'
            f'  {nm} 0 do i rf-front? if i 920 914 tk@ + tk! 914 tk@ 1 + 914 tk!'
            f' 915 tk@ i 2 rf-mod@ 2 * + 915 tk! then loop\n'
            # shuffle the order (Fisher-Yates over 920..)
            f'  914 tk@ 1 > if 914 tk@ 1 - 0 do 914 tk@ i - rf-pick i + 916 tk!'
            f' 920 i + tk@ 920 916 tk@ + tk@ 920 i + tk! 920 916 tk@ + tk! loop then\n'
            # free span after footprints and minimum gaps, shared by seeded weights
            f'  {FRONT_SPAN[1] - FRONT_SPAN[0]} 915 tk@ - 914 tk@ 1 - {MIN_GAP} * - 0 max 917 tk!\n'
            f'  0 918 tk! 914 tk@ 1 + 0 do rf-rand .25 + dup 930 i + tk! 918 tk@ + 918 tk! loop\n'
            f'  {FRONT_SPAN[0]} 919 tk!\n'
            f'  914 tk@ 0 do 919 tk@ 930 i + tk@ 918 tk@ / 917 tk@ * + 920 i + tk@ 2 rf-mod@ +'
            f' dup 920 i + tk@ 886 + tk! 920 i + tk@ 2 rf-mod@ + {MIN_GAP} + 919 tk!'
            f' {FRONT_Y[0]} {FRONT_Y[1]} rf-between 920 i + tk@ 892 + tk!'
            f' 920 i + tk@ 7 rf-mod@ if 2 rf-pick 2 / else 0 then 920 i + tk@ 898 + tk! loop ;\n')
    # Back row (4 or 5 rocks): the back hero behind the front fillers, so its tall corals show
    # above them; heading 0; footprint kept inside the span.
    src += (f': rf-back 913 tk@ 4 >= if 0 914 tk! 0 915 tk!\n'
            f'  {nm} {nh} do i rf-show? if 915 tk@ i 886 + tk@ + 915 tk! 914 tk@ 1 + 914 tk! then loop\n'
            f'  915 tk@ 914 tk@ / {FRONT_SPAN[0]} 2 2 rf-mod@ + max {FRONT_SPAN[1]} 2 2 rf-mod@ - min'
            f' {886 + 2} tk!\n'
            f'  {BACK_Y[0]} {BACK_Y[1]} rf-between {892 + 2} tk! 0 {898 + 2} tk! then ;\n')
    # Fixed: the reviewed W3 reef, exactly.
    src += (f': rf-fixed rf-clear {nh} 0 do 1 i 880 + tk! i 0 rf-mod@ i 886 + tk! i 1 rf-mod@ i 892 + tk!'
            f' 0 i 898 + tk! loop ;\n')
    src += (f': rf-displace {nh} 0 do i 886 + tk@ i 0 rf-mod@ - i 904 + tk! i 892 + tk@ i 1 rf-mod@ - i 907 + tk! loop ;\n')
    # Place one module: every piece and attached animal, its collider, its visibility.
    place = ''
    for index, m in enumerate(mods):
        name = f'rf-place-{index}'
        x, y, h = f'{886 + index} tk@', f'{892 + index} tk@', f'{898 + index} tk@'
        body = f': {name} {index} rf-show? if\n'
        base = m['pivot'] if m['role'] == 'hero' else m['park']
        for actor in m['piece_actors']:
            body += (f'  {x} INDEXOF_X_POS {actor} {w} {y} INDEXOF_Y_POS {actor} {w} {SAND_Z} INDEXOF_Z_POS {actor} {w}'
                     f' 0 INDEXOF_ROTATION_A {actor} {w} 0 INDEXOF_ROTATION_B {actor} {w} {h} INDEXOF_ROTATION_C {actor} {w}\n')
        c = m['collider_actor']
        body += (f'  {x} INDEXOF_X_POS {c} {w} {y} INDEXOF_Y_POS {c} {w} {SAND_Z} INDEXOF_Z_POS {c} {w}\n')
        for animal, off in m.get('attached_offsets', []):
            body += (f'  {x} {_num(float(off[0]))} + INDEXOF_X_POS {animal} {w} {y} {_num(float(off[1]))} + INDEXOF_Y_POS {animal} {w}'
                     f' {_num(float(base[2] + off[2]))} INDEXOF_Z_POS {animal} {w}\n')
        body += f'  1 {m["cell"]} tk! else 0 {m["cell"]} tk!\n'
        if m['role'] == 'hero':
            # A hidden hero's collider waits under the sand, inside the room box.
            body += (f'  {_num(float(base[0]))} INDEXOF_X_POS {c} {w} {_num(float(base[1]))} INDEXOF_Y_POS {c} {w}'
                     f' {_num(float(kit_map["park_z"]))} INDEXOF_Z_POS {c} {w}\n')
        if m['role'] == 'filler':
            px, py, pz = m['park']
            for actor in m['piece_actors'] + [c]:
                body += (f'  {_num(float(px))} INDEXOF_X_POS {actor} {w} {_num(float(py))} INDEXOF_Y_POS {actor} {w}'
                         f' {_num(float(pz))} INDEXOF_Z_POS {actor} {w}\n')
        body += '  then ;\n'
        place += body
    src += place
    src += f': rf-place-all ' + ' '.join(f'rf-place-{i}' for i in range(nm)) + ' ;\n'
    # Humbugs hover over the coral head on the left hero: carry them with it.
    src += ': rf-humbugs ' + ' '.join(f'{_num(float(yv))} 907 tk@ + INDEXOF_Y_POS {a} {w}' for a, yv in humbugs) + ' ;\n'
    # Colonies: founder-and-lineage over the shown modules' site tables (fillers first).
    ns = nm * SITES_PER_MODULE
    src += (f': rf-mod-of ( s -- m ) dup {SITES_PER_MODULE} mod - {SITES_PER_MODULE} / ;\n'
            # allowed: unused, on a shown module whose role (0 hero / 1 filler) is the one in 942
            f': rf-site-ok ( s -- f ) dup rf-used swap rf@ 0 = swap rf-mod-of dup rf-show? swap 7 rf-mod@ 942 tk@ = & & ;\n'
            # world position of site s into 944-946 (heading 1/2 turns the module-local point)
            f': rf-site-world ( s -- ) dup rf-mod-of 943 tk! dup 0 rf-site@ 944 tk! dup 1 rf-site@ 945 tk!'
            f' 2 rf-site@ {SAND_Z} + 946 tk!\n'
            f'  943 tk@ 898 + tk@ 0 > if 944 tk@ negate 944 tk! 945 tk@ negate 945 tk! then\n'
            f'  943 tk@ 886 + tk@ 944 tk@ + 944 tk! 943 tk@ 892 + tk@ 945 tk@ + 945 tk! ;\n'
            # squared distance between two sites
            f': rf-dist ( s t -- d2 ) rf-site-world 944 tk@ 947 tk! 945 tk@ 948 tk! 946 tk@ 949 tk!'
            f' rf-site-world 944 tk@ 947 tk@ - dup * 945 tk@ 948 tk@ - dup * + 946 tk@ 949 tk@ - dup * + ;\n'
            # a random allowed site (64 tries, then the first allowed one); -1 if none
            f': rf-founder ( -- s ) -1 950 tk! 64 0 do 950 tk@ 0 < if {ns} rf-pick dup rf-site-ok if 950 tk! else drop then then loop\n'
            f'  950 tk@ 0 < if {ns} 0 do 950 tk@ 0 < if i rf-site-ok if i 950 tk! then then loop then 950 tk@ ;\n'
            # the allowed site nearest to site p, within LINEAGE_REACH; -1 if none
            f': rf-near ( p -- s ) 951 tk! -1 950 tk! {LINEAGE_REACH * LINEAGE_REACH:.4f} 952 tk!\n'
            f'  {ns} 0 do i rf-site-ok if 951 tk@ i rf-dist dup 952 tk@ < if 952 tk! i 950 tk! else drop then then loop 950 tk@ ;\n'
            # put clump c on site s: position, +z onto the site normal (A, B, C in order); s < 0 parks and hides it
            f': rf-clump ( c s -- ) 954 tk! 957 tk! rf-cactor 957 tk@ rf@ 953 tk! rf-ccell 957 tk@ rf@ 958 tk!\n'
            f'  954 tk@ 0 < if -5 957 tk@ .8 * + INDEXOF_X_POS 953 tk@ {w} 2 INDEXOF_Y_POS 953 tk@ {w}'
            f' -3.5 INDEXOF_Z_POS 953 tk@ {w} 0 958 tk@ tk!\n'
            f'  else 1 rf-used 954 tk@ rf! 954 tk@ rf-site-world\n'
            f'  944 tk@ INDEXOF_X_POS 953 tk@ {w} 945 tk@ INDEXOF_Y_POS 953 tk@ {w} 946 tk@ INDEXOF_Z_POS 953 tk@ {w}\n'
            f'  954 tk@ rf-mod-of 898 + tk@ 0 > if 5 else 3 then 955 tk!\n'
            f'  954 tk@ 955 tk@ rf-site@ INDEXOF_ROTATION_A 953 tk@ {w}'
            f' 954 tk@ 955 tk@ 1 + rf-site@ INDEXOF_ROTATION_B 953 tk@ {w} 0 INDEXOF_ROTATION_C 953 tk@ {w}\n'
            f'  1 958 tk@ tk! then ;\n')
    # For each kind: a founder, then members grown from a random earlier member of the kind.
    per_kind = {k: [i for i, c in enumerate(clumps) if c['kind'] == k] for k in ('zoanthid', 'cups', 'crust')}
    src += f': rf-colonies {ns} 0 do 0 rf-used i rf! loop\n'
    # site role allowed: fillers (1) when any filler shows, else heroes (0)
    src += f'  0 942 tk! {nm} {nh} do i rf-show? if 1 942 tk! then loop\n'
    src += '  862 tk@ 0 max 2 min 1 + 956 tk!\n'
    for kind, members in per_kind.items():
        for order, c in enumerate(members):
            src += f'  {order} 956 tk@ < if '
            if order == 0:
                src += f'rf-founder dup 960 tk! {c} swap rf-clump'
            else:
                parent = f'960 {order} rf-pick + tk@'
                src += (f'{parent} dup 0 >= if rf-near else drop -1 then dup 0 < if drop rf-founder then'
                        f' dup {960 + order} tk! {c} swap rf-clump')
            src += f' else {c} -1 rf-clump then\n'
    src += '  ;\n'
    # The whole layout, and the trigger: first tick after the settings poll, then on change.
    src += (': rf-layout 860 tk@ 0 = if rf-fixed else rf-seed rf-modules rf-front rf-back then\n'
            '  rf-displace rf-place-all rf-humbugs 860 tk@ 0 = if 0 942 tk! 0 956 tk! ' +
            ' '.join(f'{i} -1 rf-clump' for i in range(len(clumps))) + ' else rf-colonies then\n'
            '  0 647 tk! 860 tk@ 870 tk! 861 tk@ 871 tk! 862 tk@ 872 tk! 863 tk@ 873 tk! 1 874 tk! ;\n'
            ': reef-layout? 874 tk@ 0 = 860 tk@ 870 tk@ <> | 861 tk@ 871 tk@ <> | 862 tk@ 872 tk@ <> |'
            ' 863 tk@ 873 tk@ <> | if rf-layout then ;\n')
    return src
