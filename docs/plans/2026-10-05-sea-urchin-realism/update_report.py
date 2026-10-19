#!/usr/bin/env python3
"""Render the urchin plan and a comparison using saved Chromecast evidence only."""
from pathlib import Path
import json
import statistics
import markdown

HERE=Path(__file__).resolve().parent
rows=[]
for phase in range(4):
    folder=HERE/'evidence'/f'phase-{phase}'
    normal=folder/'chromecast/release/analysis.json'
    cpu=folder/'chromecast/cpu/analysis.json'
    if not normal.exists():continue
    n=json.loads(normal.read_text());c=json.loads(cpu.read_text()) if cpu.exists() else {}
    metrics={}
    for run in c.get('runs',[]):
        for key,value in run.get('CPU_and_counter_means',{}).items():metrics.setdefault(key,[]).append(value)
    row=dict(phase=phase,**n['median'],PSS_MiB=n.get('PSS_MiB_median'),cpu={key:statistics.median(values) for key,values in metrics.items()},scenarios={name:{key:statistics.median(run['scenarios'][name][key] for run in n['runs']) for key in ('fps','p95_ms')} for name in n['runs'][0]['scenarios']})
    row['source_counts']=json.loads((folder/'source-counts.json').read_text())
    rows.append(row)
if rows:
    base=rows[0]
    for row in rows:
        row['delta_vs_phase_0']={key:dict(absolute=row[key]-base[key],percent=100*(row[key]/base[key]-1)) for key in ('fps','p95_ms','PSS_MiB') if row.get(key) is not None and base.get(key)}
        row['cpu_delta_ms']={key:row['cpu'][key]-base['cpu'][key] for key in ('actors','director','render','animation','update','total') if key in row['cpu'] and key in base['cpu']}
(HERE/'comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
lines=['# Sea-urchin phase comparison','', 'Performance evidence comes exclusively from Chromecast 1. Desktop captures check geometry, contacts and movement correctness; desktop load/FPS is not used. Fixed native library hashes, saltwater seed 713, plant age 150, growth speed 0, existing water sway. Three release repeats and one separately instrumented repeat per phase; each repeat contains 60 seconds each of wide idle, close idle and cardinal crawl. CPU values are reported separately from presented-frame pacing.','', '| Phase | Animal / scene actors | Animal source triangles | FPS | Δ FPS % | p95 present ms | Actor CPU ms | Render CPU ms | PSS MiB | Δ actor CPU ms | Δ render CPU ms |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
fmt=lambda x:'—' if x is None else f'{x:.3f}'
for row in rows:
    count=row['source_counts']
    lines.append(f'| {row["phase"]} | {count["animal_actors"]} / {count["scene_actors"]} | {count["animal_triangles"]} | '+' | '.join(fmt(x) for x in (row['fps'],row['delta_vs_phase_0']['fps']['percent'],row['p95_ms'],row['cpu'].get('actors'),row['cpu'].get('render'),row.get('PSS_MiB'),row['cpu_delta_ms'].get('actors'),row['cpu_delta_ms'].get('render')))+' |')
lines+=['','Source triangle counts can differ from cooked meshes. Presented p95 is frame interval, not CPU time. The coordinator’s reviewed plants trace uses cardinal key events; diagonal, reversal and anchor checks use deterministic host/runtime correctness traces. Chromecast 2 currently requires local setup. CPU repeats are exploratory single runs; do not infer statistical certainty from small deltas.','']
lines+=['## Instrumented script and rendering cost','', '| Phase | Director CPU ms | Δ Director CPU ms | Plant animation CPU ms | Actor mailbox writes/frame | Render actors/frame | Draws/frame | Rendered triangles/frame |','|---|---:|---:|---:|---:|---:|---:|---:|']
for row in rows:
    lines.append(f'| {row["phase"]} | '+' | '.join(fmt(value) for value in (row['cpu'].get('director'),row['cpu_delta_ms'].get('director'),*[row['cpu'].get(key) for key in ('animation','actor-mailbox-writes','render-actors','draws','triangles')]))+' |')
lines+=['', 'Director CPU includes its Forth and runtime plant calls. The animation section measures existing runtime plant animation and overlaps Director CPU; do not add it again. These counters cover the whole planted scene, not an isolated animal. Source animal triangles and rendered scene triangles are distinct.','']
for row in rows:
    lines += [f'## Phase {row["phase"]} scenarios','', '| Scenario | FPS | p95 present ms |','|---|---:|---:|']
    lines += [f'| {name} | {data["fps"]:.3f} | {data["p95_ms"]:.3f} |' for name,data in row['scenarios'].items()]
    lines+=['']
(HERE/'comparison.md').write_text('\n'.join(lines))
style='body{max-width:1140px;margin:36px auto;padding:0 24px;background:#faf7ee;color:#263c48;font:17px/1.6 system-ui,sans-serif}h1,h2,h3{line-height:1.2;color:#654784}h2{margin-top:42px}img{max-width:100%;display:block;margin:20px auto;border-radius:12px}img[src$="poster.png"]{max-width:520px;width:100%}table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow-x:auto}th,td{border:1px solid #c5d3cb;padding:10px;text-align:left;vertical-align:top}th{background:#e0ece5}a{color:#167e83}pre{padding:20px;background:#e8ece7;overflow:auto}'
for p in (HERE.with_suffix('.md'),HERE/'comparison.md'):
    body=markdown.markdown(p.read_text(),extensions=['tables','fenced_code'])
    p.with_suffix('.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sea urchin realism</title><style>'+style+'</style><main>'+body+'</main></html>')
print(HERE/'comparison.html')
