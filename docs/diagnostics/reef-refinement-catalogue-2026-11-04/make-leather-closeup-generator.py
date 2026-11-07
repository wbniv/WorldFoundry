"""Make a temporary generator with a leather-coral diagnostic camera target."""
from pathlib import Path

root = Path(__file__).resolve().parents[3]
source = root/'wflevels/aquarium_thai_reef/generate.py'
text = source.read_text()
here = 'HERE = Path(__file__).resolve().parent'
choices = "choices=('duster', 'clam', 'crab', 'shrimp')"
targets = "'crab': anchor_map()['guard_crab'], 'shrimp': anchor_map()['cleaner_station']}"
assert all(text.count(value) == 1 for value in (here, choices, targets))
text = text.replace(here, f'HERE = Path({str(source.parent)!r})')
text = text.replace(choices, "choices=('duster', 'clam', 'crab', 'shrimp', 'leather')")
text = text.replace(targets, "'crab': anchor_map()['guard_crab'], "
                    "'shrimp': anchor_map()['cleaner_station'], 'leather': (4.0, -.72, 2.76)}")
out = Path('/tmp/reef-leather-close/generate.py')
out.parent.mkdir(exist_ok=True)
out.write_text(text)
print(out)
