#!/usr/bin/env bash
# check-fl-scan.sh: regression check for the Filelight/Dome directory scan (fl-scan).
# Until 2026-11-28 a tree larger than fl_scan's stat budget drew only the centre disk,
# because sizing the root spent the whole budget and every child then measured 0 bytes.
# This runs filelight and dome headless from /src/wftools with a tiny budget
# (WF_FL_STAT_BUDGET=400) and requires a partial scan that still lays out rings.
#
# Runs inside the linux-test container against the dev engine:
#   scripts/in-linux-container.sh scripts/build-wf-game-container.sh --dev   (once)
#   scripts/in-linux-container.sh scripts/check-fl-scan.sh                    (task check-fl-scan)
# exit: 0 both pass; 1 a level drew one segment or no scan line; 2 usage / no engine
set -euo pipefail
case "${1-}" in
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    "") ;;
    *) echo "check-fl-scan.sh: unexpected argument $1" >&2; exit 2 ;;
esac
engine="${WF_ENGINE:-/build/wf-game-dev/src/engine/wf_game}"
[ -x "$engine" ] || { echo "check-fl-scan.sh: no engine at $engine (build it with --dev)" >&2; exit 2; }
ulimit -c 0
status=0
for lvl in filelight dome; do
    out=$(cd /src/wftools && WF_FL_STAT_BUDGET=400 LD_LIBRARY_PATH=/src/engine/libs \
          xvfb-run -a "$engine" --frame-step-smoke=10 --cycles=1 \
          "-L/src/wflevels/$lvl-standalone.iff" -rate20 --no-fps 2>&1 || true)
    line=$(grep -m1 'FL: scanned' <<<"$out" || true)
    n=$(sed -n 's/.* — \([0-9]*\) segments.*/\1/p' <<<"$line")
    if [[ -n "$n" && "$n" -gt 1 && "$line" == *partial* ]]; then
        echo "PASS $lvl: $line"
    else
        echo "FAIL $lvl: ${line:-no 'FL: scanned' line}"
        status=1
    fi
done
exit "$status"
