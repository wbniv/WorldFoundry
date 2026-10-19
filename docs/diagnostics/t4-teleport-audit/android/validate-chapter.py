"""Check retained chapter pose evidence and coordinator cleanup, offline."""
import argparse,hashlib,itertools,json,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);args=p.parse_args()
batch=json.loads((args.evidence/'batch.json').read_text());assert batch['state']=='completed'
results=[]
for path in sorted(args.evidence.rglob('wf.log')):
    receipt=json.loads((path.parent/'receipt.json').read_text())
    assert receipt['result']=='completed' and receipt['cleanup_verified'] and not receipt['error'],receipt
    text=path.read_text(errors='replace').rsplit('=== wf_game android_main',1)[-1]
    rows=re.findall(r'ball pos: \(([^)]*)\)',text)
    sequence=[k for k,_ in itertools.groupby(next((name for center,name in [(294,'Truth'),(400,'God'),(500,'Being')]
        if abs(float(row.split(',')[0])-center)<10),'other') for row in rows)]
    assert sequence[:4]==['Truth','God','Being','Truth'] and len(sequence)>=7,sequence
    assert all((a,b) in [('Truth','God'),('God','Being'),('Being','Truth')] for a,b in zip(sequence,sequence[1:])),sequence
    assert not any(s in text for s in ['Fatal signal','FATAL EXCEPTION','ASSERTION FAILED','zforth compile error','zforth eval error','ValidPtr( (nil) ) failed','runtime error:']),str(path)
    video=path.parent/'capture.mp4'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-show_entries','format=duration,size','-of','json',str(video)]))
    assert float(probe['format']['duration'])>=130,probe
    result=dict(log=str(path),log_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pose_samples=len(rows),
        observed_realm_sequence=sequence,observed_transitions=len(sequence)-1,cleanup_verified=True,
        video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),video=probe,passed=True)
    results.append(result);print(json.dumps(result),flush=True)
assert len(results)==2
(args.evidence/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
