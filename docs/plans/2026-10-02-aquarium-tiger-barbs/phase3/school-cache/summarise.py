"""Reproduce the matched schooling comparison from saved device captures."""
from pathlib import Path
import csv
import json
import re
OUT=Path(__file__).resolve().parent
PROFILES=OUT.parent.parent/'profiles/school-cache'
rows=[]
for name in ['P3-before','P3-cache']:
    presented=json.loads((PROFILES/name/'analysis.json').read_text())
    instrumented=json.loads((PROFILES/(name+'-cpu')/'analysis.json').read_text())
    assert len(presented['runs'])==3
    cpu=instrumented['runs'][0]['CPU_and_counter_means']
    rows.append({'variant':name,**presented['median'],
        'school_ms':cpu['school'],'actor_ms':cpu['actors'],
        'pose_ms':cpu['pose'],'animation_ms':cpu['animation'],
        'render_ms':cpu['render'],'total_cpu_ms':cpu['total'],
        'pss_mib':instrumented['PSS_MiB_median'],
        'level_actors':cpu['level-objects'],'render_actors':cpu['render-actors'],
        'draws':cpu['draws'],'triangles':cpu['triangles'],
        'fish_deformations':cpu['fish-deformations'],
        'fps_range':[min(r['combined']['fps'] for r in presented['runs']),max(r['combined']['fps'] for r in presented['runs'])],
        'cpu_windows':instrumented['runs'][0]['CPU_window_count']})
a,b=rows
metrics=['school_ms','actor_ms','pose_ms','animation_ms','render_ms','total_cpu_ms','fps','p95_ms','p99_ms','missed_refresh_percent','pss_mib']
delta={k:{'absolute':b[k]-a[k],'percent':100*(b[k]/a[k]-1)} for k in metrics}
late=json.loads((PROFILES/'P3-before-late/analysis.json').read_text())
control={'fps':late['median']['fps'],'baseline_fps':a['fps'],'change_percent':100*(late['median']['fps']/a['fps']-1)}
thermal=[]
for file in sorted(PROFILES.glob('*/run-*/thermal.txt')):
    match=re.search(r'^Thermal Status: (\d+)',file.read_text(),re.M)
    assert match and int(match[1])==0,file
    thermal.append({'path':str(file.relative_to(PROFILES)),'status':int(match[1])})
assert len(thermal)==9
protocol='Chromecast HD 1920×1080; 30 s warmup; five 12 s timed segments; 3 uninstrumented runs + 1 CPU trace per build; late baseline control. Identical native libraries, 29 phase 3 meshes, 5 behavior updates/frame.'
data={'protocol':protocol,'rows':rows,'deltas':delta,'late_control':control,'thermal':thermal,'limitations':'CPU scopes are nested; total is update plus render. SurfaceFlinger FPS measures presentation, not isolated GPU execution. Simulation output equivalence is established by the fixed-step VM regressions; device traces follow the same timed inputs.'}
(OUT/'comparison.json').write_text(json.dumps(data,indent=2)+'\n')
with (OUT/'comparison.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(a));writer.writeheader();writer.writerows(rows)
table=[protocol,'','| Build | School ms | Render ms | CPU total ms | FPS | p95 ms | Missed refresh % | PSS MiB |','|---|---:|---:|---:|---:|---:|---:|---:|']
for row in rows:
    table.append('| '+row['variant']+' | '+' | '.join(f'{row[k]:.3f}' for k in ['school_ms','render_ms','total_cpu_ms','fps','p95_ms','missed_refresh_percent','pss_mib'])+' |')
table+=['','| Metric | Absolute delta | Relative delta |','|---|---:|---:|']
for k in metrics:
    table.append(f"| {k} | {delta[k]['absolute']:+.3f} | {delta[k]['percent']:+.2f}% |")
table+=['',f"Late baseline: {control['fps']:.3f} FPS ({control['change_percent']:+.2f}% versus initial baseline). All nine captures have thermal status 0."]
(OUT/'table.md').write_text('\n'.join(table)+'\n')
print('\n'.join(table))
