"""Validate opt-in engine FPS probes, including a real lifecycle reset."""
import argparse
from pathlib import Path
import re

p = argparse.ArgumentParser()
p.add_argument("log", type=Path)
p.add_argument("--resume", action="store_true")
a = p.parse_args()
log = a.log.read_text(errors="replace")
assert "FPS CHECK FAIL" not in log, "runtime mailbox probe failed"
rows = [(backend, float(raw), float(script), int(epoch)) for backend, raw, script, epoch in
        re.findall(r"FPS CHECK PASS backend=(\S+) raw=([\d.]+) script=([\d.]+) generation=(\d+)", log)]
assert rows, "no runtime mailbox probes found"
backends = {r[0] for r in rows}
for backend in backends:
    samples = [r for r in rows if r[0] == backend]
    assert any(r[1] == 0 for r in samples), f"{backend}: missing baseline zero"
    assert any(r[1] > 0 for r in samples), f"{backend}: missing positive frame rate"
if a.resume:
    initial = min(r[3] for r in rows)
    resumed = [r for r in rows if r[3] > initial]
    assert any(r[1] == 0 for r in resumed), "missing lifecycle baseline reset"
    assert any(r[1] > 0 for r in resumed), "missing resumed positive sample"
print(f"PASS FPS runtime backends={','.join(sorted(backends))} samples={len(rows)} resume={a.resume}")
