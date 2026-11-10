#!/usr/bin/env bash
set -euo pipefail
# Repeat: measure the bisect revision; > +0.9 ms = bad, < +0.5 ms = good, otherwise stop for a person.
W=/home/will/wf-bisect; B=/home/will/WorldFoundry-wbniv/build-docker/bisect
while :; do
    rev=$(git -C "$W" rev-parse --short=8 HEAD)
    if ! out=$("$B/measure.sh" 2>&1); then echo "$rev measure failed: $out" | tee -a "$B/bisect-log.txt"; exit 1; fi
    a=$(echo "$out" | awk '/^A /{print $NF}'); r=$(echo "$out" | awk '/^R /{print $NF}')
    if [ -z "$a" ] || [ -z "$r" ]; then echo "$rev incomplete: $out" | tee -a "$B/bisect-log.txt"; exit 1; fi
    d=$(python3 -c "print(round($r-$a,2))")
    verdict=$(python3 -c "d=$d; print('bad' if d>1.3 else 'good' if d<0.95 else 'unclear')")
    echo "$rev $verdict R=$r A=$a delta=$d" | tee -a "$B/bisect-log.txt"
    [ "$verdict" = unclear ] && exit 2
    res=$(git -C "$W" bisect "$verdict" 2>&1)
    echo "$res" | head -2 | tee -a "$B/bisect-log.txt"
    echo "$res" | grep -q "is the first bad commit" && exit 0
done
