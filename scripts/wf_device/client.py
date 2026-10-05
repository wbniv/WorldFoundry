"""Task/CLI client; job inputs are uploaded, never passed as service filesystem paths."""
import base64
import hashlib
import json
import os
import secrets
import socket
import shutil
import sys
import textwrap
import time
from pathlib import Path
from .store import TERMINAL, selection

class Client:
    def __init__(self, path=None, session_file=None):
        self.path=path or os.environ.get('WF_COORDINATOR_SOCKET','/run/wf-device-coordinator/coordinator.sock')
        identity=os.environ.get('CODEX_THREAD_ID') or os.environ.get('WF_COORDINATOR_SESSION') or 'interactive'
        state=Path(os.environ.get('WF_COORDINATOR_CLIENT_STATE',str(Path.home()/'.local/state/wf-device-coordinator')))
        self.session_file=Path(session_file) if session_file else state/(hashlib.sha256((self.path+'|'+identity).encode()).hexdigest()+'.json')
        self.credentials=None
        if self.session_file.exists():
            self.credentials=json.loads(self.session_file.read_text())
        else:
            self.session_file.parent.mkdir(parents=True,exist_ok=True)
            self.credentials=self.call('register',{'label':identity},authenticate=False)
            # Atomic per-client publication. Session tokens aren't printed or included in receipts.
            temp=self.session_file.with_suffix('.'+str(os.getpid())+'.tmp')
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as out:
                json.dump(self.credentials,out)
            # Concurrent clients need the same identity credentials, not overwrite each other.
            try:
                os.link(temp,self.session_file)
            except FileExistsError:
                self.credentials=json.loads(self.session_file.read_text())
            finally:
                temp.unlink()

    def call(self,method,args=None,authenticate=True):
        request={'method':method,'args':args or {}}
        if authenticate:
            request['credentials']=self.credentials
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(120)
            try:
                sock.connect(self.path)
            except PermissionError as exc:
                raise RuntimeError('Coordinator socket access denied at '+self.path+
                                   '; this may be a sandbox restriction, not a service outage. '
                                   'Retry the same Task command with escalation; no direct ADB fallback') from exc
            except OSError as exc:
                raise RuntimeError('Coordinator connection failed at '+self.path+': '+str(exc)+
                                   '; no direct ADB fallback') from exc
            sock.sendall(json.dumps(request).encode()+b'\n')
            stream=sock.makefile('rb')
            raw=stream.readline(128*1024*1024)
        result=json.loads(raw)
        if not result['ok']:
            if method in {'reserve','release'} and result['error']=='Unknown operation':
                raise RuntimeError('The installed coordinator does not support reservations yet. '
                                   'Run task chromecast:install from your terminal, then retry this command.')
            raise RuntimeError(result['error'])
        return result['result']

    def upload(self,path):
        path=Path(path)
        if path.stat().st_size>32*1024*1024:
            raise ValueError('APK exceeds 32 MiB upload limit')
        return self.call('upload',{'data':base64.b64encode(path.read_bytes()).decode()})['apk']

    def freeze(self,request):
        req=dict(request)
        uploaded={}
        def upload(path):
            key=str(Path(path).resolve())
            if key not in uploaded:
                uploaded[key]=self.upload(path)
            return uploaded[key]
        for key in ('apk','restore_apk'):
            if req.get(key):
                req[key]=upload(req[key])
        if 'variants' in req:
            req['variants']=[dict(v,apk=upload(v['apk'])) for v in req['variants']]
        return req

    def submit(self,request):
        targets=selection(request['device']) if request.get('device') else None
        multiple=targets and (len(targets)>1 or targets==['all'])
        if multiple:
            if request.get('pool') or request.get('_setup') or request.get('address'):
                raise ValueError('Multiple DEVICE cannot share POOL, ADDRESS or pairing setup')
            if not self.call('capabilities').get('device_batches'):
                raise RuntimeError('Coordinator upgrade required for multiple DEVICE; no jobs submitted')
        req=self.freeze(request)
        if multiple:
            req.pop('device')
            # Retry exactly this admission if the socket response is lost. Inputs
            # are already immutable and the service token prevents duplication.
            args={'devices':targets,'request':req,'token':secrets.token_hex(16)}
            try:
                return self.call('submit_batch',args)
            except (OSError, json.JSONDecodeError):
                return self.call('submit_batch',args)
        if targets:
            req['device']=targets[0]
        return self.call('submit',req)

    def watch_batch(self,bid):
        previous=None
        while True:
            batch=self.call('batch',{'batch':bid})
            rows=[[j['target'],j['id'],j['phase'],j['error'] or ''] for j in batch['jobs']]
            if rows!=previous:
                print(bid+'\n'+box_table(['Device','Job','State / phase','Error'],rows),flush=True)
                previous=rows
            self.notifications()
            if batch['state']!='pending':
                return 0 if batch['state']=='completed' else 1
            time.sleep(.5)

    def batch_evidence(self,bid,out):
        batch=self.call('batch',{'batch':bid})
        root=Path(out);root.mkdir(parents=True,exist_ok=True)
        for job in batch['jobs']:
            for value in (job['target'],job['id']):
                if Path(value).name!=value or value in {'.','..'}:
                    raise ValueError('Unsafe batch evidence path')
            destination=root/job['target']/job['id']
            if not destination.resolve().is_relative_to(root.resolve()):
                raise ValueError('Batch evidence escapes output directory')
            self.evidence(job['id'],destination)
        # Do not persist the admission token or session credentials.
        manifest=root/'batch.json'
        if manifest.is_symlink():
            raise ValueError('Unsafe batch manifest path')
        manifest.write_text(json.dumps(batch,indent=2)+'\n')
        return batch

    def watch(self,jid):
        cursor=0
        while True:
            for event in self.call('events',{'cursor':cursor,'job':jid}):
                cursor=event['seq']
                print(f"{jid}: {event['kind']} {json.dumps(event['data'])}",flush=True)
            self.notifications()
            job=self.call('status',{'job':jid})
            if job['state'] in TERMINAL:
                print(f"{jid}: {job['state']}"+((': '+job['error']) if job['error'] else ''),flush=True)
                return 0 if job['state']=='completed' else 1
            time.sleep(.5)

    def notifications(self):
        messages=self.call('inbox')
        for msg in messages:
            print(f"{msg['id']} / {msg['job']} from {msg['sender_label']}: {msg['text']}",flush=True)
        if messages:
            self.call('acknowledge',{'ids':[m['id'] for m in messages]})

    def evidence(self,jid,out):
        result=self.call('evidence',{'job':jid})
        destination=Path(out);destination.mkdir(parents=True,exist_ok=True)
        for name,entry in result['files'].items():
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('Unsafe evidence filename')
            path=destination/name
            path.parent.mkdir(parents=True,exist_ok=True)
            if not path.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Evidence destination escapes output directory')
            if path.exists():
                with path.open('rb') as stream:
                    existing=hashlib.file_digest(stream,'sha256').hexdigest()
                if path.is_symlink() or existing!=entry['sha256']:
                    raise FileExistsError('Conflicting destination file: '+str(path))
                continue
            temp=path.with_name(path.name+'.'+str(os.getpid())+'.download')
            digest=hashlib.sha256();offset=0
            try:
                with temp.open('xb') as stream:
                    while offset<entry['size']:
                        chunk=self.call('artifact',{'job':jid,'name':name,'offset':offset})
                        data=base64.b64decode(chunk['data'],validate=True)
                        if not data or offset+len(data)>entry['size']:
                            raise RuntimeError('Artifact size changed; retry after completion')
                        stream.write(data);digest.update(data);offset+=len(data)
                if digest.hexdigest()!=entry['sha256']:
                    raise RuntimeError('Evidence checksum mismatch')
                os.link(temp,path)
            finally:
                temp.unlink(missing_ok=True)
        print(f"{jid}: {result['job']['state']}; verified {len(result['files'])} artifacts -> {destination.resolve()}")
        return result


