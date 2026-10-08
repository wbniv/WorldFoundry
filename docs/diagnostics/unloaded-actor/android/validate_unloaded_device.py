"""Validate autonomous inactive-source actor evidence without accessing devices."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def validate(path, minimum=24):
    text=path.read_text(errors='replace').rsplit('=== wf_game android_main',1)[-1]
    rows=[list(map(float,line.split())) for line in re.findall(r'T4_ACTOR ([^\r\n]+)',text)]
    assert len(rows)>=minimum, f'{path}: only {len(rows)} observations'
    assert rows[0][0]==1, f'{path}: initial never-loaded case missing'
    sequence=[7,8,9,8,1,4,7,8,7,8,9,8]
    for step,command,player,camera,target,delta,frames in rows:
        assert command==sequence[(int(step)-1)%12], f'wrong command: {step,command}'
        expected_player=300 if command==1 else 0
        expected_target=-5 if command in (7,9) else 295
        assert abs(player-expected_player)<.01 and abs(camera-player)<.01
        assert abs(target-expected_target)<.01 and frames>=10
        if command in (7,9,1):
            assert frames-2<=delta<=frames+1, f'active target stalled: {step,command,delta,frames}'
        else:
            assert 0<=delta<=1, f'inactive target kept updating: {step,command,delta,frames}'
    assert all(b[0]==a[0]+1 for a,b in zip(rows,rows[1:])), 'missing observations'
    assert not re.search(r'Fatal signal|FATAL EXCEPTION|ASSERTION FAILED|zforth (?:compile|eval) error|ValidPtr\( \(nil\) \) failed|runtime error:',text)
    return {'log':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'observations':len(rows),'complete_cycles':len(rows)//12,
            'active_intervals':sum(row[1] in (7,9,1) for row in rows),
            'inactive_intervals':sum(row[1] in (8,4) for row in rows),
            'initial_never_loaded_verified':True,'passed':True}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('evidence',type=Path);p.add_argument('--minimum',type=int,default=24)
    p.add_argument('--logs',type=int,default=2)
    args=p.parse_args()
    paths=[args.evidence] if args.evidence.is_file() else sorted(args.evidence.rglob('wf.log'))
    assert len(paths)==args.logs, f'expected {args.logs} logs, found {len(paths)}'
    results=[validate(path,args.minimum) for path in paths]
    print(json.dumps(results,indent=2))
    if args.evidence.is_dir():(args.evidence/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
