"""Reproduce the phase table/deltas from matched captures and archived builds.
Run from any directory; APKs are kept outside git under /tmp/aquarium-phase3-variants.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import struct
import zipfile

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
PROFILES=OUT.parent/'profiles/phase3-comparison'
BUILDS=Path('/tmp/aquarium-phase3-variants')
NAMES=['B1','B11','P1','P2-static','P2-animated','P3-static','P3-animated']
rows=[]
for name in NAMES:
    presentation=json.loads((PROFILES/name/'analysis.json').read_text())
    instrumented=json.loads((PROFILES/(name+'-cpu')/'analysis.json').read_text())
    cpu=instrumented['runs'][0]['CPU_and_counter_means']
    assert len(presentation['runs'])==3
    row={'variant':name,**presentation['median'],'actor_ms':cpu['actors'],
         'school_ms':cpu.get('school',0),'pose_ms':cpu.get('pose',0),
         'animation_ms':cpu.get('animation',0),'render_ms':cpu['render'],
         'total_cpu_ms':cpu['total'],'pss_mib':instrumented['PSS_MiB_median'],
         'presentation_pss_mib':presentation['PSS_MiB_median'],
         'level_actors':cpu['level-objects'],'render_actors':cpu['render-actors'],
         'draws':cpu['draws'],'rendered_triangles':cpu['triangles'],
         'fish_deformations':cpu.get('fish-deformations',0),
         'presentation_fps_range':[min(r['combined']['fps'] for r in presentation['runs']),max(r['combined']['fps'] for r in presentation['runs'])],
         'cpu_windows':instrumented['runs'][0]['CPU_window_count']}
    log=(PROFILES/(name+'-cpu')/'run-1/wf.log').read_text()
    static=re.findall(r'OptimizeBroadPhase done \((\d+) static bodies\)',log)
    row['static_bodies']=int(static[-1]) if static else None
    memory=(PROFILES/(name+'-cpu')/'run-1/meminfo.txt').read_text()
    for label,key in [('Native Heap','native_heap_mib'),('Graphics','graphics_mib'),('System','system_pss_mib')]:
        m=re.search(r'^\s*'+label+r':\s*(\d+)',memory,re.M)
        row[key]=int(m.group(1))/1024 if m else None
    row['level_cd_bytes']=(BUILDS/(name+'-cd.iff')).stat().st_size
    rows.append(row)
by_name={row['variant']:row for row in rows}
metrics=['actor_ms','school_ms','pose_ms','animation_ms','render_ms','total_cpu_ms','fps','p95_ms','p99_ms','missed_refresh_percent','pss_mib','native_heap_mib','graphics_mib','level_cd_bytes']
deltas=[]
for variant,baseline in [('P3-animated','B1'),('P3-animated','B11'),('P3-animated','P1'),('P3-animated','P2-animated'),('P3-static','P2-static'),('P3-animated','P3-static')]:
    newer=by_name[variant];older=by_name[baseline]
    deltas.append({'variant':variant,'baseline':baseline,'absolute':{k:newer[k]-older[k] for k in metrics},'percent':{k:100*(newer[k]-older[k])/older[k] if older[k] else None for k in metrics}})
protocol='Three presentation runs and one separate instrumented run per variant; 30 s warmup, five 12 s input segments. Identical native libraries; nested CPU scopes; PSS from the instrumented trace.'
(OUT/'comparison.json').write_text(json.dumps({'protocol':protocol,'rows':rows,'deltas':deltas},indent=2))
columns=['variant','actor_ms','school_ms','pose_ms','animation_ms','render_ms','total_cpu_ms','p50_ms','p95_ms','p99_ms','fps','missed_refresh_percent','pss_mib','draws','rendered_triangles','level_actors','render_actors','static_bodies','level_cd_bytes','native_heap_mib','graphics_mib','system_pss_mib']
with (OUT/'comparison.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
headers=['Variant','Actor ms','School ms','Pose ms','Animation ms','Render ms','Total CPU ms','Present p50 / p95 / p99 ms','FPS','Missed refresh %','PSS MiB','Draws / triangles']
table=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
for row in rows:
    values=[row['variant']]+[f"{row[k]:.3f}" for k in ['actor_ms','school_ms','pose_ms','animation_ms','render_ms','total_cpu_ms']]
    values += [' / '.join(f"{row[k]:.3f}" for k in ['p50_ms','p95_ms','p99_ms']),f"{row['fps']:.2f}",f"{row['missed_refresh_percent']:.2f}",f"{row['pss_mib']:.2f}",f"{row['draws']:.0f} / {row['rendered_triangles']:.0f}"]
    table.append('| '+' | '.join(values)+' |')
(OUT/'table.md').write_text('\n'.join(table)+'\n')
# Receipts prove every variant uses precisely the same native binary bytes.
with zipfile.ZipFile('/tmp/aquarium-before-phase3.apk') as src:
    native={n:hashlib.sha256(src.read(n)).hexdigest() for n in src.namelist() if n.endswith('.so')}
artifact=[];receipts=OUT/'builds';receipts.mkdir(exist_ok=True)
for name in NAMES:
    for suffix in ['', '-cpu']:
        label=name+suffix;apk=BUILDS/(label+'.apk')
        with zipfile.ZipFile(apk) as z:
            assert {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.endswith('.so')}==native
            cd=z.read('assets/cd.iff')
            artifact.append({'variant':label,'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'apk_bytes':apk.stat().st_size,'level_cd_bytes':len(cd),'level_cd_sha256':hashlib.sha256(cd).hexdigest(),'instrumented':'assets/wf_args.txt' in z.namelist()})
        (receipts/(label+'.json')).write_bytes((BUILDS/(label+'.json')).read_bytes())
(receipts/'artifact-hashes.json').write_text(json.dumps({'unchanged_native':native,'variants':artifact},indent=2))
data=(ROOT/'wflevels/aquarium/tiger_barb_refined.iff').read_bytes();off=8;chunks={}
while off<len(data):
    tag=data[off:off+4].decode('ascii');size=struct.unpack_from('<I',data,off+4)[0]
    chunks[tag]=data[off+8:off+8+size];off+=8+(size+3)//4*4
mesh={'source_vertices':98,'exported_vertices':len(chunks['VRTX'])//24,'triangles':len(chunks['FACE'])//8,'materials':len(chunks['MATL'])//264,'material_flags':hex(struct.unpack_from('<I',chunks['MATL'])[0]),'mesh_bytes':len(data),'mesh_sha256':hashlib.sha256(data).hexdigest(),'actor_count':61,'barb_actors':29,'barb_meshes_per_actor':1}
assert mesh['triangles']==172 and mesh['materials']==1
(OUT/'mesh-metrics.json').write_text(json.dumps(mesh,indent=2))
print('\n'.join(table))

# Embed the table so the viewer also works when opened directly as a file.
viewer=OUT/'comparison.html'
page=viewer.read_text()
columns=['variant','fps','p95_ms','actor_ms','school_ms','pose_ms','render_ms','total_cpu_ms','pss_mib']
labels=['Variant','FPS','p95 ms','Actor ms','School ms','Pose ms','Render ms','CPU ms','PSS MiB']
markup='<table><thead><tr>'+''.join('<th>'+label+'</th>' for label in labels)+'</tr></thead><tbody>'
for row in rows:
    markup+='<tr>'+''.join('<td>'+(f'{row[k]:.2f}' if isinstance(row[k],(int,float)) else row[k])+'</td>' for k in columns)+'</tr>'
markup+='</tbody></table>'
page=re.sub(r'<p id="status">.*?</p>','<p id="status">'+protocol+'</p>',page)
page=re.sub(r'<div id="results">.*?</div>','<div id="results">'+markup+'</div>',page,flags=re.S)
viewer.write_text(page)
