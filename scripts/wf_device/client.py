"""Task/CLI client; job inputs are uploaded, never passed as service filesystem paths."""
import base64
import hashlib
import json
import os
import socket
import shutil
import sys
import textwrap
import time
from pathlib import Path
from .store import TERMINAL

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

    def submit(self,request):
        req=dict(request)
        for key in ('apk','restore_apk'):
            if req.get(key):
                req[key]=self.upload(req[key])
        if 'variants' in req:
            req['variants']=[dict(v,apk=self.upload(v['apk'])) for v in req['variants']]
        return self.call('submit',req)

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
    args={k:os.environ.get('WF_CC_'+k.upper(),'') for k in ('device','pool','job','out','text','workflow','app','scene','apk','require_abi','warmup','runs','duration','watch','validator','async','recipe','trace','pairing_endpoint','address','reason')}
    args={k:v for k,v in args.items() if v!=''}
    if command in {'check','profile','record','submit','readd'}:
        keys={'device','pool','require_abi','app','scene','apk','warmup','runs','duration','validator','trace','address'}
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
            req.update(recipe)
        if req['workflow'] not in {'readd'} and not req.get('apk'):
            app=req.get('app','aquarium');req['app']=app
            req['apk']=str(Path(os.environ.get('WF_COORDINATOR_REPO',str(Path(__file__).resolve().parents[2])))/f'android/app/build/outputs/apk/{app}/release/worldfoundry-{app}-release.apk')
        if args.get('pairing_endpoint'):
            if command!='readd' or not sys.stdin.isatty():
                raise ValueError('Pairing requires readd in an interactive terminal; never pass the code as an argument')
            import getpass
            req['_setup']={'endpoint':args['pairing_endpoint'],'code':getpass.getpass('Fresh TV pairing code: ')}
        job=client.submit(req)
        print(f"Accepted {job['id']}: {job['state']}; {req['workflow']}",flush=True)
        print(f"Follow: task chromecast:watch JOB={job['id']}",flush=True)
        if command=='submit' or args.get('async')=='true':
            return 0
        result=client.watch(job['id'])
        return result
    if command in {'reserve','release'}:
        if not args.get('device') or args.get('pool'):
            raise ValueError('Reserve/release requires DEVICE, not POOL')
        request={'device':args['device']}
        if command=='reserve':
            request['reason']=args.get('reason','Personal use')
        result=client.call(command,request)
        if command=='reserve':
            print(f"{result['device']}: {result['state']}; {result['reason']}; retained until you release it")
            if result['state']=='waiting-for-cleanup':
                print('An active job is finishing; wait for status to show reserved before using the device.')
        else:
            print(f"{result['device']}: "+('released; queued jobs may now start' if result['released'] else 'no reservation to release'))
    elif command=='devices':
        for d in client.call('devices'):
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
