#!/usr/bin/env python3
"""Report the cost of the Cuckoo Village window-box flowers from three coordinator `profile` evidence folders.

    python3 scripts/flowers-profile-report.py --off DIR --on DIR --off-again DIR [--out DIR] [--trim SECONDS] [--level-ref REV]
                                              [--apk-sha256 HEX] [--picture-off PNG --picture-on PNG] [-h]

The three folders are the evidence of the plan's profile runs on cast1, one APK, only the `Detailed flowers`
setting changed: Off (today's blocks), On (the petunia and geranium boxes), Off again. Each folder holds
`run-*/summary.json` (and, when present, `run-*/presents-ns.json`, `meminfo.txt`, `thermal.txt`) as the
coordinator's profile job writes them. Plan: docs/plans/2026-11-22-cuckoo-village-flowers.md ("Profiling before
and after" and "The report"). Writes report.md, report.json and frame-time-histogram.png into --out (default
docs/diagnostics/cuckoo-village-flowers-<date>/) and exits 0 only if the gate passes.

The gate, all of: median p50 and median p95 frame time with the field On each within 1.0 ms of the mean of the two
Off sets; fps On at least 59 and within 0.5 of the Off sets; missed refreshes up by no more than 2 points; and the two
Off sets agree with each other to within 0.5 ms (otherwise the run drifted and is thrown away: exit 2).

`--trim N` drops the first N seconds of every run and recomputes the statistics from the per-frame present times, for runs
whose first seconds are the menu and the settings form that set the field.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = dict(frame_ms=1.0, fps_floor=59.0, fps_delta=0.5, missed_points=2.0, drift_ms=0.5)
METRICS = ("fps", "p50_ms", "p90_ms", "p95_ms", "p99_ms", "worst_ms", "missed_refresh_percent")


def load_runs(folder: Path) -> list[dict]:
    runs = []
    for path in sorted(folder.glob("run-*/summary.json")):
        data = json.loads(path.read_text())
        data["_dir"] = path.parent
        runs.append(data)
    if not runs:
        raise SystemExit(f"{folder}: no run-*/summary.json (is this a profile job's evidence folder?)")
    return runs


def percentile(sorted_vals: list[float], q: float) -> float:
    """Nearest-rank percentile of an ascending list, q in 0..100."""
    return sorted_vals[min(len(sorted_vals) - 1, max(0, int(round(q / 100 * len(sorted_vals) + 0.5)) - 1))]


def trimmed(run: dict, trim: float) -> dict:
    """The run's statistics recomputed from its per-frame present times with the first `trim` seconds dropped (the menu and
    the settings form, which a scripted run cannot keep out of its window). A missed refresh is an interval over 1.5
    refresh periods, which matches the profile job's own count. Without a trim, or without present times, the job's own
    summary is used unchanged."""
    path = run["_dir"] / "presents-ns.json"
    if trim <= 0 or not path.exists():
        return run
    ts = json.loads(path.read_text())
    cut = ts[0] + trim * 1e9
    kept = [t for t in ts if t >= cut]
    if len(kept) < 31:
        raise SystemExit(f"{run['_dir']}: only {len(kept)} frames after the first {trim} s: nothing left to measure")
    iv = [(b - a) / 1e6 for a, b in zip(kept, kept[1:])]
    srt = sorted(iv)
    refresh = float(run.get("refresh_ms") or 16.683)
    out = dict(run)
    out.update(fps=len(iv) / ((kept[-1] - kept[0]) / 1e9), p50_ms=percentile(srt, 50), p90_ms=percentile(srt, 90), p95_ms=percentile(srt, 95),
               p99_ms=percentile(srt, 99), worst_ms=srt[-1], missed_refresh_percent=100.0 * sum(1 for v in iv if v > 1.5 * refresh) / len(iv))
    return out


def median(runs: list[dict], key: str) -> float:
    return statistics.median(float(r[key]) for r in runs)


def summarise(runs: list[dict], trim: float = 0.0) -> dict:
    runs = [trimmed(r, trim) for r in runs]
    out = {k: median(runs, k) for k in METRICS}
    out["runs"] = len(runs)
    out["pss_kib"] = statistics.median(v for v in (pss(r["_dir"]) for r in runs) if v is not None) if any(pss(r["_dir"]) is not None for r in runs) else None
    out["thermal_max"] = max([t for r in runs for t in thermal(r["_dir"])] or [None], key=lambda x: -1 if x is None else x)
    return out


def pss(run_dir: Path) -> int | None:
    """Total PSS in KiB from the run's meminfo (`TOTAL PSS:` or the `TOTAL` row of `dumpsys meminfo`)."""
    path = run_dir / "meminfo.txt"
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    m = re.search(r"TOTAL PSS:\s*(\d+)", text) or re.search(r"^\s*TOTAL\s+(\d+)", text, re.M)
    return int(m.group(1)) if m else None


def thermal(run_dir: Path) -> list[int]:
    path = run_dir / "thermal.txt"
    return [int(x) for x in re.findall(r"Thermal Status:\s*(\d+)", path.read_text(errors="replace"))] if path.exists() else []


