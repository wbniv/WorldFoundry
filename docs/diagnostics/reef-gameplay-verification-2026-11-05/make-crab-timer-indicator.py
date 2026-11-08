from pathlib import Path
root=Path(__file__).resolve().parents[3];source=root/'wflevels/aquarium_thai_reef/generate.py';s=source.read_text();s=s.replace('HERE = Path(__file__).resolve().parent',f'HERE = Path({str(source.parent)!r})');s=s.replace('wide.location = (verification[0], verification[1] - 3.0, verification[2] + .4)','wide.location = (verification[0] - .1, verification[1] - 1.25, verification[2] + .3)');needle="life_tick += ';\\n'\ntick = tick.replace";assert s.count(needle)==1
injection="""# Diagnostic: move the nudibranch into view only while crab timer 643 is active.
# This marker is instrumented and is not normal reef behavior.
life_tick += (f' {crab_x-.6} INDEXOF_X_POS {indices[\"Nudibranch\"]} write-actor-mailbox '
              f' {crab_y-.35} INDEXOF_Y_POS {indices[\"Nudibranch\"]} write-actor-mailbox '
              f' 643 tk@ 0 > if {crab_z+.65} else -3 then '
              f'INDEXOF_Z_POS {indices[\"Nudibranch\"]} write-actor-mailbox\\n')
life_tick += ';\\n'
tick = tick.replace"""
Path('/tmp/reef-current-reaction-fresh/crab-timer-indicator-generator.py').write_text(s.replace(needle,injection))
