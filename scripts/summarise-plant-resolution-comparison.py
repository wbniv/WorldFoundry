#!/usr/bin/env python3
"""Verify and analyse a coordinated plant-atlas comparison against 256."""
import argparse
import gzip
import json
import os
from pathlib import Path
import statistics
import re
import subprocess
import shutil
import sys
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('evidence', type=Path)
p.add_argument('--recipe', type=Path, required=True)
p.add_argument('--identities', type=Path, required=True)
p.add_argument('--comparison-size', type=int, default=128, choices=[128,512])
p.add_argument('--matched-static', action='store_true', help='Audit cameras and compare only the two stationary views')
a = p.parse_args()
recipe = json.loads(a.recipe.read_text())
identities = {v['name']:v for v in json.loads(a.identities.read_text())}
receipt = json.loads((a.evidence/'receipt.json').read_text())
assert receipt['result'] == 'completed' and receipt['cleanup_verified']
actual = {v['label']:v for v in receipt['job']['request']['variants']}
native = next(iter(identities.values()))['native']
thermal_statuses = []
core_temperatures = []
camera_audit = {}
analysis_root = a.evidence/'matched-static' if a.matched_static else a.evidence
def camera_of(path):
    # Whole-tank framing has dark exterior at the top left; close framing
    # fills this area with tank water/plants. Preserve pixels in the audit.
    with Image.open(path) as im:
        pixel = im.convert('RGB').getpixel((10,10))
    return ('wide-idle' if sum(pixel)<70 else 'close-idle'), pixel
for variant in recipe['variants']:
    name = variant['label']
    assert actual[name]['apk'] == identities[name]['apk_sha256']+'.apk'
    assert identities[name]['native'] == native
    if a.comparison_size == 512:
        larger = '-512' in name
        assert ('--vram-slot-width=512' in identities[name]['args']) == larger
        assert ('--vram-slot-height=512' in identities[name]['args']) == larger
        assert ('--vram-height=1024' in identities[name]['args']) == larger
    directory = a.evidence/name
    assert len(list(directory.glob('run-*/summary.json'))) == variant['runs']
    for run in sorted(directory.glob('run-*')):
        def read_log(stem):
            path = run/stem
            return path.read_text() if path.exists() else gzip.open(str(path)+'.gz','rt').read()
        log = read_log('wf.log').rsplit('=== wf_game android_main',1)[-1]
        if identities[name].get('plant_catalog'):
            assert re.search(r'PLANTS settings-source=RPRP seed=713 water='+identities[name]['plant_catalog']['settings']['water']+r' age=150(?:\.0*)? speed=0 textures=1 sway=0',log), name
        else:
            # Archived measurements retain their original CLI/native identities.
            assert '--plant-seed=713' in log and '--plant-age=150' in log, name
        thermal = read_log('thermal.txt')
        thermal_statuses += [int(x) for x in re.findall(r'Thermal Status:\s*(\d+)',thermal)]
        current = thermal.split('Current temperatures from HAL:',1)[-1].split('Current cooling devices',1)[0]
        core_temperatures += [float(x) for x in re.findall(r'mValue=([\d.]+).*mName=core_soc_thermal', current)]
        if a.matched_static:
            segments = json.loads((run/'segments.json').read_text())
            retained=[];audit=[]
            for segment in segments:
                actual_camera,pixel=camera_of(run/(segment['name']+'.png'))
                audit.append(dict(label=segment['name'],camera=actual_camera,corner_pixel=pixel))
                if segment['name'] in ('wide-idle','close-idle'):
                    retained.append(dict(segment,name=actual_camera,start=segment['start']+1.0))
            assert {s['name'] for s in retained} == {'wide-idle','close-idle'}, 'Missing distinct stationary views: '+str(run)
            camera_audit[str(run.relative_to(a.evidence))]=audit
            target=analysis_root/name/run.name;target.mkdir(parents=True,exist_ok=True)
            for stem in ('samples.json','summary.json','meminfo.txt','wf.log'):
                source=run/stem
                if (run/(stem+'.gz')).exists():source=run/(stem+'.gz')
                shutil.copyfile(source,target/source.name)
            (target/'segments.json').write_text(json.dumps(retained,indent=2)+'\n')
    subprocess.run([sys.executable, str(Path(__file__).with_name('analyse-aquarium-profile.py')), str(analysis_root/name)], check=True)

rows = []
for water in ('freshwater','saltwater'):
    for size in (256,a.comparison_size):
        name = f'{water}-{size}'
        release = json.loads((analysis_root/name/'analysis.json').read_text())
        cpu = json.loads((analysis_root/(name+'-cpu')/'analysis.json').read_text())['runs'][0]
        assert cpu.get('CPU_window_count',0) >= (2 if a.matched_static else 3), name
        row = dict(case=name, water=water, size=size, **release['median'], PSS_MiB=release['PSS_MiB_median'],
            PSS_range_MiB=[min(r['PSS_MiB'] for r in release['runs']),max(r['PSS_MiB'] for r in release['runs'])],
            FPS_range=[min(r['combined']['fps'] for r in release['runs']),max(r['combined']['fps'] for r in release['runs'])],
            CPU_windows=cpu['CPU_window_count'], CPU_ms_and_counters=cpu['CPU_and_counter_means'],
            scenarios={k:{metric:statistics.median(r['scenarios'][k][metric] for r in release['runs']) for metric in ('fps','p95_ms')} for k in release['runs'][0]['scenarios']})
        if size == a.comparison_size:
            reference = rows[-1]
            row['delta'] = {k:dict(absolute=row[k]-reference[k],percent=100*(row[k]/reference[k]-1)) for k in ('fps','p95_ms','PSS_MiB')}
            row['CPU_delta_ms'] = {k:row['CPU_ms_and_counters'][k]-reference['CPU_ms_and_counters'][k] for k in ('render','actors','animation','total')}
        rows.append(row)