def intervals_ms(runs: list[dict], trim: float = 0.0) -> list[float]:
    out: list[float] = []
    for r in runs:
        path = r["_dir"] / "presents-ns.json"
        if path.exists():
            t = json.loads(path.read_text())
            if trim > 0:
                t = [x for x in t if x >= t[0] + trim * 1e9]
            out += [(b - a) / 1e6 for a, b in zip(t, t[1:])]
    return out


def verdict(off: dict, on: dict, off2: dict) -> tuple[bool, list[tuple[bool, str]]]:
    off_mean = {k: (off[k] + off2[k]) / 2 for k in METRICS}
    rows = []
    drift = abs(off["p50_ms"] - off2["p50_ms"])
    rows.append((drift <= GATE["drift_ms"], f"the two Off sets agree: p50 {off['p50_ms']:.2f} and {off2['p50_ms']:.2f} ms differ by {drift:.2f} ms (at most {GATE['drift_ms']})"))
    for key in ("p50_ms", "p95_ms"):
        d = on[key] - off_mean[key]
        rows.append((d <= GATE["frame_ms"], f"{key.replace('_ms', '')} with the flowers: {on[key]:.2f} ms against {off_mean[key]:.2f} ms Off, difference {d:+.2f} ms (at most +{GATE['frame_ms']})"))
    rows.append((on["fps"] >= GATE["fps_floor"], f"fps with the flowers {on['fps']:.2f} (at least {GATE['fps_floor']})"))
    dfps = abs(on["fps"] - off_mean["fps"])
    rows.append((dfps <= GATE["fps_delta"], f"fps differs from Off by {dfps:.2f} (at most {GATE['fps_delta']})"))
    dm = on["missed_refresh_percent"] - off_mean["missed_refresh_percent"]
    rows.append((dm <= GATE["missed_points"], f"missed refreshes {on['missed_refresh_percent']:.1f} % against {off_mean['missed_refresh_percent']:.1f} % Off, difference {dm:+.1f} points (at most +{GATE['missed_points']})"))
    return all(ok for ok, _ in rows), rows


