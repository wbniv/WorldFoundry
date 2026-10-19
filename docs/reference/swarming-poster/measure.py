"""measure.py: measure school.fth for the poster and write measured.json (size per word, error against couzin.py, timing).

  size    dictionary bytes after each definition (zForth's HERE), summed per word; source lines and bytes
  error   one-tick comparison with couzin.py (sigma = 0), 60 ticks, N = 11: forth_check.compare
  engine  the in-engine figures (from the bench APK on the device, entered by hand below in ENGINE) are kept from the previous file
  timing  the Chromecast HD's figure if `--device-ms a b c` is given (from device_bench.sh); otherwise the previous
          file's device figure is kept.
Usage: python3 measure.py [--device-ms MS [MS ...]] [-h]
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import forth_check as fc, zfhost

HERE = Path(__file__).resolve().parent
OUT = HERE / "measured.json"


def per_word():
    h = fc.make_host()
    assert h.eval(f"11 constant sch-n") == "ok"
    words, cur, last = [], None, h.size()
    for line in fc.SCHOOL_FTH.read_text().splitlines():
        r = h.eval(line) if line.strip() else "ok"
        assert r == "ok", (r, line)
        now = h.size()
        m = re.match(r": (\S+)", line)
        if m:
            cur = [m.group(1), 0, 0]; words.append(cur)
        if cur is not None and line.strip() and not line.lstrip().startswith("\\"):
            cur[1] += 1
            cur[2] += now - last
        last = now
    total = h.size()
    h.close()
    return [dict(name=n, lines=l, bytes=b) for n, l, b in words], total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-ms", type=float, nargs="+")
    a = ap.parse_args()
    zfhost.build()
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    words, total = per_word()
    text = fc.SCHOOL_FTH.read_text()
    code_lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("\\")]
    errs, _ = fc.compare(n=11, ticks=60)
    ep = np.array([e[0] for e in errs]); ev = np.array([e[1] for e in errs])
    dev = dict(ms=float(np.median(a.device_ms)), runs=a.device_ms, device="Chromecast HD (armeabi-v7a)", bytes_at_measure=sum(w["bytes"] for w in words)) if a.device_ms else prev.get("device")
    OUT.write_text(json.dumps(dict(
        words=words, dictionary_bytes=sum(w["bytes"] for w in words), dictionary_after_load=total, dictionary_size=65536, source_lines=len(text.splitlines()), code_lines=len(code_lines), source_bytes=len(text.encode()),
        error=dict(ticks=60, n=11, pos_median=float(np.median(ep)), pos_max=float(ep.max()), head_median=float(np.median(ev)), head_max=float(ev.max())),
        device=dev, engine=prev.get("engine")), indent=1))
    print(OUT.read_text())

main()