def box_table(headers, rows):
    """Wrap cells to the terminal width without dropping IDs or status text."""
    rows=[[str(value) for value in row] for row in rows]
    widths=[max(len(header),max((len(line) for row in rows for line in row[i].splitlines()),default=0))
            for i,header in enumerate(headers)]
    budget=max(40,shutil.get_terminal_size((120,24)).columns)-3*len(headers)-1
    minimum=[max(len(header),6) for header in headers]
    while sum(widths)>budget:
        candidates=[i for i,width in enumerate(widths) if width>minimum[i]]
        if not candidates:break
        widest=max(candidates,key=lambda i:widths[i])
        widths[widest]-=1
    def border(left,junction,right):
        return left+junction.join('═'*(width+2) for width in widths)+right
    def line(cells):
        return '║'+'║'.join(' '+cell.ljust(width)+' ' for cell,width in zip(cells,widths))+'║'
    lines=[border('╔','╦','╗'),line(headers),border('╠','╬','╣')]
    for index,row in enumerate(rows):
        wrapped=[sum((textwrap.wrap(part,width=width,break_on_hyphens=False) or ['']
                      for part in cell.splitlines() or ['']),[]) for cell,width in zip(row,widths)]
        for offset in range(max(map(len,wrapped))):
            lines.append(line([cell[offset] if offset<len(cell) else '' for cell in wrapped]))
        if index<len(rows)-1:lines.append(border('╠','╬','╣'))
    lines.append(border('╚','╩','╝'))
    return '\n'.join(lines)


