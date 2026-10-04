#!/usr/bin/env python3
"""Build/freeze, play, collect evidence and restore through owned coordinator sessions."""
import argparse
from datetime import datetime
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
TV=ROOT/'party-games/games/patchwork/tv'
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin',default=os.environ.get('WF_PD_ORIGIN'))
    parser.add_argument('--pool',default=os.environ.get('WF_PD_POOL') or 'chromecast-test')
    parser.add_argument('--out',type=Path,default=Path(os.environ.get('WF_PD_OUT') or ROOT/'docs/diagnostics'/('patchwork-tv-playthrough-'+datetime.now().strftime('%Y%m%d-%H%M%S'))))
    args=parser.parse_args()
    if not args.origin:parser.error('A running hosted game is required: set ORIGIN=https://...')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    print('Evidence: '+str(out),flush=True)
    def run(command,name):
        with (out/name).open('w') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        text=(out/name).read_text();print(text,end='',flush=True)
        return result.returncode,text
    def submit(apk,selector,duration,name):
        code,text=run(['task','chromecast:check','APP=patchwork',selector,'APK='+apk,f'DURATION={duration}','ASYNC=true'],name)
        match=re.search(r'Accepted (J-[a-f0-9]+):',text)
        if code or not match:raise RuntimeError('Coordinator submission failed; see '+str(out/name))
        return match.group(1)
    try:
        # Both versions are frozen before requesting any device session.
        for mode,flags in [('automated',['--automated-check']),('interactive',[])]:
            code,_=run([sys.executable,str(TV/'build.py'),'--origin',args.origin,*flags],mode+'-build.log')
            if code:return code
            receipt=json.loads((TV/'build'/mode/'build-receipt.json').read_text())
            (out/(mode+'-build-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
        sources=list((ROOT/'party-games/games/patchwork').glob('*.js'))
        for folder,pattern in [('party-games/games/patchwork/client','*'),('party-games/platform/receiver-shell','*'),('party-games/platform/controller-shell','*'),('party-games/platform/server','*.js')]:
            sources.extend((ROOT/folder).glob(pattern))
        (out/'web-source-hashes.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()},indent=2)+'\n')
        run(['task','chromecast:queue'],'queue.log')
        automated=json.loads((out/'automated-build-receipt.json').read_text())
        job=submit(automated['apk'],'POOL='+args.pool,180,'submission.log')
        print('Game job: '+job,flush=True)
        # Interrupting this watcher does not cancel the job. The printed job ID
        # and submission log let the owner resume following it safely.
        check_code,_=run(['task','chromecast:watch','JOB='+job],'watch.log')
        evidence_code,_=run(['task','chromecast:evidence','JOB='+job,'OUT='+str(out/'game')],'evidence.log')
        if evidence_code:return evidence_code
        receipt=json.loads((out/'game/receipt.json').read_text())
        if not receipt.get('cleanup_verified'):
            raise RuntimeError('Cleanup is not verified; restoration must wait for coordinator recovery')
        device=receipt.get('device',{}).get('id')
        if not device:raise RuntimeError('No allocated device in receipt; ordinary build restoration cannot be targeted')
        interactive=json.loads((out/'interactive-build-receipt.json').read_text())
        restore=submit(interactive['apk'],'DEVICE='+device,15,'restore-submission.log')
        restore_code,_=run(['task','chromecast:watch','JOB='+restore],'restore-watch.log')
        saved_code,_=run(['task','chromecast:evidence','JOB='+restore,'OUT='+str(out/'restored')],'restore-evidence.log')
        if restore_code and not saved_code:
            restored=json.loads((out/'restored/receipt.json').read_text())
            if restored.get('cleanup_verified') and restored.get('error')=='Target app left foreground; measurement invalid':
                print('Retrying one foreground launch check after verified cleanup; the initial failure remains archived.',flush=True)
                retry=submit(interactive['apk'],'DEVICE='+device,15,'restore-retry-submission.log')
                restore_code,_=run(['task','chromecast:watch','JOB='+retry],'restore-retry-watch.log')
                saved_code,_=run(['task','chromecast:evidence','JOB='+retry,'OUT='+str(out/'restored-retry')],'restore-retry-evidence.log')
        result=check_code or restore_code or saved_code
        print(('PASS' if result==0 else 'FAIL')+': TV playthrough and ordinary-build restoration. Evidence: '+str(out),flush=True)
        return result
    except (OSError,RuntimeError,json.JSONDecodeError) as error:
        print(str(error),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
