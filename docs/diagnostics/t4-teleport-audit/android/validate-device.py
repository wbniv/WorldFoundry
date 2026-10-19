"""Validate coordinator-downloaded autonomous teleport logs, offline."""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);p.add_argument('--minimum',type=int,default=70)
args=p.parse_args();results=[]
for path in sorted(args.evidence.rglob('wf.log')):
    text=path.read_text(errors='replace').rsplit('=== wf_game android_main',1)[-1]
    rows=[list(map(float,s.split())) for s in re.findall(r'T4_ARRIVAL ([^\r\n]+)',text)]
    assert len(rows)>=args.minimum,f'{path}: only {len(rows)} arrivals'
    expected={1:300,2:100,3:200,4:0,5:200};sequence=[2,4,1,2,5,1,4]
    for row in rows:
        step,command,x,camera,scale,ok=row
        assert command==sequence[(int(step)-1)%7],f'{path}: wrong command sequence {row}'
        assert abs(x-expected[int(command)])<.01 and abs(camera-x)<.01 and scale==.25 and ok!=0,f'{path}: failed arrival {row}'
    assert all(int(b[0])==int(a[0])+1 for a,b in zip(rows,rows[1:])),f'{path}: missing arrival records'
    assert not any(s in text for s in ['Fatal signal','FATAL EXCEPTION','ASSERTION FAILED','zforth compile error','zforth eval error','ValidPtr( (nil) ) failed','runtime error:']),f'{path}: engine diagnostic'
    result=dict(log=str(path),log_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),arrivals=len(rows),
        first_step=int(rows[0][0]),last_step=int(rows[-1][0]),full_laps=len(rows)//7,
        camera_max_error=max(abs(r[2]-r[3]) for r in rows),scale=.25,passed=True)
    results.append(result);print(json.dumps(result),flush=True)
assert len(results)==2,f'expected both Chromecast logs; found {len(results)}'
(args.evidence/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
