"""Authenticated Unix socket service, durable scheduler and immutable input upload."""
import base64
import fcntl
import hashlib
import io
import ipaddress
import json
import os
import secrets
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from .store import Store, selection

MAX_APK = 32*1024*1024
MAX_REQUEST = 48*1024*1024
WORKFLOWS = {'check','profile','record','variant-benchmark','readd','capture','install'}
REQUEST_KEYS = {'device','pool','require_abi','workflow','app','scene','warmup','duration','runs',
                'apk','restore_apk','variants','validator','trace','address','method'}


def validate_request(request, scenes):
    if not isinstance(request,dict) or set(request)-REQUEST_KEYS:
        raise ValueError('Unknown workflow request fields')
    if bool(request.get('device')) == bool(request.get('pool')):
        raise ValueError('Specify exactly one DEVICE or POOL')
    if request.get('workflow') not in WORKFLOWS:
        raise ValueError('Unregistered workflow')
    if request['workflow']=='install' and set(request)-{'device','pool','workflow','app','apk','require_abi'}:
        raise ValueError('Install accepts only target, app, APK and ABI; it never launches or sends input')
    if request['workflow']=='capture' and set(request)-{'device','pool','workflow','method'}:
        raise ValueError('Capture accepts only DEVICE or POOL; it preserves the current display')
    if 'method' in request:
        from .capture import METHODS
        if request['workflow']!='capture' or request['method'] not in METHODS:
            raise ValueError('METHOD must select a reviewed capture backend')
    from .workflows import APPS
    if request['workflow'] not in {'readd','capture'} and request.get('app') not in APPS:
        raise ValueError('Unknown app')
    if request.get('scene') and (request.get('app')!='aquarium' or request['scene'] not in scenes):
        raise ValueError('Unknown scene for this app')
    if request.get('trace') not in (None,'idle','swarm','all','plants','school'):
        raise ValueError('Unknown reviewed trace')
    if request.get('trace')=='school' and request['workflow']!='record':
        raise ValueError('School trace is a recording workflow')
    if request.get('validator') not in (None,'menu-back','poke-resume','prime-study'):
        raise ValueError('Unknown validator')
    if request.get('validator') == 'prime-study' and (request.get('app') != 'primes' or request['workflow'] != 'check'):
        raise ValueError('Prime study validator requires a Primes check workflow')
    for field, lower, upper in [('warmup',0,300),('duration',.05,180),('runs',1,10)]:
        if field in request and (isinstance(request[field],bool) or not isinstance(request[field],(int,float))
                                 or not lower<=request[field]<=upper):
            raise ValueError('Invalid '+field)
    if 'runs' in request and not isinstance(request['runs'],int):
        raise ValueError('RUNS must be an integer')
    if request['workflow']=='record' and int(request.get('duration',10))!=request.get('duration',10):
        raise ValueError('Recording duration must be whole seconds')
    if request['workflow']=='readd' and request.get('pool'):
        raise ValueError('Readd requires an explicit DEVICE')
    if 'address' in request:
        address=ipaddress.ip_address(request['address'])
        if request['workflow']!='readd' or address.version!=4 or not address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
            raise ValueError('ADDRESS requires readd and a private LAN IPv4 address')
    if request['workflow']=='variant-benchmark':
        variants=request.get('variants')
        if not isinstance(variants,list) or not 1<=len(variants)<=12 or not request.get('restore_apk'):
            raise ValueError('Variant benchmark requires 1..12 variants and restore APK')
        labels=[]
        import re
        for variant in variants:
            if not {'label','apk'}<=set(variant) or set(variant)-{'label','apk','runs','warmup'} or not re.fullmatch('[A-Za-z0-9_-]{1,40}',variant['label']):
                raise ValueError('Invalid variant')
            for key,low,high in [('runs',1,10),('warmup',0,300)]:
                if key in variant and (not isinstance(variant[key],(int,float)) or not low<=variant[key]<=high or (key=='runs' and not isinstance(variant[key],int))):
                    raise ValueError('Invalid variant '+key)
            labels.append(variant['label'])
        if len(set(labels))!=len(labels):
            raise ValueError('Duplicate variant labels')
    return request