def snapshot_text(snapshot):
    lines=[f"Snapshot {time.strftime('%Y-%m-%d %H:%M:%S %z',time.localtime(snapshot['time']))}; revision {snapshot['revision']}; connected"]
    if snapshot.get('maintenance'):
        lines.append('Maintenance: grants paused; '+snapshot['maintenance']['reason'])
    devices=[]
    for device in snapshot['devices']:
        active=[j for j in snapshot['jobs'] if j['device']==device['id'] and j['state']=='running']
        owner='\n'.join(j['label'] for j in active) or 'unowned'
        job_phase='\n'.join(j['id']+'\n'+j['phase'] for j in active) or '—'
        if device.get('reservation'):
            r=device['reservation']
            owner=f"{r['state']}: {r['label']}\n{r['reason']}"+(('\nActive: '+owner) if active else '')
        devices.append([device['id'],device['health'],device.get('model','unknown'),owner,job_phase,', '.join(device.get('abis',[])) or '—'])
    lines+=['','Devices',box_table(['Device','Health','Model','Owner / reservation','Job / phase','ABI'],devices or [['None','—','—','—','—','—']])]
    waiting=[]
    for job in snapshot['jobs']:
        if job['state']=='queued':
            req=job['request'];selector=req.get('device') or 'pool:'+req['pool']
            waiting.append([job['id'],job['label'],selector,', '.join(job['eligible']) or 'None'])
    lines+=['','Waiting jobs',box_table(['Job','Owner','Target','Eligible devices'],waiting or [['None','—','—','—']])]
    lines.append('Pool positions depend on eligibility and release order.')
    return '\n'.join(lines)


