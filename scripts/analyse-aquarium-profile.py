#!/usr/bin/env python3
"""Analyse saved SurfaceFlinger captures, excluding screenshot gaps and warmup."""
import argparse
import gzip
import json
from pathlib import Path
import re
import statistics as S

def percentile(values, p):
    values = sorted(values)
    return values[int((len(values)-1)*p)] if values else None

def stats(intervals, refresh):
    return {'frames': len(intervals), 'fps': 1000/S.mean(intervals),
            **{f'p{int(p*100)}_ms': percentile(intervals, p) for p in [.5,.9,.95,.99]},
            'missed_refresh_percent': 100*sum(x>refresh*1.5 for x in intervals)/len(intervals)}

def analyse(work):
    samples = json.loads((work/'samples.json').read_text())
    segments = json.loads((work/'segments.json').read_text())
    presents = set(); offsets = []; refresh = None
    for sample in samples:
        rows = sample['raw'].splitlines()
        if rows and rows[0].isdigit(): refresh = int(rows[0])/1e6
        actual = []
        for row in rows[1:]:
            cells = row.split()
            if len(cells)==3 and all(c.isdigit() for c in cells):
                p = int(cells[1])
                if 0<p<9223372036854775807: actual.append(p)
        presents.update(actual)
        if actual: offsets.append(max(actual)/1e9-sample['host_seconds'])
    # Device monotonic clock vs host-relative time, bounded by poll latency/vsync.
    offset = S.median(offsets)
    ordered = sorted(presents)
    bounds = [(offset+s['start'], offset+s['end']) for s in segments]
    per = {}; combined = []
    for s, (lo, hi) in zip(segments, bounds):
        intervals = [(b-a)/1e6 for a,b in zip(ordered,ordered[1:]) if lo<=a/1e9 and b/1e9<=hi]
        per[s['name']] = stats(intervals, refresh); combined.extend(intervals)
    result = {'combined': stats(combined,refresh), 'scenarios': per,
              'clock_offset_seconds': offset,
              'clock_alignment_note': 'Median latest-present timestamp minus poll start; boundaries approximate within one poll round trip plus a frame.'}
    memory_path = work/'meminfo.txt'
    if memory_path.exists():
        memory = memory_path.read_text()
    else:
        with gzip.open(work/'meminfo.txt.gz','rt') as source:
            memory = source.read()
    pss = re.search(r'TOTAL PSS:\s*(\d+)',memory)
    if pss: result['PSS_MiB']=int(pss[1])/1024
    log_path = work/'wf.log'
    if log_path.exists():
        log_text = log_path.read_text()
    else:
        with gzip.open(work/'wf.log.gz','rt') as source:
            log_text = source.read()
    log = log_text.rsplit('=== wf_game android_main',1)[-1]
    windows = []
    for chunk in log.split('frame-window: ')[1:]:
        m = re.match(r'start-ns=(\d+) end-ns=(\d+)',chunk)
        if not m: continue
        start,end = [int(x)/1e9 for x in m.groups()]
        # Retain complete CPU windows inside timed scenarios only.
        if not any(lo<=start and end<=hi for lo,hi in bounds): continue
        measurements = {}
        for m in re.finditer(r'frame-(profile|count): ([\w-]+) frames=(\d+) mean=([\d.]+)',chunk):
            kind,name,n,mean = m.groups(); measurements[name] = {'frames':int(n),'mean':float(mean)}
        windows.append(measurements)
    if windows:
        result['CPU_window_count']=len(windows)
        result['CPU_and_counter_means'] = {
            name:sum(w[name]['frames']*w[name]['mean'] for w in windows if name in w)/sum(w[name]['frames'] for w in windows if name in w)
            for name in windows[0]}
    (work/'analysis.json').write_text(json.dumps(result,indent=2))
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('profiles',nargs='+'); args=ap.parse_args()
    for directory in args.profiles:
        path=Path(directory); runs=[analyse(p) for p in sorted(path.glob('run-*')) if (p/'summary.json').exists()]
        if not runs: continue
        median={k:S.median(r['combined'][k] for r in runs) for k in runs[0]['combined']}
        out={'runs':runs,'median':median,'PSS_MiB_median':S.median(r['PSS_MiB'] for r in runs if 'PSS_MiB' in r)}
        (path/'analysis.json').write_text(json.dumps(out,indent=2)); print(path.name,json.dumps(median))

if __name__=='__main__': main()