def level_facts(level_ref: str | None) -> list[str]:
    lines = []
    path = "wflevels/cuckoo_village-standalone.iff"
    now = (ROOT / path)
    if now.exists():
        lines.append(f"- Level file now: {now.stat().st_size:,} bytes (`{path}`).")
    if level_ref:
        try:
            before = int(subprocess.check_output(["git", "cat-file", "-s", f"{level_ref}:{path}"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL))
            lines.append(f"- Level file at `{level_ref}` (before the change): {before:,} bytes" + (f", so {now.stat().st_size - before:+,} bytes." if now.exists() else "."))
        except (subprocess.CalledProcessError, FileNotFoundError):
            lines.append(f"- Level file at `{level_ref}`: not readable here.")
    try:
        sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village_assets"))
        import flowers as fw
        full = fw.merge([fw.box_flowers(i, "full") for i in range(26)])
        lines.append(f"- Flowers: {fw.triangle_count(full):,} triangles in 26 boxes, {len(fw.MATERIALS)} flat materials, "
                     f"{len(fw.DOUBLE_SIDED)} double-sided; the removed blocks were 4,264 triangles (shown when the setting is Off).")
    except ImportError:
        pass
    return lines


def histogram(off: list[float], on: list[float], out: Path) -> bool:
    """Frame-interval histogram, Off against On on one axis, drawn with PIL (no plotting dependency)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    if not off or not on:
        return False
    lo, hi, bins = 10.0, 40.0, 60
    def counts(vals):
        c = [0] * bins
        for v in vals:
            c[min(bins - 1, max(0, int((v - lo) / (hi - lo) * bins)))] += 1
        return [x / len(vals) for x in c]
    a, b = counts(off), counts(on)
    w, h, pad = 960, 420, 50
    im = Image.new("RGB", (w, h), (24, 28, 24)); d = ImageDraw.Draw(im)
    top = max(max(a), max(b)) or 1
    bw = (w - 2 * pad) / bins
    for i in range(bins):
        x0 = pad + i * bw
        d.rectangle([x0, h - pad - (h - 2 * pad) * a[i] / top, x0 + bw / 2 - 1, h - pad], fill=(120, 150, 210))
        d.rectangle([x0 + bw / 2, h - pad - (h - 2 * pad) * b[i] / top, x0 + bw - 1, h - pad], fill=(230, 150, 80))
    for ms in range(10, 41, 5):
        x = pad + (ms - lo) / (hi - lo) * (w - 2 * pad)
        d.line([x, h - pad, x, h - pad + 5], fill=(200, 200, 190)); d.text((x - 8, h - pad + 8), f"{ms} ms", fill=(200, 200, 190))
    d.text((pad, 12), "Frame interval, share of frames: Off (blue) against On (orange)", fill=(235, 235, 225))
    im.save(out)
    return True


def table(rows: dict[str, dict]) -> str:
    head = "| Set | runs | fps | p50 ms | p90 ms | p95 ms | p99 ms | worst ms | missed % | PSS MiB | thermal |\n|---|---|---|---|---|---|---|---|---|---|---|\n"
    lines = []
    for name, s in rows.items():
        pss_mib = f"{s['pss_kib'] / 1024:.1f}" if s.get("pss_kib") else "n/a"
        lines.append(f"| {name} | {s['runs']} | {s['fps']:.2f} | {s['p50_ms']:.2f} | {s['p90_ms']:.2f} | {s['p95_ms']:.2f} | {s['p99_ms']:.2f} | "
                     f"{s['worst_ms']:.2f} | {s['missed_refresh_percent']:.1f} | {pss_mib} | {s['thermal_max'] if s['thermal_max'] is not None else 'n/a'} |")
    return head + "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--off", type=Path, required=True, help="evidence folder of the first Off profile")
    ap.add_argument("--on", type=Path, required=True, help="evidence folder of the On profile")
    ap.add_argument("--off-again", type=Path, required=True, help="evidence folder of the second Off profile")
    ap.add_argument("--out", type=Path, help="output folder (default docs/diagnostics/cuckoo-village-flowers-<date>)")
    ap.add_argument("--level-ref", help="a git revision from before the change, for the level file size")
    ap.add_argument("--apk-sha256", help="the APK that was profiled")
    ap.add_argument("--trim", type=float, default=0.0, help="seconds to drop from the start of every run (the menu and the settings form)")
    ap.add_argument("--picture-off", type=Path, help="a device capture with the field Off")
    ap.add_argument("--picture-on", type=Path, help="the same camera moment with the field On")
    args = ap.parse_args(argv)

    runs = {k: load_runs(p) for k, p in (("Off", args.off), ("On", args.on), ("Off again", args.off_again))}
    sets = {k: summarise(v, args.trim) for k, v in runs.items()}
    ok, rows = verdict(sets["Off"], sets["On"], sets["Off again"])
    drifted = not rows[0][0]
    out = args.out or ROOT / "docs/diagnostics" / f"cuckoo-village-flowers-{dt.date.today().isoformat()}"
    out.mkdir(parents=True, exist_ok=True)
    chart = histogram(intervals_ms(runs["Off"] + runs["Off again"], args.trim), intervals_ms(runs["On"], args.trim), out / "frame-time-histogram.png")

    off_mean = {k: (sets["Off"][k] + sets["Off again"][k]) / 2 for k in METRICS}
    diff = {k: sets["On"][k] - off_mean[k] for k in METRICS}
    md = ["# Cuckoo Village window boxes: before and after, profiled on one APK", "",
          f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by `scripts/flowers-profile-report.py`. Plan: "
          "[the window-box plan](../../plans/2026-11-22-cuckoo-village-flowers.md).", "",
          f"**Verdict: {'PASS' if ok else ('INVALID: the Off sets drifted' if drifted else 'FAIL')}**", ""]
    md += [f"- {'PASS' if good else 'FAIL'}: {text}" for good, text in rows]
    if args.trim > 0:
        md += ["", f"Statistics are recomputed from the per-frame present times with the first {args.trim:g} s of every run dropped (the menu and the settings form)."]
    md += ["", "## Build facts", ""] + level_facts(args.level_ref)
    if args.apk_sha256:
        md.append(f"- APK profiled: sha256 `{args.apk_sha256}`.")
    md += ["", "## Frame times (median over each set's runs)", "", table(sets),
           "### On minus the mean of the two Off sets", "",
           "| Measure | Difference | Percent |", "|---|---|---|"]
    for k in METRICS:
        pct = f"{100 * diff[k] / off_mean[k]:+.1f} %" if off_mean[k] else "n/a"
        md.append(f"| {k} | {diff[k]:+.3f} | {pct} |")
    md += ["", "## Drift", "", f"The two Off sets: p50 {sets['Off']['p50_ms']:.2f} and {sets['Off again']['p50_ms']:.2f} ms, fps {sets['Off']['fps']:.2f} and {sets['Off again']['fps']:.2f}, "
           f"thermal status at most {sets['Off']['thermal_max']} and {sets['Off again']['thermal_max']}.", ""]
    if chart:
        md += ["## Frame-time histogram", "", "![Frame intervals, Off against On](frame-time-histogram.png)", ""]
    if args.picture_off or args.picture_on:
        md += ["## Pictures", ""] + [f"- {label}: `{p}`" for label, p in (("Off", args.picture_off), ("On", args.picture_on)) if p] + [""]
    (out / "report.md").write_text("\n".join(md))
    (out / "report.json").write_text(json.dumps(dict(verdict="pass" if ok else ("invalid" if drifted else "fail"), sets=sets, difference=diff,
                                                      checks=[dict(ok=g, text=t) for g, t in rows]), indent=2) + "\n")
    print(f"report: {out / 'report.md'}")
    print("verdict:", "PASS" if ok else ("INVALID (drift)" if drifted else "FAIL"))
    return 0 if ok else (2 if drifted else 1)


if __name__ == "__main__":
    sys.exit(main())
