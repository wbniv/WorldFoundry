"""Compose exported Forth; actor indices and collision bounds resolve at export."""
from pathlib import Path
from config import (LIMIT_X, LIMIT_Y, SAND_Z, TOP, PLAYER_SPEED, ROCKS, RESIDENTS, KIND_ORDER,
                    MAX_COUNTS, DEFAULT_COUNTS, SEED_SPREAD)
HERE = Path(__file__).resolve().parent
CELLS = {name: 600+i for i,name in enumerate(('init','x','y','z','surface','old','roll','reach','idle','clock','dx','dy','buttons','prev','dt','neutral','auto-phase','heading','a','b','c','leader','turn','auto-step','auto-wait','lock'))}

# Mailbox layout. Indices up to GLOBAL_USER_MAX (mailbox.inc) are level-global, shared by the
# player, director and settings scripts; anything above is local to the one actor that uses it,
# so every shared cell must stay at or below it. The controller cells are 600-625; then 60 cells
# of DFRM block per animated actor (the player, then each resident); then the director's tables.
GLOBAL_USER_MAX = 1900
DFRM_BASE = 640
ACTORS = len(RESIDENTS) + 1                       # the player plus the maximum population

def dfrm_block(actor_serial):
    """Start of an animated actor's DFRM block: 40 header cells + 4 per arm curve. 0 = the player."""
    return DFRM_BASE + actor_serial*60

TBASE = DFRM_BASE + ACTORS*60
SERIAL_TABLES = ('active','fade','ox','oy','tx','ty')              # one cell per resident serial
KIND_TABLES = ('chip','burrow','contact','sink','brittle-x','brittle-t')   # one cell per resident of a kind
KIND_STRIDE = max(MAX_COUNTS.values())
KBASE = TBASE + len(SERIAL_TABLES)*len(RESIDENTS)

def kind_index(serial):
    """Position of RESIDENTS[serial] among the residents of its kind (parked when >= its count)."""
    kind = RESIDENTS[serial][1]
    return sum(1 for _,k,_ in RESIDENTS[:serial] if k == kind)

def rcell(table, serial):
    if table in SERIAL_TABLES:
        return TBASE + SERIAL_TABLES.index(table)*len(RESIDENTS) + serial
    return KBASE + KIND_TABLES.index(table)*KIND_STRIDE + kind_index(serial)

SCALAR_BASE = KBASE + len(KIND_TABLES)*KIND_STRIDE
SCALARS = ('poll','speedf','glass','seed','entry','chip-n','fromia-n','sand-n','brittle-n','cushion-n',
           'rclock','b0','b1','b2','b3','valid')
SC = {n: SCALAR_BASE+i for i,n in enumerate(SCALARS)}
assert max(SC.values()) <= GLOBAL_USER_MAX, 'director cells must be level-global'
COUNT_CELL = {k: SC[k+'-n'] for k in KIND_ORDER}
# The settings fields, in the order of the OAS: the five counts then the tank fields.
FIELD_LABELS = {'chip':'Chocolate-chip stars','fromia':'Red Fromia','sand':'Sand-sifting stars',
                'brittle':'Brittle stars','cushion':'Cushion stars','speed':'Speed',
                'glass':'Glass climbing','caustics':'Caustics','seed':'Seed'}

def header():
    text = ''.join(f': st-{n} {v} ;\n' for n,v in CELLS.items())
    text += ': st-dream 0 ;\n'
    text += ''.join(f': st-{n} {v} ;\n' for n,v in {'limit-x':LIMIT_X,'limit-y':LIMIT_Y,'bottom':SAND_Z,'top':TOP}.items())
    # Speed (x.5, x1, x2 of the default) and Glass climbing come from the director's poll of
    # SeaStarsSettings. Both cells read 0 until the first poll, which means the defaults.
    text += f': st-speed-base {PLAYER_SPEED} ;\n'
    text += f': st-speedf {SC["speedf"]} read-mailbox dup 0 = if drop 1 then ;\n'
    text += ': st-speed st-speed-base st-speedf * ;\n'
    text += f': st-glass-on {SC["glass"]} read-mailbox 1 <> ;\n'
    return text

