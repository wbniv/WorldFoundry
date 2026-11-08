"""Create a temporary close-camera level that logs crab timing to wf.log."""
from pathlib import Path

root = Path(__file__).resolve().parents[3]
source = root / 'wflevels/aquarium_thai_reef/generate.py'
text = source.read_text().replace('HERE = Path(__file__).resolve().parent',
                                  f'HERE = Path({str(source.parent)!r})')
text = text.replace('wide.location = (verification[0], verification[1] - 3.0, verification[2] + .4)',
                    'wide.location = (verification[0] - .1, verification[1] - 1.25, verification[2] + .3)')
needle = "life_tick += ';\\n'\ntick = tick.replace"
assert text.count(needle) == 1
injection = """# Diagnostic only: timestamp, timer and player position every half second.
life_tick += (f' 1112 tk@ tk-dt@ + 1112 tk! '
              f' 1114 tk@ tk-dt@ + 1114 tk! '
              f' 1114 tk@ .5 >= if 0 1114 tk! '
              f' 12345 1 sys 1112 tk@ 1 sys 643 tk@ 1 sys '
              f' INDEXOF_X_POS tk-player read-actor-mailbox 1 sys '
              f' INDEXOF_Y_POS tk-player read-actor-mailbox 1 sys '
              f' INDEXOF_Z_POS tk-player read-actor-mailbox 1 sys 10 0 sys then\\n')
life_tick += ';\\n'
tick = tick.replace"""
out = Path('/tmp/reef-current-reaction-fresh/crab-timing-generator.py')
out.parent.mkdir(exist_ok=True)
out.write_text(text.replace(needle, injection))
print(out)
