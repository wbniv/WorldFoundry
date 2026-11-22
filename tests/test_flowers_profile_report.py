"""scripts/flowers-profile-report.py: medians, the On-minus-Off difference, the drift check and the gate's exit code.

Plan docs/plans/2026-11-22-cuckoo-village-flowers.md ("The gate"). The evidence folders here are synthetic but have the
layout of the coordinator's profile job: run-N/summary.json, presents-ns.json, meminfo.txt, thermal.txt.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("flowers_profile_report", ROOT / "scripts/flowers-profile-report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def make(folder: Path, p50, p95, fps=59.94, missed=0.0, runs=3, pss_kib=250_000, thermal=0, frames=300):
    for n in range(1, runs + 1):
        run = folder / f"run-{n}"
        run.mkdir(parents=True)
        (run / "summary.json").write_text(json.dumps(dict(
            run=n, frames=frames, fps=fps + 0.01 * n, p50_ms=p50 + 0.01 * n, p90_ms=p95 - 1, p95_ms=p95 + 0.01 * n, p99_ms=p95 + 2,
            worst_ms=p95 + 8, missed_refresh_percent=missed, refresh_ms=16.68)))
        t, ts = 1_000_000_000, []
        for i in range(frames):
            ts.append(t); t += int(p50 * 1e6)
        (run / "presents-ns.json").write_text(json.dumps(ts))
        (run / "meminfo.txt").write_text(f"** MEMINFO **\n           TOTAL PSS:   {pss_kib}            TOTAL RSS:   300000\n")
        (run / "thermal.txt").write_text(f"Thermal Status: {thermal}\n")
    return folder


def run(tmp_path, off, on, off2, **kw):
    dirs = [make(tmp_path / n, *args) if isinstance(args, tuple) else make(tmp_path / n, **args)
            for n, args in (("off", off), ("on", on), ("off2", off2))]
    out = tmp_path / "out"
    code = report.main(["--off", str(dirs[0]), "--on", str(dirs[1]), "--off-again", str(dirs[2]), "--out", str(out)])
    return code, out


def test_a_cheap_change_passes_and_the_report_is_written(tmp_path):
    code, out = run(tmp_path, (16.7, 18.0), (17.0, 18.6), (16.8, 18.1))
    assert code == 0
    md = (out / "report.md").read_text()
    assert "**Verdict: PASS**" in md and "Frame times" in md and "On minus the mean" in md and "Drift" in md
    data = json.loads((out / "report.json").read_text())
    assert data["verdict"] == "pass" and data["sets"]["On"]["runs"] == 3
    assert abs(data["difference"]["p50_ms"] - (17.02 - 16.77)) < 0.05          # medians of the three runs, On minus the mean of Off
    assert (out / "frame-time-histogram.png").exists()
    assert "250.0" not in md and "244.1" in md                                  # PSS 250000 KiB shown in MiB


def test_a_costly_change_fails_the_gate_on_the_frame_time(tmp_path):
    code, out = run(tmp_path, (16.7, 18.0), (18.2, 20.5), (16.8, 18.1))
    assert code == 1
    assert "**Verdict: FAIL**" in (out / "report.md").read_text()
    assert json.loads((out / "report.json").read_text())["verdict"] == "fail"


def test_dropping_below_59_fps_or_missing_refreshes_fails(tmp_path):
    code, _ = run(tmp_path / "a", (16.7, 18.0), dict(p50=16.8, p95=18.0, fps=58.0), (16.7, 18.0))
    assert code == 1
    code, _ = run(tmp_path / "b", (16.7, 18.0), dict(p50=16.8, p95=18.0, missed=4.5), (16.7, 18.0))
    assert code == 1


def test_off_sets_that_disagree_are_thrown_away_as_drift(tmp_path):
    code, out = run(tmp_path, (16.7, 18.0), (16.9, 18.2), (17.6, 19.0))
    assert code == 2
    md = (out / "report.md").read_text()
    assert "INVALID" in md and json.loads((out / "report.json").read_text())["verdict"] == "invalid"


def test_a_folder_without_runs_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    try:
        report.load_runs(tmp_path / "empty")
    except SystemExit as e:
        assert "no run-*/summary.json" in str(e)
    else:
        raise AssertionError("an empty evidence folder was accepted")


def test_pss_and_thermal_parsers_read_the_dumpsys_shapes(tmp_path):
    (tmp_path / "meminfo.txt").write_text("        TOTAL   123456    111      99\n")
    assert report.pss(tmp_path) == 123456
    (tmp_path / "thermal.txt").write_text("Thermal Status: 0\n...\nThermal Status: 2\n")
    assert report.thermal(tmp_path) == [0, 2]


def test_trim_drops_the_menu_period_and_recomputes_from_the_present_times(tmp_path):
    """A run whose first 20 s are slow (the menu and form) passes once those seconds are trimmed, and fails without the trim."""
    def slow_start(folder, steady_ms):
        for n in (1, 2, 3):
            run = folder / f"run-{n}"
            run.mkdir(parents=True)
            t, ts = 1_000_000_000, []
            for _ in range(60):                       # 20 s of 333 ms frames: the menu
                ts.append(t); t += int(333e6)
            for _ in range(900):                      # then 60 fps-ish frames
                ts.append(t); t += int(steady_ms * 1e6)
            (run / "presents-ns.json").write_text(json.dumps(ts))
            (run / "summary.json").write_text(json.dumps(dict(
                run=n, fps=20.0, p50_ms=60.0, p90_ms=333.0, p95_ms=333.0, p99_ms=333.0, worst_ms=333.0, missed_refresh_percent=40.0, refresh_ms=16.683)))
        return folder
    dirs = [slow_start(tmp_path / n, ms) for n, ms in (("off", 16.7), ("on", 16.75), ("off2", 16.7))]
    base = ["--off", str(dirs[0]), "--on", str(dirs[1]), "--off-again", str(dirs[2])]
    assert report.main(base + ["--out", str(tmp_path / "raw")]) == 1             # untrimmed, the job's own numbers are the menu's: 20 fps fails
    code = report.main(base + ["--out", str(tmp_path / "trimmed"), "--trim", "20"])
    assert code == 0
    data = json.loads((tmp_path / "trimmed/report.json").read_text())
    assert abs(data["sets"]["On"]["p50_ms"] - 16.75) < 0.2 and abs(data["sets"]["Off"]["p50_ms"] - 16.7) < 0.2
    assert data["sets"]["On"]["missed_refresh_percent"] == 0.0
    assert "first 20 s of every run dropped" in (tmp_path / "trimmed/report.md").read_text()


def test_trim_refuses_a_run_with_nothing_left(tmp_path):
    run = tmp_path / "run-1"
    run.mkdir()
    (run / "presents-ns.json").write_text(json.dumps([i * 16_700_000 for i in range(40)]))
    (run / "summary.json").write_text(json.dumps(dict(fps=60, p50_ms=16.7, p90_ms=16.7, p95_ms=16.7, p99_ms=16.7, worst_ms=16.7, missed_refresh_percent=0)))
    runs = report.load_runs(tmp_path)
    try:
        report.trimmed(runs[0], 5.0)
    except SystemExit as e:
        assert "nothing left to measure" in str(e)
    else:
        raise AssertionError("an empty trimmed run was accepted")