def player():
    # Clearance proxies are expanded by the player's disc, resolved before export.
    avoid = ': st-avoid-rocks st-surface st@ 0 = if\n'
    for x,y,rx,ry,_ in ROCKS:
        avoid += (f' st-x st@ {x-rx-.22:.5f} > st-x st@ {x+rx+.22:.5f} < & '
                  f'st-y st@ {y-ry-.22:.5f} > & st-y st@ {y+ry+.22:.5f} < & '
                  f'if {y-ry-.22:.5f} st-y st! then\n')
    avoid += ' then ;\n'
    core = (HERE/'sea_star_player.fth').read_text()
    pre, rest = core.split(': st-reset', 1)
    return header() + pre + (HERE/'sea_stars_screensaver.fth').read_text() + avoid + ': st-reset' + rest

def settings_words(indices, fields):
    """The director's view of SeaStarsSettings: its actor, its field indices and the poll."""
    w = f': st-settings {indices["SeaStarsSettings"]} ;\n'
    for key,label in FIELD_LABELS.items():
        w += f': st-f-{key} {fields[label]} ;\n'
    w += ': st-setting ( field fallback -- value ) swap st-settings swap property@ if nip else drop then ;\n'
    b = [SC['b0'],SC['b1'],SC['b2'],SC['b3']]
    # Seed can exceed property@'s range, so read its four bytes (least significant first) and
    # mix them into a float-safe number. All four bytes zero means Seed 0: use the per-entry
    # random value the SeaStarsSettings actor writes into the entry cell.
    w += f': st-seed-mix {b[0]} st@ {b[1]} st@ 256 * + {b[2]} st@ 977 * + {b[3]} st@ 131 * + ;\n'
    # The valid cell records whether the overlay answered (1) or the director fell back to its
    # defaults (0): the desktop check reads it to prove property@ works in the real engine.
    w += (f': st-seed@ st-settings st-f-seed property-int-bytes@\n'
          f'  if 1 {SC["valid"]} st! {b[3]} st! {b[2]} st! {b[1]} st! {b[0]} st!\n'
          f'     {b[0]} st@ {b[1]} st@ + {b[2]} st@ + {b[3]} st@ + if st-seed-mix else {SC["entry"]} st@ then\n'
          f'  else 0 {SC["valid"]} st! drop drop drop drop {SC["entry"]} st@ then ;\n')
    poll = ': st-poll\n'
    for kind in KIND_ORDER:
        poll += f' st-f-{kind} {DEFAULT_COUNTS[kind]} st-setting {COUNT_CELL[kind]} st!\n'
    poll += f' st-f-speed 1 st-setting dup 0 = if drop .5 else 2 = if 2 else 1 then then {SC["speedf"]} st!\n'
    poll += f' st-f-glass 1 st-setting 1 + {SC["glass"]} st!\n'
    poll += f' st-seed@ {SC["seed"]} st!\n'
    # Each resident's spot offset for this seed. In the first second of the level the offsets
    # are taken at once; after that they are glided to (st-glide), so a Seed edit shows as a move.
    for serial,(name,kind,_) in enumerate(RESIDENTS):
        if kind not in SEED_SPREAD: continue
        ax,ay = SEED_SPREAD[kind]
        poll += f' {SC["seed"]} st@ .0137 * {serial*1.7} + st-sin {ax} * {rcell("tx",serial)} st!\n'
        poll += f' {SC["seed"]} st@ .0191 * {serial*2.3} + st-sin {ay} * {rcell("ty",serial)} st!\n'
        poll += f' {SC["rclock"]} st@ 1 < if {rcell("tx",serial)} st@ {rcell("ox",serial)} st! {rcell("ty",serial)} st@ {rcell("oy",serial)} st! then\n'
    poll += ' ;\n'
    glide = ': st-glide ( cur target -- new ) over - dup 0 < if negate st-dt .6 * min negate else st-dt .6 * min then + ;\n'
    return w + poll + glide

