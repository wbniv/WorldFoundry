#!/usr/bin/env bash
set -euo pipefail
# usage: measure.sh — build the bisect worktree's current revision, run [A R R A A R] on cast1, print the medians.
W=/home/will/wf-bisect; B=/home/will/WorldFoundry-wbniv/build-docker/bisect; ROOT=/home/will/WorldFoundry-wbniv
rev=$(git -C "$W" rev-parse --short=8 HEAD)
apk=$("$B/step2.sh" "$rev")
python3 - "$apk" "$rev" <<'PY'
import json, sys
B='/home/will/WorldFoundry-wbniv/build-docker/bisect'; R='/home/will/WorldFoundry-wbniv/build-docker/show/aquarium-show.apk'
apk, rev = sys.argv[1], sys.argv[2]
seq = [('A1', f'{B}/A-9f97.apk'), ('R1', apk), ('R2', apk), ('A2', f'{B}/A-9f97.apk'), ('A3', f'{B}/A-9f97.apk'), ('R3', apk)]
json.dump({'workflow': 'variant-benchmark', 'app': 'aquarium', 'scene': 'planted-tank', 'apk': R, 'restore_apk': R,
           'variants': [{'label': l, 'apk': a, 'runs': 1, 'warmup': 15} for l, a in seq], 'duration': 60},
          open(f'{B}/recipe-{rev}.json', 'w'), indent=1)
PY
cd "$ROOT"
job=$(WF_CC_DEVICE=chromecast-test-01 WF_CC_ASYNC=true WF_CC_RECIPE=$B/recipe-$rev.json WF_CC_WORKFLOW=variant-benchmark \
      timeout 120 task chromecast:submit 2>&1 | grep -oE "J-[0-9a-f]{12}" | head -1)
echo "$rev job $job"
while :; do
    s=$(WF_CC_JOB=$job timeout 30 python3 scripts/chromecast.py task status 2>&1 | grep -m1 '"state"' || true)
    case "$s" in *queued*|*running*) sleep 30;; *) break;; esac
done
rm -rf "$B/ev-$rev"; WF_CC_JOB=$job WF_CC_OUT=$B/ev-$rev timeout 300 task chromecast:evidence >/dev/null 2>&1 || true
python3 "$B/summ.py" "$B/ev-$rev"
