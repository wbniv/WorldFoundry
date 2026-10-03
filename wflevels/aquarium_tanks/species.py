"""Motion state shared by standalone generators; no indices from another tank."""
from pathlib import Path
COMMON=Path(__file__).resolve().parent
STATES={name:700+i for i,name in enumerate((
    'pitch','roll','pose-pitch','pose-roll','drive','pitch-target','error','steer',
    'fx','fy','fz','cp','sp','cr','sr','lateral','vertical','cap','neutral','action',
    'local-x','cap-pos','cap-hi','cap-lo','cap-facing','turn-side','last-target','pose-drive'))}
def header(kind):
    text=''.join(f': tk-{name} {value} ;\n' for name,value in STATES.items())
    if kind=='jellyfish':
        text+=''.join(f': j-{name} {value} ;\n' for name,value in JELLY.items())
        text+=': j-cell j-base read-mailbox + read-mailbox ; : j-store j-base read-mailbox + write-mailbox ;\n'
    text+=f': tk-turn-rate {0.55 if kind=="betta" else 0.35} ; : tk-pitch-max .0833333 ;\n'
    return text
def controller(kind):
    return (COMMON/('jelly_motion.fth' if kind=='jellyfish' else 'fish_motion.fth')).read_text()

JELLY={name:730+i for i,name in enumerate(("phase","period","player-phase","pending","held","current-x","current-y","thrust","base","lag-pitch","lag-roll","contraction","player-vx","player-vy","player-vz","player-lag-pitch","player-lag-roll","dt","steps","suppress"))}
