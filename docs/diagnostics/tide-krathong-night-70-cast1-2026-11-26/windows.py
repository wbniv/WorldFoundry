"""Per-window frame statistics from a coordinator profile's run-1/presents-ns.json.
Script time t = (present - measurement_anchor_ns)/1e9 + (measurement_start_wall - host_start_wall)."""
import json, sys, statistics
d = sys.argv[1]
s = json.load(open(f"{d}/run-1/summary.json"))
r = s["runs"][0] if "runs" in s else s
tl = json.load(open(f"{d}/input-timeline.json"))
p = json.load(open(f"{d}/run-1/presents-ns.json"))
off = r["measurement_start_wall_time"] - tl["host_start_wall"]
ts = [(x - r["measurement_anchor_ns"]) / 1e9 + off for x in p]
refresh = r["refresh_ms"]
def win(a, b):
    sel = [t for t in ts if a <= t <= b]
    iv = [(y - x) * 1000 for x, y in zip(sel, sel[1:])]
    if len(iv) < 2: return None
    iv.sort()
    q = lambda f: iv[min(len(iv) - 1, int(f * len(iv)))]
    span = sel[-1] - sel[0]
    missed = 100 * sum(1 for v in iv if v > 1.5 * refresh) / len(iv)
    return dict(window=f"{a:g}-{b:g}s", frames=len(iv), fps=round(len(iv) / span, 2), p50=round(q(.5), 2),
                p95=round(q(.95), 2), p99=round(q(.99), 2), worst=round(iv[-1], 2), missed_pct=round(missed, 1))
print("offset", round(off, 3), "first", round(ts[0], 2), "last", round(ts[-1], 2))
for a, b in [(ts[0], ts[-1])] + [tuple(map(float, w.split(':'))) for w in sys.argv[2:]]:
    print(win(a, b))
