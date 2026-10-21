#!/usr/bin/env bash
set -euo pipefail
# Planted Tank screensaver: run the planted cd.iff bundle under the meta-loop on the
# desktop engine (inside wf-linux-test:local), timestamp every log line, sample RSS,
# and summarise the tank cycle. Plan Verification steps 4 and 5 of
# docs/plans/2026-10-21-planted-tank-screensaver.md.

usage() {
    cat <<'EOF'
Usage: planted-cycle-desktop-run.sh [--wf-game PATH] [--bundle PATH] [--seconds N]
                                    [--out DIR] [-- ENGINE_ARGS...]

Runs inside the container (repo at /src, read-only). Copies the bundle to
OUT/run/cd.iff, runs wf_game there under xvfb-run with the VRAM switches,
--frame-profile and -ppe, and stops it with `timeout N`. Core dumps are off.

  --wf-game PATH   engine binary (default /tmp/wf_game)
  --bundle PATH    cd.iff bundle (default /src/wflevels/planted-screensaver-cd.iff)
  --seconds N      wall-clock limit (default 120)
  --out DIR        output directory (default /tmp/planted-run)
  ENGINE_ARGS      extra engine switches, e.g.
                   --property="PlantedTankSettings.Growth speed=6"

Writes OUT/engine.log (each line prefixed with wall seconds since start),
OUT/rss.log (seconds, VmRSS kB) and prints a summary: Level Loaded lines,
PLANTS lines, intervals between tank starts, frame rate, rejected overrides,
asserts and crashes.
EOF
}

for a in "$@"; do
    case "$a" in -h|--help) usage; exit 0 ;; --) break ;; esac
done

WF_GAME=/tmp/wf_game
BUNDLE=/src/wflevels/planted-screensaver-cd.iff
SECONDS_LIMIT=120
OUT=/tmp/planted-run
while [[ $# -gt 0 ]]; do
    case "$1" in
        --wf-game) WF_GAME="$2"; shift 2 ;;
        --bundle) BUNDLE="$2"; shift 2 ;;
        --seconds) SECONDS_LIMIT="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --) shift; break ;;
        *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
    esac
done

ulimit -c 0
rm -rf "$OUT"; mkdir -p "$OUT/run"
cp "$BUNDLE" "$OUT/run/cd.iff"
cd "$OUT/run"

VRAM=(--vram-width=4096 --vram-height=2048 --vram-slot-width=1024 --vram-slot-height=1024
      --vram-perm-width=1024 --vram-perm-height=1024)

START=$(date +%s.%N)
export START
(
    set +e
    LD_LIBRARY_PATH=/src/engine/libs vblank_mode=0 __GL_SYNC_TO_VBLANK=0 \
        timeout --signal=TERM --kill-after=5 "$SECONDS_LIMIT" \
        xvfb-run -a -s "-screen 0 1280x720x24" \
        "$WF_GAME" "${VRAM[@]}" --frame-profile -ppe "$@" 2>&1
    echo "ENGINE-EXIT rc=$?"
) | python3 -u -c '
import os, sys, time
t0 = float(os.environ["START"])
for line in sys.stdin:
    sys.stdout.write("%8.2f %s" % (time.time() - t0, line))
' > "$OUT/engine.log" &
RUNNER=$!

# RSS sampler: find the wf_game process and sample VmRSS every second.
: > "$OUT/rss.log"
while kill -0 "$RUNNER" 2>/dev/null; do
    pid=$(pgrep -n -x wf_game || true)
    if [[ -n "$pid" && -r /proc/$pid/status ]]; then
        rss=$(awk '/^VmRSS:/ {print $2}' "/proc/$pid/status" 2>/dev/null || true)
        now=$(date +%s.%N)
        [[ -n "$rss" ]] && python3 -c "print('%.1f %s %s' % ($now - $START, '$pid', '$rss'))" >> "$OUT/rss.log"
    fi
    sleep 1
done
wait "$RUNNER" || true

python3 - "$OUT" <<'PY'
import re, sys
out = sys.argv[1]
lines = open(out + "/engine.log", errors="replace").read().splitlines()
def t(l): return float(l.split(None, 1)[0])
def body(l): return l.split(None, 1)[1] if " " in l.strip() else ""
loads = [l for l in lines if "Level Loaded" in l]
plants = [l for l in lines if "PLANTS settings-source=" in l]
print("Level Loaded lines: %d" % len(loads))
for l in loads: print("  " + l)
print("PLANTS lines: %d" % len(plants))
for l in plants: print("  " + l)
starts = [t(l) for l in plants]
gaps = [round(b - a, 2) for a, b in zip(starts, starts[1:])]
print("tank-start intervals (wall s): %s" % gaps)
fw = [l for l in lines if "frame-profile: total" in l]
print("frame-profile windows: %d" % len(fw))
wins = [l for l in lines if "frame-window:" in l]
rates = []
for w, f in zip(wins, fw):
    m = re.search(r"start-ns=(\d+) end-ns=(\d+)", w); n = re.search(r"frames=(\d+)", f)
    if m and n:
        dur = (int(m.group(2)) - int(m.group(1))) / 1e9
        rates.append((t(w), round(int(n.group(1)) / dur, 2)))
print("fps per window (wall s, fps): %s" % rates)
# Level time: Level::update caps each frame at kMaxSimDeltaSeconds (0.1 s), so below
# 10 FPS level time (TIME, DELTA_TIME) runs slower than the wall clock. Estimate it per
# tank from the 5 s profile windows, assuming frames are uniform inside a window.
wins3 = []
for w, f in zip(wins, fw):
    m = re.search(r"start-ns=(\d+) end-ns=(\d+)", w); n = re.search(r"frames=(\d+)", f)
    if m and n:
        wins3.append((t(w), (int(m.group(2)) - int(m.group(1))) / 1e9, int(n.group(1))))
for k in range(1, len(starts)):
    a, b = starts[k - 1], starts[k]
    lt = 0.0
    for end, dur, n in wins3:
        ov = max(0.0, min(end, b) - max(end - dur, a))
        if ov > 0 and n:
            lt += n * ov / dur * min(dur / n, 0.1)
    print("  tank %d->%d: wall %.2f s, estimated level time %.1f s" % (k - 1, k, b - a, lt))
for l in lines:
    m = re.search(r"level-load: index=(\d+) start-ns=(\d+) end-ns=(\d+)", l)
    if m: print("  level-load index=%s took %.3f s (at %.2f)" % (m.group(1), (int(m.group(3)) - int(m.group(2))) / 1e9, t(l)))
print("delta-too-large lines: %d" % sum(1 for l in lines if "delta too large" in l))
for key in ("PROPERTIES launch-override", "Assert", "assert", "Segmentation", "Aborted",
            "ENGINE-EXIT", "WARNING", "rror"):
    hits = [l for l in lines if key in l]
    print("%r: %d" % (key, len(hits)))
    for l in hits[:6]: print("  " + l)
rss = [l.split() for l in open(out + "/rss.log").read().splitlines()]
if rss:
    vals = [(float(a), int(c)) for a, _, c in rss]
    print("RSS samples: %d first=%s kB max=%s kB last=%s kB" % (len(vals), vals[0][1], max(v for _, v in vals), vals[-1][1]))
    for s in starts:
        near = [v for tt, v in vals if tt <= s]
        print("  RSS just before tank start at %.2f s: %s kB" % (s, near[-1] if near else "n/a"))
PY
