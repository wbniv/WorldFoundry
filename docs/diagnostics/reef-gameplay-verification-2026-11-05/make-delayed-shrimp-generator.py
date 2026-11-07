"""Create a diagnostic generator that moves the fish after recording begins."""
from pathlib import Path

root = Path(__file__).resolve().parents[3]
source = root/'wflevels/aquarium_thai_reef/generate.py'
text = source.read_text().replace('HERE = Path(__file__).resolve().parent',
                                  f'HERE = Path({str(source.parent)!r})')
needle = "life_tick += ';\\n'\ntick = tick.replace"
injection = """# Diagnostic only: introduce the stationary visitor after screenrecord starts.
life_tick += (f' 1112 tk@ tk-dt@ + 1112 tk! 1112 tk@ 35 > 1113 tk@ 0 = & if '
              f'{station[0]+.3} INDEXOF_X_POS tk-player write-actor-mailbox '
              f'{station[1]} INDEXOF_Y_POS tk-player write-actor-mailbox '
              f'{max(.9,station[2]+.35)} INDEXOF_Z_POS tk-player write-actor-mailbox '
              f'0 INDEXOF_XSPEED tk-player write-actor-mailbox '
              f'0 INDEXOF_YSPEED tk-player write-actor-mailbox '
              f'0 INDEXOF_ZSPEED tk-player write-actor-mailbox 1 1113 tk! then\\n')
life_tick += ';\\n'
tick = tick.replace"""
assert text.count(needle) == 1
out = Path('/tmp/reef-current-reaction-fresh/delayed-shrimp-generator.py')
out.parent.mkdir(exist_ok=True)
out.write_text(text.replace(needle, injection))
print(out)
