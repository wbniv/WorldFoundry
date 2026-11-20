"""Compose exported Forth; actor indices and collision bounds resolve at export."""
from pathlib import Path
from config import LIMIT_X, LIMIT_Y, SAND_Z, TOP, PLAYER_SPEED, ROCKS
HERE = Path(__file__).resolve().parent
CELLS = {name: 600+i for i,name in enumerate(('init','x','y','z','surface','old','roll','reach','idle','clock','dx','dy','buttons','prev','dt','neutral','auto-phase','heading','a','b','c','leader','turn','auto-step','auto-wait','lock'))}

def header():
    text = ''.join(f': st-{n} {v} ;\n' for n,v in CELLS.items())
    text += ': st-dream 0 ;\n'
    text += ''.join(f': st-{n} {v} ;\n' for n,v in {'limit-x':LIMIT_X,'limit-y':LIMIT_Y,'bottom':SAND_Z,'top':TOP,'speed':PLAYER_SPEED}.items())
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

def director(indices):
    common = player().split(': st-reset',1)[0]
    # floor is supplied by the engine core; no host-only Forth words.
    text = common + f': st-player {indices["Player"]} ; : st-visual {indices["BlueStar"]} ;\n'
    text += (HERE/'star_director.fth').read_text()
    def put(expr,mb,actor): return f' {expr} {mb} {indices[actor]} write-actor-mailbox\n'
    tick = ': st-director-tick st-pose-player\n'
    # One shared 40-cell header and five four-cell per-arm rows per actor.
    for serial,(name,kind,pos) in enumerate([('BlueStar','linckia',(0,0,SAND_Z)),*__import__('config').RESIDENTS]):
        actor=indices[name]; block=1100+serial*60
        if kind != 'cushion':
            for arm in range(5):
                ctrl=block+40+arm*4
                tick += f' 1 {ctrl} st! 0 {ctrl+1} st! st-clock st@ {arm*.17} - {ctrl+2} st!\n'
                flex=f'st-clock st@ .3 * {arm*.2} + st-sin 2 *'
                if name=='BlueStar':
                    flex += f' st-leader st@ {arm} = if 3.75 + then'
                    flex += f' st-roll st@ 0 > if 15 + then'
                    flex += f' st-reach st@ 0 > if {14 if arm<3 else -3} + then'
                if kind=='brittle':
                    flex='0'
                    tick += f' 752 st@ 0 > if 2 else 1 then {ctrl+1} st!\n'
                tick += f' {flex} {ctrl+3} st!\n'
            tick += f' {block} 5 {actor} dfrm-pose-curves drop\n'
    from config import RESIDENTS
    for serial,(name,kind,(x,y,z)) in enumerate(RESIDENTS):
        phase=f'st-clock st@ {serial*.18} +'
        if kind=='chip':
            # 20-60 second grazing pauses, straight segments between spots.
            cell=700+serial
            tick+=f' {phase} 90 st-mod dup 30 > if 30 - 30 min 30 / else drop 0 then {cell} st!\n'
            tick+=put(f'{x} {cell} st@ .45 * +','INDEXOF_X_POS',name)
        elif kind=='fromia':
            # Author-baked front-facing rock route, no runtime surface query.
            tick+=put(f'{x} {phase} .02 * st-sin .10 * +','INDEXOF_X_POS',name)
            tick+=put('0.18','INDEXOF_ROTATION_A',name)
        elif kind=='sand':
            cell=740+serial
            # Burrow cycle: 40-120 s rest; four-second emerge/sink.
            tick+=f' {phase} 100 st-mod dup 60 < if drop 0 else 60 - 4 / 1 min then {cell} st!\n'
            tick+=f' {phase} 100 st-mod 80 > if 100 {phase} 100 st-mod - 4 / 0 max 1 min {cell} st! then\n'
            # Contact is latched (the cycle above is recomputed every frame): the star
            # sinks in under a second and stays down 6 s after the player leaves.
            cont=760+serial; sink=770+serial
            tick+=f' {cont} st@ st-dt - 0 max {cont} st!\n'
            tick+=f' {x} {y} .8 st-near if 6 {cont} st! then\n'
            tick+=f' {cont} st@ 0 > if {sink} st@ st-dt 1.5 * + 1 min else {sink} st@ st-dt .25 * - 0 max then {sink} st!\n'
            tick+=f' 1 {sink} st@ - {cell} st@ min {cell} st!\n'
            tick+=put(f'{z-.12} {cell} st@ .12 * +','INDEXOF_Z_POS',name)
            tick+=put(f'{x} {phase} 100 st-mod 64 - 0 max 16 min .015 * +','INDEXOF_X_POS',name)
        elif kind=='brittle':
            # A retreat is latched; player proximity starts it within one tick.
            tick+=f' {x} {y} 2.5 st-near if 6 752 st! then\n'
            tick+=' 752 st@ st-dt - 0 max 752 st!\n'
            tick+=' 752 st@ 0 > if 751 st@ st-dt 2.43 * + 3 min else 751 st@ st-dt .12 * - 0 max then 751 st!\n'
            tick+=put(f'{x} 751 st@ -','INDEXOF_X_POS',name)
        elif kind=='cushion':
            # D3's visual puff; research flags the biological claim for review.
            tick+=put(f'1 {phase} .1 * st-sin .04 * .04 + +','INDEXOF_Z_SCALE',name)
    tick+=f' {indices["cs_wide"]} INDEXOF_CAMSHOT st! ;\nst-director-tick\n'
    return text+tick
