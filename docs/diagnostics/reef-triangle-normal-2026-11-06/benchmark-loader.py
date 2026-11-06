"""Paired fresh-process loader timing and peak RSS on identical exported meshes."""
import csv
import hashlib
import re
import subprocess
from pathlib import Path

out = Path('docs/diagnostics/reef-triangle-normal-2026-11-06')
meshes = [Path('wflevels/aquarium_thai_reef/reef_left.iff'),
          Path('wflevels/aquarium_thai_reef_anime/reef_left.iff')]
rows = []
for mesh in meshes:
    digest = hashlib.sha256(mesh.read_bytes()).hexdigest()
    for sample in range(-2, 20):
        order = ['baseline', 'candidate'] if sample % 2 == 0 else ['candidate', 'baseline']
        for variant in order:
            result = subprocess.run(['/tmp/reef-loader-' + variant, str(mesh), '--quiet'],
                                    capture_output=True, text=True, check=True)
            micros = float(re.search(r'load_us=([0-9.]+)', result.stdout).group(1))
            rss = int(re.search(r'peak_rss_kib=(\d+)', result.stdout).group(1))
            if sample >= 0:
                rows.append((str(mesh), digest, sample, variant, micros, rss))
with (out / 'loader-samples.csv').open('w', newline='') as f:
    writer = csv.writer(f, lineterminator="\n")
    writer.writerow(['mesh', 'sha256', 'sample', 'variant', 'load_us', 'peak_rss_kib'])
    writer.writerows(rows)
