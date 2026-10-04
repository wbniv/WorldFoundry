#!/usr/bin/env python3
"""Finish background-only installation, authenticating sudo locally if required."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/diagnostics/bomberman-chromecast'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'scripts'))
from wf_device.client import Client

def main():
    report=OUT/'installation.log'
    print('Installation log: '+str(report),flush=True)
    print('Checking coordinator capabilities',flush=True)
    try:
        client=Client()
        capabilities=client.call('capabilities')
    except RuntimeError as error:
        stopped=isinstance(error.__cause__,(FileNotFoundError,ConnectionRefusedError))
        if str(error) != 'Unknown operation' and not stopped:
            raise
        if stopped:
            print('Coordinator socket unavailable; resuming reviewed service deployment',flush=True)
        capabilities={'workflows': [], 'maintenance_drain': False}
    if 'install' not in capabilities['workflows'] or not capabilities.get('maintenance_drain'):
        # Authentication happens in the user's terminal, never in a chat message.
        with report.open('a') as log:
            with subprocess.Popen(['sudo',sys.executable,str(ROOT/'android/bomberman/deploy-coordinator.py')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True) as process:
                for line in process.stdout:
                    print(line,end='',flush=True);log.write(line);log.flush()
                result=process.wait()
        if result:
            return result
        client=Client()
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
