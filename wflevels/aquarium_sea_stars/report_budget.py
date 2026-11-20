#!/usr/bin/env python3
"""Fail a Sea Stars build exceeding the approved static budgets."""
import json
from pathlib import Path
from config import STATIC_TRIANGLES_MAX,STATIC_GROUPS_MAX
m=json.loads((Path(__file__).resolve().parent/'actor-map.json').read_text())
t=m['static_triangles']
print(json.dumps(dict(static_groups=len(t),static_triangles=sum(t.values()),groups=t,animated_actors=len(m['animated_triangles'])),indent=2))
assert len(t)<=STATIC_GROUPS_MAX and sum(t.values())<=STATIC_TRIANGLES_MAX
assert len(m['animated_triangles']) in (0,10)
