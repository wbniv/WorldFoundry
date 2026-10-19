#!/usr/bin/env python3
"""Analyse the current-build, coordinator-owned texture comparison separately from historical traces."""
import argparse, json, statistics, subprocess, sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('evidence',type=Path)
p.add_argument('--recipe',type=Path,required=True)
p.add_argument('--identities',type=Path,required=True)
a=p.parse_args()
recipe=json.loads(a.recipe.read_text()); identities={v['name']:v for v in json.loads(a.identities.read_text())}
receipt=json.loads((a.evidence/'receipt.json').read_text())
assert receipt['result']=='completed' and receipt['cleanup_verified'], 'Benchmark did not complete with verified cleanup'
actual={v['label']:v for v in receipt['job']['request']['variants']}
expected_native=None
for v in recipe['variants']:
    identity=identities[v['label']]
    assert actual[v['label']]['apk']==identity['apk_sha256']+'.apk', v['label']
    if expected_native is None: expected_native=identity['native']
    assert identity['native']==expected_native, 'Native libraries differ between cases'
    directory=a.evidence/v['label']
    assert len(list(directory.glob('run-*/summary.json')))==v['runs'], v['label']
    subprocess.run([sys.executable,str(Path(__file__).with_name('analyse-aquarium-profile.py')),str(directory)],check=True)

rows=[]
for v in recipe['variants']:
    name=v['label']
    if name.endswith('-cpu'):continue
    release=json.loads((a.evidence/name/'analysis.json').read_text())
    cpu=json.loads((a.evidence/(name+'-cpu')/'analysis.json').read_text())
    cpu_means=cpu['runs'][0].get('CPU_and_counter_means',{})
    assert cpu_means, 'No CPU windows inside timed scenarios: '+name
    row={'case':name,'release_runs':len(release['runs']),'cpu_runs':len(cpu['runs']),
         **release['median'],'PSS_MiB':release['PSS_MiB_median'],'CPU_ms_and_counters':cpu_means,
         'CPU_windows':sum(r.get('CPU_window_count',0) for r in cpu['runs']),
         'scenarios':{key:{metric:statistics.median(r['scenarios'][key][metric] for r in release['runs'])
             for metric in ['fps','p95_ms']} for key in release['runs'][0]['scenarios']}}
    rows.append(row)
by_name={r['case']:r for r in rows}
for row in rows:
    base=by_name.get(row['case']+'-shaded',by_name['old-static'])
    if base is row:continue
    row['reference']=base['case']
    row['delta']={k:{'absolute':row[k]-base[k],'percent':100*(row[k]/base[k]-1)} for k in ['fps','p95_ms','PSS_MiB']}
    row['CPU_delta_ms']={k:row['CPU_ms_and_counters'][k]-base['CPU_ms_and_counters'][k]
                         for k in ['render','actors','animation','total']}
report={'job':receipt['job']['id'],'method':'Three release repeats and one separate CPU run per case. Current native libraries in all cases, no phone connected, 30-second warmup and 12-second wide/close/crawl scenarios. Present intervals exclude screenshot gaps. CPU sections are thread CPU time, nested and not additive; these are not GPU timings. Paired shaded controls retain the atlas, so memory differences do not measure removal of texture storage.',
        'native':expected_native,'normal_apk_sha256':receipt['job']['request']['restore_apk'].removesuffix('.apk'),
        'normal_restored':True,'cases':rows}
(a.evidence/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
lines=['| Case | FPS | p95 ms | Render CPU ms | Actors CPU ms | Growth/deform CPU ms | PSS MiB |',
       '|---|---:|---:|---:|---:|---:|---:|']
for r in rows:
    c=r['CPU_ms_and_counters']
    lines.append('| '+r['case']+' | '+' | '.join(f'{x:.2f}' for x in [r['fps'],r['p95_ms'],c['render'],c['actors'],c['animation'],r['PSS_MiB']])+' |')
(a.evidence/'comparison.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))

# A shareable plot of measured values; CPU and presented FPS have separate axes.
import os
os.environ.setdefault('MPLCONFIGDIR',str(a.evidence/'.matplotlib-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
labels=['Static reference','Freshwater textured','Freshwater shaded',
        'Saltwater textured','Saltwater shaded']
fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
colours=['#667c8a','#368357','#9bbda5','#aa8547','#cbb899']
for ax,values,title in [(axes[0],[r['fps'] for r in rows],'Presented FPS'),
                       (axes[1],[r['CPU_ms_and_counters']['render'] for r in rows],'Render CPU (ms/frame)')]:
    ax.barh(labels,values,color=colours)
    ax.invert_yaxis();ax.set_title(title);ax.set_xlim(0,max(values)*1.22)
    ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    for i,value in enumerate(values):ax.text(value,i,f' {value:.2f}',va='center',fontsize=9)
fig.suptitle('Chromecast HD · current native libraries · seed 713 · mature plants')
fig.savefig(a.evidence/'texture-comparison.png',dpi=180)
fig.savefig(a.evidence/'texture-comparison.svg')
plt.close(fig)