class Coordinator:
    def __init__(self, config):
        self.config=config
        self.store=Store(config['state'],config['devices'])
        self.children={}
        self.setup={}
        self.setup_lock=threading.Lock()
        self.stop_event=threading.Event()
        self.lock=open(self.store.root/'locks'/'service.lock','a')
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Never grant a replacement after uncertain broker/worker death.
        with self.store.db() as db:
            orphaned=list(db.execute("SELECT id,device FROM jobs WHERE state='running'"))
            for row in orphaned:
                db.execute("UPDATE devices SET health='recovery-required' WHERE id=?",(row['device'],))
                # Live workers retain leases and lock. Dead workers remain gated for readd.
                job=self.store.job(row['id'])
                pid=job['worker_pid']
                if not pid or not Path(f'/proc/{pid}').exists():
                    db.execute("UPDATE jobs SET state='recovery-required',phase='recovery-required',error=? WHERE id=?",('Broker restart during '+job['phase']+': uncertain worker completion',row['id']))
        self.thread=threading.Thread(target=self.schedule,daemon=True)

    def schedule(self):
        while not self.stop_event.wait(.1):
            try:
                for jid,p in list(self.children.items()):
                    if p.poll() is not None:
                        job=self.store.job(jid)
                        if job['state']=='running':
                            self.store.finish(jid,'recovery-required','Worker exited during '+job['phase']+' without verified cleanup',health='recovery-required')
                        self.children.pop(jid)
                for jid in self.store.claim(exclude=set(self.children)):
                    log=open(self.store.root/'evidence'/(jid+'.worker.log'),'ab')
                    try:
                        with self.setup_lock:
                            setup=self.setup.pop(jid,{})
                        p=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'chromecast.py'),
                                            'worker','--config',self.config['_path'],'--job',jid,'--setup-stdin'],
                                           stdout=log,stderr=log,stdin=subprocess.PIPE,start_new_session=True)
                        p.stdin.write(json.dumps(setup).encode()+b'\n');p.stdin.close()
                        self.children[jid]=p
                    except Exception as exc:
                        self.store.finish(jid,'recovery-required',str(exc),health='recovery-required')
                    finally:
                        log.close()
            except Exception as exc:
                print('scheduler error:',exc,file=sys.stderr,flush=True)

    def upload(self, encoded):
        if not isinstance(encoded,str) or len(encoded)>MAX_APK*4//3+8:
            raise ValueError('APK upload too large')
        data=base64.b64decode(encoded,validate=True)
        if len(data)>MAX_APK:
            raise ValueError('APK upload too large')
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            if 'AndroidManifest.xml' not in bundle.namelist():
                raise ValueError('Input is not an APK')
            if sum(n.file_size for n in bundle.infolist())>256*1024*1024:
                raise ValueError('APK expanded size exceeds limit')
        digest=hashlib.sha256(data).hexdigest()
        path=self.store.root/'inputs'/(digest+'.apk')
        if not path.exists():
            temp=path.with_suffix('.'+secrets.token_hex(8)+'.tmp')
            with temp.open('xb') as f:
                f.write(data);f.flush();os.fsync(f.fileno())
            os.chmod(temp,0o400)
            os.replace(temp,path)
        return {'apk':path.name,'sha256':digest}

    def dispatch(self, uid, call):
        if uid not in self.config['allowed_uids']:
            raise PermissionError('Peer UID is not authorized')
        method=call.get('method')
        args=call.get('args',{})
        if method=='register':
            return self.store.register(uid,args['label'])
        owner=self.store.authenticate(uid,call.get('credentials',{}))
        if method=='capabilities':
            return {'workflows': sorted(WORKFLOWS), 'maintenance_drain': True,
                    'device_batches': True, 'launcher_verification': True}
        if method=='upload':
            return self.upload(args['data'])
        if method=='submit_batch':
            if set(args) != {'devices','request','token'} or not isinstance(args['request'],dict):
                raise ValueError('Batch requires devices, request and token')
            req = dict(args['request'])
            if any(k in req for k in ('device','pool','_setup','address')):
                raise ValueError('Batch request must not override selection or share pairing/address setup')
            validate_request(dict(req, device='batch-validation'), self.config['scenes'])
            self.validate_inputs(req)
            return self.store.submit_batch(owner, args['devices'], req, args['token'])
        if method=='batch':
            return self.store.batch(args['batch'])
        if method=='cancel_batch':
            return self.store.cancel_batch(owner, args['batch'])
        if method in {'reserve_many','release_many'}:
            allowed = {'devices','reason'} if method=='reserve_many' else {'devices'}
            if set(args)-allowed or 'devices' not in args:
                raise ValueError('Invalid multi-device reservation request')
            if method=='reserve_many' and not isinstance(args.get('reason','Personal use'),str):
                raise ValueError('Reservation reason must be text')
            return self.store.reserve_many(owner, args['devices'], args.get('reason','Personal use') if method=='reserve_many' else None)
        if method=='submit':
            args=dict(args)
            setup=args.pop('_setup',None)
            req=validate_request(args,self.config['scenes'])
            if 'address' in req:
                device=next((d for d in self.store.devices() if d['id']==req.get('device')),None)
                if not device or device.get('transport')!='legacy-tcp':
                    raise ValueError('ADDRESS is a reconnect hint for a registered legacy TCP device')
                networks=self.config.get('discovery_networks',[device['endpoint'].rsplit(':',1)[0]+'/24'])
                if not any(ipaddress.ip_address(req['address']) in ipaddress.ip_network(n,strict=False) for n in networks):
                    raise ValueError('ADDRESS is outside the registered discovery networks')
            if setup:
                import re
                if req['workflow']!='readd' or set(setup)!={'endpoint','code'} or not re.fullmatch(r'[0-9]{6}',str(setup['code'])):
                    raise ValueError('Invalid secure pairing setup')
                device=next((d for d in self.store.devices() if d['id']==req.get('device')),None)
                host,separator,port=setup['endpoint'].rpartition(':')
                if not device or device['transport']!='tls' or host!=device['endpoint'].rsplit(':',1)[0] or not separator or not port.isdigit() or not 1<=int(port)<=65535:
                    raise ValueError('Pairing endpoint does not match the registered TLS device')
            self.validate_inputs(req)
            with self.setup_lock:
                job=self.store.submit(owner,req)
                if setup:self.setup[job['id']]=setup
            return job
        if method=='devices':
            devices = self.store.devices()
            if args.get('device'):
                with self.store.db() as db:
                    selected = self.store.resolve_targets(db, args['device'])
                devices = [d for d in devices if d['id'] in selected]
            return devices
        if method in {'reserve','release'}:
            if set(args) - ({'device','reason'} if method=='reserve' else {'device'}) or not isinstance(args.get('device'),str):
                raise ValueError('Reservation operations require DEVICE; reserve also accepts REASON')
            if method=='reserve':
                return self.store.reserve(owner,args['device'],args.get('reason','Personal use'))
            return self.store.release(owner,args['device'])
        if method=='queue':
            return self.snapshot(args)
        if method=='status':
            return self.store.job(args['job']) if args.get('job') else self.snapshot(args)
        if method=='events':
            return self.store.events(int(args.get('cursor',0)),args.get('job'))
        if method=='cancel':
            return self.store.cancel(owner,args['job'])
        if method=='message':
            return self.store.message(owner,args['job'],args['text'])
        if method=='inbox':
            return self.store.inbox(owner)
        if method=='acknowledge':
            return self.store.acknowledge(owner,args['ids'])
        if method=='evidence':
            job=self.store.job(args['job'])
            files={}
            folder=self.store.root/'evidence'/job['id']
            for path in folder.rglob('*'):
                if path.is_file() and not path.is_symlink():
                    with path.open('rb') as stream:
                        digest=hashlib.file_digest(stream,'sha256').hexdigest()
                    files[str(path.relative_to(folder))]={'size':path.stat().st_size,'sha256':digest}
            return {'job':job,'files':files}
        if method=='artifact':
            job=self.store.job(args['job'])
            name=Path(args['name']);offset=args.get('offset',0)
            if name.is_absolute() or '..' in name.parts or not isinstance(offset,int) or offset<0:
                raise ValueError('Unsafe artifact request')
            folder=self.store.root/'evidence'/job['id'];path=folder/name
            if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Unsafe artifact path')
            with path.open('rb') as stream:
                stream.seek(offset);data=stream.read(1024*1024)
            return {'data':base64.b64encode(data).decode(),'offset':offset,'bytes':len(data)}
        raise ValueError('Unknown operation')

    def validate_inputs(self, req):
        import re
        references=[req.get('apk'),req.get('restore_apk')]+[v['apk'] for v in req.get('variants',[])]
        if not self.config.get('fake') and req['workflow'] not in {'readd','capture'} and not req.get('apk'):
            raise ValueError('An immutable APK is required')
        for name in filter(None,references):
            if not isinstance(name,str) or not re.fullmatch(r'[a-f0-9]{64}\.apk',name) or not (self.store.root/'inputs'/name).is_file():
                raise ValueError('Unknown staged input')

    def snapshot(self, args):
        if args.get('device') and args.get('pool'):
            raise ValueError('Specify DEVICE or POOL, not both')
        result = self.store.snapshot(pool=args.get('pool'))
        if args.get('device'):
            with self.store.db() as db:
                targets = self.store.resolve_targets(db, args['device'])
            result['devices'] = [d for d in result['devices'] if d['id'] in targets]
            result['jobs'] = [j for j in result['jobs'] if j['device'] in targets or set(j['eligible']).intersection(targets)]
            for job in result['jobs']:
                job['eligible'] = [d for d in job['eligible'] if d in targets]
            result['batches'] = [b for b in result['batches'] if set(b['targets']).intersection(targets)]
        return result

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(30)
        uid=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
        try:
            line=self.rfile.readline(MAX_REQUEST+1)
            if len(line)>MAX_REQUEST or not line.endswith(b'\n'):
                raise ValueError('Oversized or incomplete request')
            data=self.server.coordinator.dispatch(uid,json.loads(line))
            response={'ok':True,'result':data}
        except Exception as exc:
            response={'ok':False,'error':str(exc),'type':type(exc).__name__}
        self.wfile.write(json.dumps(response).encode()+b'\n')

class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads=True


def serve(config):
    coordinator=Coordinator(config)
    path=Path(config['socket']);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        path.unlink()
    server=Server(str(path),Handler)
    server.coordinator=coordinator
    os.chmod(path,0o660)
    coordinator.thread.start()
    dashboard=None
    if config.get("dashboard_port"):
        from .dashboard import start
        dashboard=start(coordinator.store,config["dashboard_port"],config.get("enforcement","not verified"))
    try:
        server.serve_forever(poll_interval=.2)
    finally:
        coordinator.stop_event.set()
        if dashboard:
            dashboard.shutdown()
        # Workers own locks/leases and drain cleanup even if this client/service exits.
        server.server_close()
        coordinator.lock.close()
