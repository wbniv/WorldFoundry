"""Check actual loaded normals for ordinary, small, and degenerate faces."""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
binary = Path(sys.argv[2])
with tempfile.TemporaryDirectory() as tmp:
    fixture = Path(tmp) / 'small-faces.iff'
    subprocess.run([sys.executable, str(root / 'docs/diagnostics/reef-triangle-normal-2026-11-06/make-loader-fixture.py'), str(fixture)], cwd=root, check=True)
    output = subprocess.run([str(binary), str(fixture)], cwd=root, check=True, capture_output=True, text=True).stdout
    normals = re.findall(r'face=(\d+) normal=\(([^,]+),([^,]+),([^,]+)\)', output)
    assert len(normals) == 4, output
    for index, x, y, z in normals:
        expected = (1.0, 1.0, 0.0, -1.0)[int(index)]
        assert abs(float(x)) < 1e-5 and abs(float(y)) < 1e-5 and abs(float(z)-expected) < 1e-5, output
