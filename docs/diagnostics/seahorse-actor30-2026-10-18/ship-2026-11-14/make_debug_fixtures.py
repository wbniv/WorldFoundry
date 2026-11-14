#!/usr/bin/env python3
"""The Debug assertion check's levels (2026-11-14), from the shipped planted level.

Runs in the linux-test container (scripts/in-linux-container.sh), after
`cargo build --release --offline --manifest-path /src/wftools/wf_attr_edit/Cargo.toml`
(configure_level needs its catalog tool). Writes to /build/a30/:
  pair1-fixed.iff          the shipped level, saltwater, 1 pair (the device pair-1 settings)
  pair1-bug.iff            the same with only the old sh-valid line put back (patch_fix.py --reverse)
  pair1-*-eps1e-4.iff      each with device-like frame deltas, 50 ms x (1 - 1e-4) (patch_dt.py)

    python3 make_debug_fixtures.py
"""
import os
import subprocess
import sys

if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
    print(__doc__)
    sys.exit(0)
sys.path.insert(0, '/src/scripts')
from plant_settings_actor import configure_level  # noqa: E402

D = '/src/docs/diagnostics/seahorse-actor30-2026-10-18'
os.makedirs('/build/a30', exist_ok=True)
src = open('/src/wflevels/aquarium_plants-standalone.iff', 'rb').read()
lvl, receipt = configure_level(src, dict(seed=713, age=150, speed=0, greeting=True, water='saltwater', seahorses=1))
open('/build/a30/pair1-fixed.iff', 'wb').write(lvl)
print(receipt['settings'])
subprocess.check_call(['python3', D + '/patch_fix.py', '--reverse', '/build/a30/pair1-fixed.iff', '/build/a30/pair1-bug.iff'])
for v in ('fixed', 'bug'):
    subprocess.check_call(['python3', D + '/patch_dt.py', f'/build/a30/pair1-{v}.iff',
                           f'/build/a30/pair1-{v}-eps1e-4.iff', '0.0001'])