def director(indices, fields):
    common = player().split(': st-reset',1)[0]
    # floor is supplied by the engine core; no host-only Forth words.
    text = common + f': st-player {indices["Player"]} ; : st-visual {indices["BlueStar"]} ;\n'
    text += (HERE/'star_director.fth').read_text()
    text += settings_words(indices, fields)
    def put(expr,mb,actor): return f' {expr} {mb} {indices[actor]} write-actor-mailbox\n'
    rclock = SC['rclock']
    tick = ': st-director-tick st-pose-player\n'
    # The resident clock runs at the Speed setting (x.5, x1, x2); the player's own speed scales
    # the same way in st-speed. The settings are polled at once, then once a second.
    tick += f' {rclock} st@ st-dt st-speedf * + {rclock} st!\n'
    tick += (f' {SC["poll"]} st@ st-dt - dup {SC["poll"]} st! 0 <= {rclock} st@ st-dt 2 * < | {SC["seed"]} st@ 0 = | '
             f'if st-poll 1 {SC["poll"]} st! then\n')

    def arms(name, kind, serial, brittle_timer=None):
        """One shared 40-cell header and five four-cell per-arm rows per actor (serial 0 = player)."""
        actor = indices[name]; block = dfrm_block(serial); out = ''
        for arm in range(5):
            ctrl = block + 40 + arm*4
            out += f' 1 {ctrl} st! 0 {ctrl+1} st! st-clock st@ {arm*.17} - {ctrl+2} st!\n'
            flex = f'st-clock st@ .3 * {arm*.2} + st-sin 2 *'
            if name == 'BlueStar':
                flex += f' st-leader st@ {arm} = if 3.75 + then'
                flex += f' st-roll st@ 0 > if 15 + then'
                flex += f' st-reach st@ 0 > if {14 if arm<3 else -3} + then'
            if kind == 'brittle':
                flex = '0'
                out += f' {brittle_timer} st@ 0 > if 2 else 1 then {ctrl+1} st!\n'
            out += f' {flex} {ctrl+3} st!\n'
        return out + f' {block} 5 {actor} dfrm-pose-curves drop\n'

    tick += arms('BlueStar', 'linckia', 0)
    for serial,(name,kind,(x,y,z)) in enumerate(RESIDENTS):
        act, fade = rcell('active',serial), rcell('fade',serial)
        ox, oy = rcell('ox',serial), rcell('oy',serial)
        want = f'{kind_index(serial)} {COUNT_CELL[kind]} st@ <'
        # Unpark: a wanted, parked resident becomes active and fades in over 2 s (at once in the
        # first second of the level, so the default population just appears as shipped).
        tick += f' {want} {act} st@ 0 = & if 1 {act} st! {rclock} st@ 1 < if 1 else 0 then {fade} st! then\n'
        # Park: an unwanted, active resident is parked.
        tick += f' {want} 0 = {act} st@ 0 <> & if 0 {act} st! then\n'
        tick += f' {act} st@ if {fade} st@ st-dt .5 * + 1 min {fade} st! then\n'
        if kind in SEED_SPREAD:
            tick += f' {ox} st@ {rcell("tx",serial)} st@ st-glide {ox} st!\n'
            tick += f' {oy} st@ {rcell("ty",serial)} st@ st-glide {oy} st!\n'
        # Parked = scale .001 (hidden). Active = the fade scale, 1 once faded in.
        scale = f'{act} st@ if {fade} st@ else .001 then'
        tick += put(scale,'INDEXOF_X_SCALE',name) + put(scale,'INDEXOF_Y_SCALE',name)
        if kind != 'cushion':
            tick += put(scale,'INDEXOF_Z_SCALE',name)
        else:
            tick += f' {act} st@ 0 = if' + put('.001','INDEXOF_Z_SCALE',name).rstrip('\n') + ' then\n'
        phase = f'{rclock} st@ {serial*.18} +'
        # Everything below runs only while the resident is active: a parked one is skipped
        # (no deform, no pose, no behaviour), so it costs only the scale write above.
        tick += f' {act} st@ if\n'
        if kind != 'cushion':
            tick += arms(name, kind, serial+1, rcell('brittle-t',serial) if kind=='brittle' else None)
        if kind=='chip':
            # 20-60 second grazing pauses, straight segments between spots.
            cell = rcell('chip',serial)
            tick += f' {phase} 90 st-mod dup 30 > if 30 - 30 min 30 / else drop 0 then {cell} st!\n'
            tick += put(f'{x} {cell} st@ .45 * + {ox} st@ +','INDEXOF_X_POS',name)
            tick += put(f'{y} {oy} st@ +','INDEXOF_Y_POS',name)
        elif kind=='fromia':
            # Author-baked front-facing rock route, no runtime surface query.
            tick += put(f'{x} {phase} .02 * st-sin .10 * + {ox} st@ +','INDEXOF_X_POS',name)
            tick += put('0.18','INDEXOF_ROTATION_A',name)
        elif kind=='sand':
            cell = rcell('burrow',serial)
            # Burrow cycle: 40-120 s rest; four-second emerge/sink.
            tick += f' {phase} 100 st-mod dup 60 < if drop 0 else 60 - 4 / 1 min then {cell} st!\n'
            tick += f' {phase} 100 st-mod 80 > if 100 {phase} 100 st-mod - 4 / 0 max 1 min {cell} st! then\n'
            # Contact is latched (the cycle above is recomputed every frame): the star
            # sinks in under a second and stays down 6 s after the player leaves.
            cont, sink = rcell('contact',serial), rcell('sink',serial)
            tick += f' {cont} st@ st-dt - 0 max {cont} st!\n'
            tick += f' {x} {ox} st@ + {y} {oy} st@ + .8 st-near if 6 {cont} st! then\n'
            tick += f' {cont} st@ 0 > if {sink} st@ st-dt 1.5 * + 1 min else {sink} st@ st-dt .25 * - 0 max then {sink} st!\n'
            tick += f' 1 {sink} st@ - {cell} st@ min {cell} st!\n'
            tick += put(f'{z-.12} {cell} st@ .12 * +','INDEXOF_Z_POS',name)
            tick += put(f'{x} {phase} 100 st-mod 64 - 0 max 16 min .015 * + {ox} st@ +','INDEXOF_X_POS',name)
            tick += put(f'{y} {oy} st@ +','INDEXOF_Y_POS',name)
        elif kind=='brittle':
            # A retreat is latched; player proximity starts it within one tick.
            bx, bt = rcell('brittle-x',serial), rcell('brittle-t',serial)
            tick += f' {x} {y} 2.5 st-near if 6 {bt} st! then\n'
            tick += f' {bt} st@ st-dt - 0 max {bt} st!\n'
            tick += f' {bt} st@ 0 > if {bx} st@ st-dt 2.43 * + 3 min else {bx} st@ st-dt .12 * - 0 max then {bx} st!\n'
            tick += put(f'{x} {bx} st@ -','INDEXOF_X_POS',name)
        elif kind=='cushion':
            # D3's visual puff; research flags the biological claim for review.
            tick += put(f'{fade} st@ 1 {phase} .1 * st-sin .04 * .04 + + *','INDEXOF_Z_SCALE',name)
        tick += ' then\n'
    tick += f' {indices["cs_wide"]} INDEXOF_CAMSHOT st! ;\nst-director-tick\n'
    return text+tick
