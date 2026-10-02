#!/usr/bin/env python3
"""Isolated desktop CPU/wall-time probes; never rewrites canonical levels or app assets."""
import hashlib,json,os,re,shutil,statistics,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/plans/2026-10-02-lionfish-goldfish-feeding/profiles/desktop'
TMP=Path('/tmp/lionfish-goldfish-profiles');TMP.mkdir(exist_ok=True,parents=True);OUT.mkdir(exist_ok=True,parents=True)
source=ROOT/'wflevels/aquarium_lionfish'
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs'),ASAN_OPTIONS='detect_leaks=0',
         __GL_SYNC_TO_VBLANK='0',vblank_mode='0',WF_REST_HOST='127.0.0.1',WF_REST_PORT='18935')
iffcomp=ROOT/'wftools/iffcomp-rs/target/release/iffcomp'
levcomp=ROOT/'wftools/levcomp-rs/target/release/levcomp'
variants={'baseline':Path('/tmp/lionfish-goldfish-baseline/baseline.iff')}
for label,count,capture in [('active-0',0,False),('active-1',1,False),('active-3',3,False),('chase-capture',3,True)]:
    parent=TMP/label;here=parent/'level';shutil.copytree(source,here,dirs_exist_ok=True)
    name='aquarium_lionfish'
    text=(here/(name+'.lev')).read_text().replace(': gf-initial 0 ;',f': gf-initial {count} ;').replace(': gf-autoeat 1 ;',f': gf-autoeat {int(capture)} ;')
    (here/(name+'.lev')).write_text(text)
    with (parent/'build.log').open('w') as log:
        subprocess.run([str(iffcomp),'-binary',f'-o={name}.lev.bin',name+'.lev'],cwd=here,stdout=log,stderr=log,check=True)
        subprocess.run([str(levcomp),name+'.lev.bin',str(ROOT/'wfsource/source/oas/objects.lc'),name+'.lvl',
                        str(ROOT/'wfsource/source/oas'),'--mesh-dir','.', '--iff-txt',name+'.iff.txt','--textile-ini',name+'.ini'],cwd=here,stdout=log,stderr=log,check=True)
        subprocess.run([str(iffcomp),'-binary',f'-o=../{name}.iff',name+'.iff.txt'],cwd=here,stdout=log,stderr=log,check=True)
        subprocess.run([str(iffcomp),'-binary',f'-o=../{name}-standalone.iff',name+'-standalone.iff.txt'],cwd=here,stdout=log,stderr=log,check=True)
    variants[label]=parent/(name+'-standalone.iff')
report={}
for label,path in variants.items():
    here=OUT/label;here.mkdir(exist_ok=True)
    results=[]
    for run in range(3):
        durations={}
        for frames in [100,600]:
            start=time.monotonic()
            with (here/f'run-{run+1}-{frames}.log').open('w') as log:
                subprocess.run([str(ROOT/'engine/wf_game'),'-L'+str(path),'-rate60',f'--frame-step-smoke={frames}'],
                               cwd=source,env=env,stdout=log,stderr=log,check=True,timeout=90)
            durations[frames]=time.monotonic()-start
        results.append((durations[600]-durations[100])*2)
    # Separate CPU instrumentation, weighted from emitted complete 5s windows.
    with (here/'cpu.log').open('w') as log:
        subprocess.run([str(ROOT/'engine/wf_game'),'-L'+str(path),'-rate60','--frame-step-smoke=1200','--frame-profile'],
                       cwd=source,env=env,stdout=log,stderr=log,check=True,timeout=90)
    text=(here/'cpu.log').read_text(errors='replace');cpu={};counters={}
    for kind,target in [('frame-profile',cpu),('frame-count',counters)]:
        entries={}
        for key,n,mean in re.findall(kind+r': ([\w-]+) frames=(\d+) mean=([\d.]+)',text):entries.setdefault(key,[]).append((int(n),float(mean)))
        for key,vals in entries.items():target[key]=sum(n*v for n,v in vals)/sum(n for n,v in vals)
    assert cpu,'No profiling windows emitted'
    report[label]={'level_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'wall_ms_per_frame_runs':results,
                   'wall_ms_per_frame_median':statistics.median(results),'CPU_ms_per_frame':cpu,'counters':counters,
                   'exported_actors':34 if label=='baseline' else len(json.loads((source/'actor-map.json').read_text())['indices']),
                   'population':'dynamic, starting at 3' if label=='chase-capture' else (0 if label=='baseline' else int(label[-1])),
                   'note':'Desktop ASAN debug engine, vsync off, fixed 60Hz simulation; 3 subtraction runs (600−100 frames), separate 1200-frame CPU probe. Auto-capture disabled only in fixed-population copies; chase-capture keeps natural feeding and no automatic replenishment. School measures the entire feeding tick, including resident pose; section timings overlap and must not be summed.'}
    (here/'summary.json').write_text(json.dumps(report[label],indent=2)+'\n')
    print(label,json.dumps(report[label]),flush=True)
(OUT/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT/'.gitignore').write_text('**/*.log\n')