def task_command(command):
    client=Client()
    args={k:os.environ.get('WF_CC_'+k.upper(),'') for k in ('device','pool','job','batch','out','text','workflow','app','scene','apk','require_abi','warmup','runs','duration','watch','validator','async','recipe','trace','pairing_endpoint','address','method','reason')}
    args={k:v for k,v in args.items() if v!=''}
    if args.get('job') and args.get('batch'):
        raise ValueError('Specify JOB or BATCH, not both')
    if (args.get('job') or args.get('batch')) and (args.get('device') or args.get('pool')):
        raise ValueError('JOB/BATCH cannot be combined with DEVICE/POOL')
    if args.get('device') and args.get('pool'):
        raise ValueError('Specify DEVICE or POOL, not both')
    if args.get('batch'):
        if command not in {'watch','status','evidence','cancel'}:
            raise ValueError('BATCH supports watch, status, evidence and cancel')
        bid=args['batch']
        if command=='watch':return client.watch_batch(bid)
        if command=='evidence':client.batch_evidence(bid,args['out']);return 0
        if command=='cancel':
            client.call('cancel_batch',{'batch':bid})
            # Completed successes remain successful; cancellation is successful
            # when no child is left queued/running and none has a cleanup failure.
            client.watch_batch(bid)
            batch=client.call('batch',{'batch':bid})
            return 0 if all(j['state'] in {'cancelled','completed','superseded'} for j in batch['jobs']) else 1
        print(json.dumps(client.call('batch',{'batch':bid}),indent=2));return 0
    if command in {'check','profile','record','submit','readd','capture'}:
        keys={'device','pool','require_abi','app','scene','apk','warmup','runs','duration','validator','trace','address','method'}
        req={k:v for k,v in args.items() if k in keys}
        req['workflow']=args.get('workflow','check') if command=='submit' else command
        for key in ('warmup','duration'):
            if key in req:
                req[key]=float(req[key])
        if 'runs' in req:
            req['runs']=int(req['runs'])
        if args.get('recipe'):
            if command!='submit':
                raise ValueError('RECIPE is supported by submit only')
            recipe=json.loads(Path(args['recipe']).read_text())
            if not isinstance(recipe,dict):
                raise ValueError('Recipe must be a JSON request object')
            for key in ('device','pool'):
                if key in recipe and (args.get('device') or args.get('pool')) and recipe[key]!=args.get(key):
                    raise ValueError('Recipe target conflicts with command selection')
            req.update(recipe)
        if req['workflow'] not in {'readd','capture'} and not req.get('apk'):
            app=req.get('app','aquarium');req['app']=app
            repo=Path(os.environ.get('WF_COORDINATOR_REPO',str(Path(__file__).resolve().parents[2])))
            if app=='bomberman':
                receipt=json.loads((repo/'android/bomberman/build/build-receipt.json').read_text())
                req['apk']=receipt['apk']
                if hashlib.sha256(Path(req['apk']).read_bytes()).hexdigest()!=receipt['sha256']:
                    raise ValueError('Latest Bomberman build receipt does not match APK')
            else:
                req['apk']=str(repo/f'android/app/build/outputs/apk/{app}/release/worldfoundry-{app}-release.apk')
        if args.get('pairing_endpoint'):
            if selection(req.get('device'))==['all'] or len(selection(req.get('device')))!=1:
                raise ValueError('Pairing requires exactly one DEVICE')
            if command!='readd' or not sys.stdin.isatty():
                raise ValueError('Pairing requires readd in an interactive terminal; never pass the code as an argument')
            import getpass
            req['_setup']={'endpoint':args['pairing_endpoint'],'code':getpass.getpass('Fresh TV pairing code: ')}
        job=client.submit(req)
        print(f"Accepted {job['id']}: {job['state']}; {req['workflow']}",flush=True)
        batch=job['id'].startswith('B-')
        if batch:
            for child in job['jobs']:
                print(child['target']+': '+child['id'],flush=True)
        print(f"Follow: task chromecast:watch {'BATCH' if batch else 'JOB'}={job['id']}",flush=True)
        if command=='submit' or args.get('async')=='true':
            return 0
        result=client.watch_batch(job['id']) if batch else client.watch(job['id'])
        if command=='capture' and result==0:
            destination=args.get('out') or str(Path('docs/diagnostics')/('chromecast-capture-'+job['id']))
            if batch:client.batch_evidence(job['id'],destination)
            else:client.evidence(job['id'],destination)
            print('Capture evidence: '+str(Path(destination).resolve()),flush=True)
        return result
    if command in {'reserve','release'}:
        if not args.get('device') or args.get('pool'):
            raise ValueError('Reserve/release requires DEVICE, not POOL')
        targets=selection(args['device'])
        multiple=len(targets)>1 or targets==['all']
        if multiple and not client.call('capabilities').get('device_batches'):
            raise RuntimeError('Coordinator upgrade required for multiple DEVICE')
        request={'devices':targets} if multiple else {'device':targets[0]}
        if command=='reserve':
            request['reason']=args.get('reason','Personal use')
        results=client.call(command+'_many' if multiple else command,request)
        for result in results if multiple else [results]:
            if command=='reserve':
                print(f"{result['device']}: {result['state']}; {result['reason']}; retained until you release it")
                if result['state']=='waiting-for-cleanup':
                    print('An active job is finishing; wait for status to show reserved before using the device.')
            else:
                print(f"{result['device']}: "+('released; queued jobs may now start' if result['released'] else 'no reservation to release'))
    elif command=='devices':
        for d in client.call('devices',{'device':args['device']} if args.get('device') else {}):
            print(f"{d['id']}: {d['health']}; {d.get('model')}; serial {d['serial']}; Android {d.get('android')}; ABI {','.join(d.get('abis',[]))}; endpoint {d.get('endpoint')}; pools {','.join(d.get('pools',[]))}")
    elif command in {'queue','status'}:
        query={k:args[k] for k in ('device','pool','job') if k in args}
        if command=='queue' and query.get('job'):
            raise ValueError('Use status JOB=... for one job')
        previous=None
        while True:
            result=client.call(command,query)
            if result!=previous:
                print(json.dumps(result,indent=2) if query.get('job') else snapshot_text(result),flush=True)
                previous=result
            client.notifications()
            if args.get('watch')!='true':
                break
            time.sleep(1)
    elif command=='watch':
        return client.watch(args['job'])
    elif command=='evidence':
        client.evidence(args['job'],args['out'])
    elif command=='message':
        print(json.dumps(client.call('message',{'job':args['job'],'text':args['text']})))
    elif command=='cancel':
        job=client.call('cancel',{'job':args['job']})
        if job['state']=='running':
            client.watch(job['id'])
            return 0 if client.call('status',{'job':job['id']})['state']=='cancelled' else 1
        else:
            print(job['id']+': '+job['state'])
    else:
        raise ValueError('Unknown Task operation')
    return 0