report = dict(job=receipt['job']['id'], native=native, normal_restored=True,
    normal_apk_sha256=receipt['job']['request']['restore_apk'].removesuffix('.apk'),
    thermal_statuses=sorted(set(thermal_statuses)), core_temperature_C_range=[min(core_temperatures),max(core_temperatures)] if core_temperatures else [],
    method='Three release repeats plus one separate CPU run per case; 30-second warmup; 12 seconds each wide, close and crawl. Seed 713, age 150, speed/sway zero, no phone. All native libraries and plant geometry match. CPU sections are nested thread time, not GPU timing. Case blocks are sequential, not randomized; small timing differences and PSS differences need caution.', cases=rows)
if a.comparison_size == 512:
    report['method'] += ' The 512 atlas is repacked from original art and requires 512-square transient slots plus global VRAM height 1024, compared with production 256-square slots and height 512. This measures the current renderer configuration needed for improved looks, not atlas resolution in isolation.'
if a.matched_static:
    report['method'] += ' Camera audit reclassifies stationary segments from their actual screenshot framing. Primary FPS/CPU analysis includes only wide and close idle in every repeat, excluding the first second of each segment for camera/input settling; all crawl segments are excluded because startup input can reverse camera order. Original samples/segments remain intact; matched-static contains derived inputs.'
    report['camera_audit']=camera_audit
    (a.evidence/'camera-audit.json').write_text(json.dumps(camera_audit,indent=2)+'\n')
(a.evidence/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
lines = ['| Water / atlas | FPS (range) | p95 ms | Render CPU ms | Actor CPU ms | Deform CPU ms | PSS MiB |','|---|---:|---:|---:|---:|---:|---:|']
for r in rows:
    c=r['CPU_ms_and_counters']
    lines.append(f"| {r['case']} | {r['fps']:.2f} ({r['FPS_range'][0]:.2f}–{r['FPS_range'][1]:.2f}) | {r['p95_ms']:.2f} | {c['render']:.2f} | {c['actors']:.2f} | {c['animation']:.3f} | {r['PSS_MiB']:.2f} |")
(a.evidence/'comparison.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
os.environ.setdefault('MPLCONFIGDIR',str(a.evidence/'.matplotlib-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(10,3.5),constrained_layout=True)
for ax,values,title in ((axes[0],[r['fps'] for r in rows],'Presented FPS'),(axes[1],[r['CPU_ms_and_counters']['render'] for r in rows],'Render CPU (ms/frame)')):
    ax.barh([r['case'] for r in rows],values,color=['#327652','#91b7a0','#977944','#c5b18b'])
    ax.invert_yaxis();ax.set_title(title);ax.set_xlim(0,max(values)*1.2);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    for i,value in enumerate(values):ax.text(value,i,f' {value:.2f}',va='center')
fig.suptitle(f'Chromecast HD · same mature plants · 256 vs {a.comparison_size} atlas')
fig.savefig(a.evidence/'resolution-comparison.png',dpi=180);plt.close(fig)
# Matched complete views and central leaf detail, preserving source pixels.
for water in ('freshwater','saltwater'):
    for camera in ('wide-idle','close-idle'):
        paths=[]
        for size in (256,a.comparison_size):
            folder=a.evidence/f'{water}-{size}'/'run-1'
            source=folder/f'{camera}.png'
            if a.matched_static:
                source=next(folder/(s+'.png') for s in ('wide-idle','close-idle') if camera_of(folder/(s+'.png'))[0]==camera)
            paths.append(source)
        images=[Image.open(path).convert('RGB') for path in paths]
        assert images[0].size == images[1].size
        w,h=images[0].size
        canvas=Image.new('RGB',(w*2,h+44),'#edf2e9');draw=ImageDraw.Draw(canvas)
        font=ImageFont.truetype('DejaVuSans.ttf',24)
        for col,(size,im) in enumerate(zip((256,a.comparison_size),images)):
            canvas.paste(im,(col*w,44));draw.text((col*w+20,8),f'{water} / {size} atlas / {camera}',fill='#183a32',font=font)
        canvas.save(a.evidence/f'{water}-{camera}-pair.png')
        cropw,croph=min(480,w),min(320,h)
        x,y=int(w*.65-cropw/2),int(h*.52-croph/2)
        canvas=Image.new('RGB',(cropw*2,croph+44),'#edf2e9');draw=ImageDraw.Draw(canvas)
        font=ImageFont.truetype('DejaVuSans.ttf',18)
        for col,(size,im) in enumerate(zip((256,a.comparison_size),images)):
            canvas.paste(im.crop((x,y,x+cropw,y+croph)),(col*cropw,44));draw.text((col*cropw+15,12),f'{size} atlas · native pixel crop',fill='#183a32',font=font)
        canvas.save(a.evidence/f'{water}-{camera}-detail.png')
