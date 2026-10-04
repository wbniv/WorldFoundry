#!/usr/bin/env python3
"""Build a reviewable comparison from analysed, matched Chromecast plant traces."""
import argparse,json,re,statistics as st
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('profiles',type=Path);p.add_argument('--identities',type=Path,required=True);a=p.parse_args()
ids=json.loads(a.identities.read_text()); rows=[]
for case in ids:
    name=case['name']
    if name.endswith('-cpu'):continue
    folder=a.profiles/name
    if not (folder/'analysis.json').exists():continue
    normal=json.loads((folder/'analysis.json').read_text());cpu_path=a.profiles/(name+'-cpu')/'analysis.json'
    cpu=json.loads(cpu_path.read_text()) if cpu_path.exists() else None
    startup=[]
    for run in sorted(folder.glob('run-*')):
        if not (run/'summary.json').exists():continue
        receipt=json.loads((folder/'receipt.json').read_text());assert receipt['apk_sha256']==case['apk_sha256']
        text=(run/'wf.log').read_text()
        found=re.findall(r'PLANTS generation=1 seed=(\d+) mode=(\w+) shoots=(\d+) vertices=(\d+) triangles=(\d+) graph_ms=([\d.]+) mesh_ms=([\d.]+)',text)
        if found:
            seed,mode,shoots,vertices,triangles,graph,mesh=found[-1]
            startup.append(dict(seed=int(seed),mode=mode,shoots=int(shoots),vertices=int(vertices),authored_triangles=int(triangles),graph_ms=float(graph),mesh_ms=float(mesh)))
    means={}
    if cpu:
        for metric in cpu['runs'][0].get('CPU_and_counter_means',{}):means[metric]=st.median(r['CPU_and_counter_means'][metric] for r in cpu['runs'])
    scenes={name:{k:st.median(r['scenarios'][name][k] for r in normal['runs']) for k in ['fps','p95_ms']} for name in normal['runs'][0]['scenarios']}
    rows.append(dict(name=case['name'],runs=len(normal['runs']),cpu_runs=len(cpu['runs']) if cpu else 0,**normal['median'],PSS_MiB=normal['PSS_MiB_median'],scenarios=scenes,cpu=means,startup=startup,identity=case))
by_name={r['name']:r for r in rows}
for row in rows:
    reference=row['name']+'-shaded'
    if reference not in by_name:reference='old-static'
    if reference in by_name and reference!=row['name']:
        base=by_name[reference];row['reference']=reference
        row['delta']={metric:dict(absolute=row[metric]-base[metric],percent=(row[metric]/base[metric]-1)*100) for metric in ['fps','p95_ms','PSS_MiB']}
        row['cpu_delta']={metric:row['cpu'][metric]-base['cpu'][metric] for metric in row['cpu'] if metric in base['cpu']}
summary={'method':'Median of uninstrumented release repeats, with matching native libraries and fixed input traces. CPU sections come from separate instrumented runs; nested sections are not additive. Seed 713 except named seed cases. FPS excludes warmup and screenshot gaps.','cases':rows}
(a.profiles/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['| Case | Release / CPU runs | FPS | p95 ms | Render CPU ms | Growth/deform CPU ms | Actor CPU ms | PSS MiB |','|---|---:|---:|---:|---:|---:|---:|---:|']
for row in rows:
    fmt=lambda x:'—' if x is None else f'{x:.2f}'
    lines.append('| '+row['name']+f" | {row['runs']} / {row['cpu_runs']} | "+' | '.join(fmt(x) for x in [row['fps'],row['p95_ms'],row['cpu'].get('render'),row['cpu'].get('animation'),row['cpu'].get('actors'),row['PSS_MiB']])+' |')
(a.profiles/'comparison.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
