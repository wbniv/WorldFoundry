#!/usr/bin/env python3
"""Submit background-only installations through the standalone coordinator."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/diagnostics/bomberman-chromecast'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'scripts'))
from wf_device.client import Client
from coordinator_producer import require_capabilities

def main():
    report=OUT/'installation.log'
    print('Installation log: '+str(report),flush=True)
    print('Checking coordinator capabilities',flush=True)
    try:
        client=Client()
        require_capabilities(client,'install')
    except RuntimeError as error:
        with report.open('a') as log:
            log.write(str(error)+'\n')
        print(str(error),file=sys.stderr,flush=True)
        return 1
    receipt=json.loads((ROOT/'android/bomberman/build/build-receipt.json').read_text())
    assert hashlib.sha256(Path(receipt['apk']).read_bytes()).hexdigest()==receipt['sha256']
    print('Submitting background-only APK installations; each device waits only for its own session',flush=True)
    jobs=[]
    journal=OUT/'jobs.json'
    previous=json.loads(journal.read_text()) if journal.exists() else {}
    resumable=previous.get('apk',{}).get('sha256')==receipt['sha256']
    by_device=previous.get('devices',{}) if resumable else {}
    for device in ('chromecast-test-01','chromecast-test-02'):
        jid=by_device.get(device)
        if jid:
            job=client.call('status',{'job':jid})
            if job['owner']!=client.credentials['session']:
                raise RuntimeError('Existing installation belongs to another session; follow its printed job ID')
        else:
            job=client.submit({'workflow':'install','app':'bomberman','device':device,'apk':receipt['apk']})
            by_device[device]=job['id']
        jobs.append(job['id'])
        journal.write_text(json.dumps({'apk':receipt,'devices':by_device,'jobs':jobs},indent=2)+'\n')
        print(device+': '+job['id'],flush=True)
    result=0
    for jid in jobs:
        result=max(result,client.watch(jid))
        client.evidence(jid,str(OUT/jid))
    (OUT/'jobs.json').write_text(json.dumps({'apk':receipt,'devices':by_device,'jobs':jobs,'exit':result},indent=2)+'\n')
    with report.open('a') as log:log.write(json.dumps({'jobs':jobs,'exit':result})+'\n')
    print('Evidence: '+str(OUT),flush=True)
    return result

if __name__=='__main__':
    raise SystemExit(main())
