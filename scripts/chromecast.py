#!/usr/bin/env python3
"""World Foundry APK defaults and the installed shared coordinator client."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def prepare_task_defaults(operation):
    if operation not in {'submit','check','profile','record'}:
        return
    workflow=os.environ.get('WF_CC_WORKFLOW') or ('check' if operation=='submit' else operation)
    request={'workflow':workflow,'app':os.environ.get('WF_CC_APP') or 'aquarium',
             'apk':os.environ.get('WF_CC_APK') or ''}
    recipe=os.environ.get('WF_CC_RECIPE')
    if recipe:
        data=json.loads(Path(recipe).read_text())
        if not isinstance(data,dict):raise ValueError('Recipe must be a JSON request object')
        request.update(data)
    if request['workflow'] in {'readd','capture'} or request.get('apk'):
        return
    app=request['app']
    if app in {'bomberman','primes'}:
        folder='prime-numbers' if app=='primes' else 'bomberman'
        receipt=json.loads((ROOT/f'android/{folder}/build/build-receipt.json').read_text())
        apk=Path(receipt['apk'])
        if hashlib.sha256(apk.read_bytes()).hexdigest()!=receipt['sha256']:
            raise ValueError('Latest '+app+' build receipt does not match APK')
    else:
        apk=ROOT/f'android/app/build/outputs/apk/{app}/release/worldfoundry-{app}-release.apk'
    os.environ['WF_CC_APK']=str(apk)
    if not os.environ.get('WF_CC_APP'):os.environ['WF_CC_APP']=app


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if len(args)!=2 or args[0]!='task':
        raise ValueError('Use task chromecast:*; service administration now belongs to /home/will/chromecast-coordinator')
    prepare_task_defaults(args[1])
    from wf_device.client import task_command
    return task_command(args[1])


if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:
        print('Detached; submitted jobs retain their ownership and cleanup policy.',file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print('chromecast: '+str(error),file=sys.stderr)
        raise SystemExit(1)
