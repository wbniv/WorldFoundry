"""Behavior tests across real client/service/worker processes, with fake hardware."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from wf_device.client import Client
from wf_device.service import Coordinator, validate_request
from wf_device.store import Store, TERMINAL
from wf_device.integration import hook_decision


def config(tmp_path):
    return {'state':str(tmp_path/'state'),'socket':str(tmp_path/'service.sock'),'allowed_uids':[os.getuid()],
            'fake':True,'scenes':['jellyfish'],
            'devices':[{'id':'d1','serial':'serial1','health':'ready','enrolled':True,'abis':['arm32'],'pools':['test']},
                       {'id':'d2','serial':'serial2','health':'ready','enrolled':True,'abis':['arm64'],'pools':['test']}]}

@pytest.fixture
def service(tmp_path):
    cfg=config(tmp_path);path=tmp_path/'config.json';path.write_text(json.dumps(cfg))
    p=subprocess.Popen([sys.executable,str(ROOT/'scripts/chromecast.py'),'serve','--config',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    deadline=time.monotonic()+5
    while not Path(cfg['socket']).exists() and p.poll() is None and time.monotonic()<deadline:
        time.sleep(.02)
    if not Path(cfg['socket']).exists():
        p.terminate();out,err=p.communicate(timeout=5)
        pytest.fail(err.decode()+out.decode())
    a=Client(cfg['socket'],tmp_path/'a.json');b=Client(cfg['socket'],tmp_path/'b.json')
    yield cfg,p,a,b
    # Cancel owned work through the authenticated API; wait for worker cleanup.
    for client in (a,b):
        for job in client.call('queue')['jobs']:
            try: client.call('cancel',{'job':job['id']})
            except RuntimeError: pass
    deadline=time.monotonic()+5
    while a.call('queue')['jobs'] and time.monotonic()<deadline:
        time.sleep(.03)
    p.terminate();p.communicate(timeout=5)


def wait(client,jid):
    deadline=time.monotonic()+7
    while time.monotonic()<deadline:
        job=client.call('status',{'job':jid})
        if job['state'] in TERMINAL:
            return job
        time.sleep(.03)
    raise AssertionError('Job did not terminate')


def submit(client,device=None,pool=None,duration=.2,**kwargs):
    return client.call('submit',dict({'workflow':'check','app':'aquarium','duration':duration},
                                   **({'device':device} if device else {'pool':pool}),**kwargs))['id']


def test_reservation_blocks_fixed_jobs_and_routes_pool_to_other_device(service):
    _,_,a,b=service
    reservation=a.call('reserve',{'device':'d2','reason':'Watching TV'})
    assert reservation['state']=='reserved'
    fixed=submit(b,device='d2')
    pooled=submit(b,pool='test')
    assert wait(b,pooled)['device']=='d1'
    assert b.call('status',{'job':fixed})['state']=='queued'
    snapshot=b.call('queue')
    assert next(d for d in snapshot['devices'] if d['id']=='d2')['reservation']['reason']=='Watching TV'
    a.call('release',{'device':'d2'})
    assert wait(b,fixed)['state']=='completed'


def test_reservation_waits_for_active_cleanup_and_survives_store_restart(service):
    cfg,_,a,b=service
    active=submit(b,device='d2',duration=.6)
    deadline=time.monotonic()+3
    while b.call('status',{'job':active})['state']=='queued' and time.monotonic()<deadline:
        time.sleep(.02)
    assert a.call('reserve',{'device':'d2'})['state']=='waiting-for-cleanup'
    queued=submit(b,device='d2')
    assert wait(b,active)['state']=='completed'
    reopened=Store(cfg['state'])
    reservation=next(d for d in reopened.devices() if d['id']=='d2')['reservation']
    assert reservation['state']=='reserved'
    assert b.call('status',{'job':queued})['state']=='queued'
    a.call('release',{'device':'d2'})
    assert wait(b,queued)['state']=='completed'


def test_reservation_owner_validation_and_idempotence(service):
    _,_,a,b=service
    initial=a.call('reserve',{'device':'d1'})
    for method in ('reserve','release'):
        with pytest.raises(RuntimeError,match='owner'):
            b.call(method,{'device':'d1'})
    changed=a.call('reserve',{'device':'d1','reason':'Movie'})
    assert changed['created']==initial['created'] and changed['reason']=='Movie'
    for request in ({'device':'missing'},{'device':'d2','reason':''},{'device':'d2','reason':'x'*201},{'pool':'test'}):
        with pytest.raises(RuntimeError):
            a.call('reserve',request)
    assert a.call('release',{'device':'d1'})['released']
    assert not a.call('release',{'device':'d1'})['released']


def test_reservation_task_commands(service,tmp_path):
    cfg,_,_,_=service
    env=dict(os.environ,WF_COORDINATOR_SOCKET=cfg['socket'],WF_COORDINATOR_CLIENT_STATE=str(tmp_path/'task-reserver'))
    for operation in ('reserve','release'):
        result=subprocess.run(['task','chromecast:'+operation,'DEVICE=d2','REASON=Watching TV'],
                              cwd=ROOT,env=env,text=True,capture_output=True,timeout=10)
        assert result.returncode==0,result.stderr
        assert ('reserved; Watching TV' if operation=='reserve' else 'released; queued jobs') in result.stdout
    Store(cfg['state'],[{'id':f'chromecast-test-0{n}','health':'ready'} for n in (1,2)])
    for n in (1,2):
        for operation in ('reserve','release'):
            result=subprocess.run(['task',f'cast{n}:'+operation,'REASON=Watching TV'],
                                  cwd=ROOT,env=env,text=True,capture_output=True,timeout=10)
            assert result.returncode==0,result.stderr
            assert f'chromecast-test-0{n}:' in result.stdout
            assert ('reserved; Watching TV' if operation=='reserve' else 'released; queued jobs') in result.stdout


def test_per_device_fifo_and_parallel_devices(service):
    cfg,_,a,b=service
    first=submit(a,device='d1',duration=.5)
    second=submit(b,device='d1',duration=.2)
    parallel=submit(b,device='d2',duration=.2)
    x,y,z=[wait(a,j) for j in (first,second,parallel)]
    assert x['state']==y['state']==z['state']=='completed'
    assert x['finished']<=y['started']
    assert z['started']<x['finished']
    assert x['generation']<y['generation']


def test_pool_eligibility_does_not_block_other_device(service):
    _,_,a,b=service
    busy=submit(a,device='d1',duration=.6)
    incompatible=submit(b,pool='test',require_abi='arm32',duration=.1)
    runnable=submit(b,pool='test',require_abi='arm64',duration=.1)
    x=wait(a,runnable);y=wait(a,busy);z=wait(a,incompatible)
    assert x['device']=='d2' and x['finished']<y['finished']
    assert z['device']=='d1' and z['started']>=y['finished']


def test_oldest_pool_request_precedes_new_fixed_request(service):
    _,_,a,b=service
    first=submit(a,device='d1',duration=.5)
    pool=submit(b,pool='test',require_abi='arm32',duration=.1)
    fixed=submit(a,device='d1',duration=.1)
    x,y,z=[wait(a,j) for j in (first,pool,fixed)]
    assert x['finished']<=y['started'] and y['finished']<=z['started']


def test_cancel_waiter_and_owner_isolation(service):
    _,_,a,b=service
    first=submit(a,device='d1',duration=.5)
    waiting=submit(b,device='d1',duration=.1)
    with pytest.raises(RuntimeError,match='authenticated owner'):
        b.call('cancel',{'job':first})
    b.call('cancel',{'job':waiting})
    assert wait(a,waiting)['state']=='cancelled'
    assert wait(a,first)['state']=='completed'


def test_active_cancel_waits_for_cleanup_before_handoff(service):
    _,_,a,b=service
    first=submit(a,device='d1',duration=2)
    deadline=time.monotonic()+3
    while a.call('status',{'job':first})['state']!='running' and time.monotonic()<deadline: time.sleep(.02)
    nextjob=submit(b,device='d1',duration=.1)
    a.call('cancel',{'job':first})
    x,y=wait(a,first),wait(a,nextjob)
    assert x['state']=='cancelled' and x['finished']<=y['started']


def test_messages_ack_once_without_changing_lease(service):
    _,_,a,b=service
    jid=submit(a,device='d1',duration=.8)
    mid=b.call('message',{'job':jid,'text':'Hello "literal" $(do not execute)'})['id']
    messages=a.call('inbox');assert messages[0]['id']==mid
    a.call('acknowledge',{'ids':[mid]});a.call('acknowledge',{'ids':[mid]})
    assert a.call('inbox')==[]
    assert len([e for e in a.call('events',{'job':jid}) if e['kind']=='message-delivered'])==1
    assert wait(a,jid)['state']=='completed'


def test_authentication_rejects_forged_token(service):
    _,_,a,_=service
    old=a.credentials;a.credentials=dict(old,token='forged')
    with pytest.raises(RuntimeError,match='credentials'):a.call('devices')
    a.credentials=old


def test_unknown_workflow_and_no_compatible_hardware_rejected(service):
    _,_,a,_=service
    with pytest.raises(RuntimeError,match='Unregistered'):
        a.call('submit',{'workflow':'shell','device':'d1','app':'aquarium'})
    with pytest.raises(RuntimeError,match='No compatible'):
        submit(a,pool='test',require_abi='missing')
    with pytest.raises(RuntimeError,match='Unknown workflow request'):
        submit(a,device='d1',shell='dangerous')


def test_cross_device_and_stale_generations_rejected(service):
    cfg,_,a,_=service
    jid=submit(a,device='d1',duration=.8)
    deadline=time.monotonic()+3
    while a.call('status',{'job':jid})['generation'] is None and time.monotonic()<deadline:time.sleep(.02)
    job=a.call('status',{'job':jid});store=Store(cfg['state'])
    with pytest.raises(PermissionError):store.validate_lease(jid,'d2',job['generation'])
    with pytest.raises(PermissionError):store.validate_lease(jid,'d1',job['generation']-1)
    wait(a,jid)
    with pytest.raises(PermissionError):store.validate_lease(jid,'d1',job['generation'])


def test_immutable_upload_and_evidence_conflict(service,tmp_path):
    _,_,a,_=service
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr('AndroidManifest.xml',b'example')
    apk=tmp_path/'input.apk';apk.write_bytes(data.getvalue())
    stored=a.upload(apk);apk.write_bytes(b'changed')
    assert stored==hashlib.sha256(data.getvalue()).hexdigest()+'.apk'
    jid=submit(a,device='d1');wait(a,jid)
    out=tmp_path/'evidence';a.evidence(jid,out)
    (out/'receipt.json').write_text('conflict')
    with pytest.raises(FileExistsError):a.evidence(jid,out)


def test_worker_death_gates_device_not_other_device(service):
    _,_,a,b=service
    jid=submit(a,device='d1',duration=4)
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        job=a.call('status',{'job':jid})
        if job['worker_pid']:break
        time.sleep(.02)
    os.kill(job['worker_pid'],signal.SIGKILL)
    failed=wait(a,jid);assert failed['state']=='recovery-required'
    waiting=submit(b,device='d1',duration=.1)
    other=submit(b,device='d2',duration=.1)
    assert wait(a,other)['state']=='completed'
    assert a.call('status',{'job':waiting})['state']=='queued'
    recovery=a.call('submit',{'workflow':'readd','device':'d1'})['id']
    assert wait(a,recovery)['state']=='completed'
    assert wait(a,waiting)['state']=='completed'


def test_filtered_queue_includes_pool_competition(service):
    _,_,a,b=service
    first=submit(a,device='d1',duration=.8)
    pool=submit(b,pool='test',require_abi='arm32',duration=.2)
    filtered=a.call('queue',{'device':'d1'})
    assert {first,pool}<={j['id'] for j in filtered['jobs']}


def test_hook_denies_raw_but_does_not_approve_mutable_taskfile():
    raw={'hook_event_name':'PreToolUse','tool_input':{'command':'adb -s 192.168.4.46:5555 shell input keyevent 3'}}
    assert hook_decision(raw)['hookSpecificOutput']['permissionDecision']=='deny'
    assert hook_decision({'hook_event_name':'PermissionRequest','tool_input':{'command':'task chromecast:check'}})=={}
    fixed={'hook_event_name':'PermissionRequest','tool_input':{'command':'/opt/wf-device-coordinator/bin/chromecast queue'}}
    assert hook_decision(fixed)['hookSpecificOutput']['decision']['behavior']=='allow'
    fixed['tool_input']['command']+='; evil'
    assert hook_decision(fixed)=={}


def test_variant_recipe_rejects_path_labels_and_requires_restore():
    with pytest.raises(ValueError):
        validate_request({'workflow':'variant-benchmark','device':'d1','app':'aquarium','variants':[]},['jellyfish'])
    with pytest.raises(ValueError):
        validate_request({'workflow':'variant-benchmark','device':'d1','app':'aquarium','restore_apk':'x','variants':[{'label':'../evil','apk':'x'}]},['jellyfish'])


def test_task_values_preserve_literal_message_text(service,tmp_path):
    cfg,_,a,_=service
    jid=submit(a,device='d1',duration=.8)
    marker=tmp_path/'must-not-exist'
    text=f'Thai ไทย "quote" `touch {marker}` $(touch {marker})\nsecond line'
    env=dict(os.environ,WF_COORDINATOR_SOCKET=cfg['socket'],WF_COORDINATOR_CLIENT_STATE=str(tmp_path/'task-client'))
    result=subprocess.run(['task','chromecast:message','JOB='+jid,'TEXT='+text],cwd=ROOT,env=env,capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert not marker.exists()
    assert a.call('inbox')[0]['text']==text


def test_pairing_code_is_not_persisted_in_jobs_or_events(service):
    cfg,_,a,_=service
    store=Store(cfg['state']);device=store.devices()[0]
    device.update(transport='tls',endpoint='192.168.4.43:41277')
    store.update_device('d1',device)
    jid=a.call('submit',{'workflow':'readd','device':'d1','_setup':{'endpoint':'192.168.4.43:40001','code':'123456'}})['id']
    wait(a,jid)
    assert '123456' not in json.dumps(a.call('status',{'job':jid}))
    assert '123456' not in json.dumps(a.call('events',{'job':jid}))
    assert b'123456' not in Path(cfg['state'],'coordinator.sqlite3').read_bytes()


def test_fifo_does_not_depend_on_wall_clock_order(tmp_path):
    cfg=config(tmp_path);s=Store(cfg['state'],cfg['devices']);owner=s.register(os.getuid(),'test')['session']
    first=s.submit(owner,{'workflow':'check','app':'aquarium','device':'d1'})
    second=s.submit(owner,{'workflow':'check','app':'aquarium','device':'d1'})
    with s.db() as db:db.execute('UPDATE jobs SET accepted=0 WHERE id=?',(second['id'],))
    assert s.claim()==[first['id']]


def test_policy_merge_preserves_other_hooks_and_constraints(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('wf_installer',ROOT/'scripts/install-device-coordinator.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import tomllib
    old={'allowed_approval_policies':['on-request'],'features':{'hooks':False},'hooks':{'PreToolUse':[{'matcher':'Bash','hooks':[{'type':'command','command':'/other/trusted-hook'}]}]}}
    policy=tmp_path/'requirements.toml';policy.write_text(module.toml_dump(old))
    fragment=tomllib.loads((ROOT/'config/device-coordinator/requirements.toml').read_text())
    result=tomllib.loads(module.merge_requirements(policy,fragment))
    assert result['allowed_approval_policies']==old['allowed_approval_policies']
    assert result['features']['hooks'] is True
    assert result['hooks']['PreToolUse'][0]==old['hooks']['PreToolUse'][0]
    policy.write_text(module.toml_dump(result))
    assert tomllib.loads(module.merge_requirements(policy,fragment))==result


def test_png_decoder_handles_sub_and_up_filters():
    import struct,zlib
    from wf_device.image_assertions import pixels
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    header=struct.pack('>IIBBBBB',2,2,8,2,0,0,0)
    # RGB row: red then green, encoded with Sub; second row identical with Up.
    raw=b'\x01\xff\x00\x00\x01\xff\x00'+b'\x02'+bytes(6)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',header)+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    w,h,c,rows=pixels(png)
    assert (w,h,c)==(2,2,3)
    assert rows[0]==rows[1]==bytearray([255,0,0,0,255,0])


def test_cleanup_restores_exported_launcher_not_internal_activity(tmp_path):
    from wf_device.workflows import Adapter
    class S:
        def phase(self,*_):pass
    adapter=Adapter.__new__(Adapter)
    adapter.cleanup_mode=False;adapter.identity_verified=True;adapter.uncertain_install=False;adapter.store=S();adapter.job={'id':'example'}
    adapter.req={'workflow':'check'};adapter.record_pid=None;adapter.package='org.worldfoundry.wf_game.aquarium'
    adapter.previous='com.google.android.youtube.tv/internal.PrivateActivity'
    commands=[]
    def shell(*words,**kwargs):
        commands.append(words)
        return 'Status: ok' if words[:2]==('am','start') else ''
    adapter.shell=shell;adapter.foreground=lambda:['com.google.android.youtube.tv/exported.Launcher']
    adapter.key=lambda key:commands.append(('key',key))
    adapter.cleanup()
    starts=[cmd for cmd in commands if cmd[:2]==('am','start')]
    assert starts and '-n' not in starts[0]
    assert 'android.intent.category.LEANBACK_LAUNCHER' in starts[0]
    assert adapter.restoration=='previous-app-TV-launcher'


def test_legacy_discovery_skips_another_chromecast_and_pins_udn():
    from wf_device.discovery import rediscover
    seen=[]
    def fetch(ip):
        seen.append(ip)
        if ip=='192.168.4.47':return 'different-chromecast'
        if ip=='192.168.4.48':return 'expected-udn'
        raise ConnectionRefusedError()
    assert rediscover('192.168.4.46','expected-udn',fetch=fetch)=='192.168.4.48'
    assert seen==['192.168.4.46','192.168.4.47','192.168.4.48']


@pytest.mark.parametrize('failure', ['timeout', 'exit'])
def test_installer_reports_bounded_administrative_failures(monkeypatch, failure):
    import importlib.util
    spec=importlib.util.spec_from_file_location('wf_installer_failure',ROOT/'scripts/install-device-coordinator.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    seen=[]
    def run(command, **kwargs):
        seen.append(kwargs)
        if failure=='timeout':
            raise subprocess.TimeoutExpired(command,kwargs['timeout'],stderr=b'Reload daemon failed')
        raise subprocess.CalledProcessError(1,command,stderr='Connection timed out')
    monkeypatch.setattr(module.subprocess,'run',run)
    with pytest.raises(module.DeploymentError,match='systemctl daemon-reload') as error:
        module.admin_step(['systemctl','daemon-reload'],timeout=15)
    assert seen[0]['timeout']==15 and seen[0]['capture_output']
    assert ('timed out after 15 seconds' if failure=='timeout' else 'Connection timed out') in str(error.value)


def test_installer_stops_before_mutation_when_manager_is_unavailable(monkeypatch,capsys):
    import importlib.util
    spec=importlib.util.spec_from_file_location('wf_installer_preflight',ROOT/'scripts/install-device-coordinator.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module.os,'geteuid',lambda:0)
    monkeypatch.setattr(module.sys,'argv',['install-device-coordinator.py'])
    monkeypatch.setattr(module.pwd,'getpwnam',lambda _:pytest.fail('Provisioning began before manager preflight'))
    def failed(*args,**kwargs):raise module.DeploymentError('Connection timed out')
    monkeypatch.setattr(module,'admin_step',failed)
    assert module.main()==1
    assert 'No installation files were changed' in capsys.readouterr().err


@pytest.mark.parametrize('needs_reload', ['no', 'yes'])
def test_installer_resume_checks_loaded_units_without_another_reload(monkeypatch,needs_reload):
    import importlib.util
    spec=importlib.util.spec_from_file_location('wf_installer_resume',ROOT/'scripts/install-device-coordinator.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    commands=[]
    def step(command,**kwargs):
        commands.append(command)
        out=''
        if command[:2]==['systemctl','show']:
            out=f'LoadState=loaded\nNeedDaemonReload={needs_reload}\nFragmentPath=/etc/systemd/system/{command[2]}\n'
        return subprocess.CompletedProcess(command,0,stdout=out)
    monkeypatch.setattr(module,'admin_step',step)
    monkeypatch.setattr(module.Path,'exists',lambda _:True)
    if needs_reload=='yes':
        with pytest.raises(module.DeploymentError,match='has not loaded'):
            module.activate(resume=True)
        assert len(commands)==1
    else:
        module.activate(resume=True)
        assert ['systemctl','enable','--no-reload','wf-device-coordinator.service','wf-device-coordinator-network.timer'] in commands
        assert any(command[:2]==['systemctl','start'] for command in commands)
    assert not any('daemon-reload' in command for command in commands)


def test_persistent_adb_server_does_not_inherit_device_lock(tmp_path):
    import fcntl
    from wf_device.workflows import ensure_adb_server
    lock=open(tmp_path/'device.lock','a');fcntl.flock(lock,fcntl.LOCK_EX)
    os.set_inheritable(lock.fileno(),True)
    pidfile=tmp_path/'daemon.pid'
    daemon=tmp_path/'daemon.py'
    daemon.write_text('import os,time\nfrom pathlib import Path\nPath('+repr(str(pidfile))+').write_text(str(os.getpid()))\ntime.sleep(15)\n')
    adb=tmp_path/'adb'
    adb.write_text('#!'+sys.executable+'\nimport subprocess,sys\nsubprocess.Popen([sys.executable,'+repr(str(daemon))+'],close_fds=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n')
    adb.chmod(0o755)
    try:
        ensure_adb_server({'adb':str(adb)})
        deadline=time.monotonic()+3
        while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert pidfile.exists()
        lock.close()
        with open(tmp_path/'device.lock','a') as next_owner:
            fcntl.flock(next_owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
    finally:
        lock.close()
        if pidfile.exists():os.kill(int(pidfile.read_text()),signal.SIGTERM)


def test_cast_discovery_failure_retains_setup_error(tmp_path,monkeypatch):
    from wf_device.workflows import Adapter,NeedsSetup
    import wf_device.discovery
    adapter=Adapter.__new__(Adapter)
    adapter.device={'transport':'legacy-tcp','endpoint':'192.168.4.46:5555','cast_udn':'expected'}
    adapter.req={}
    adapter.store=type('StoreStub',(),{'phase':lambda *_:None})();adapter.job={'id':'j'}
    adapter.guard=lambda:None
    def unavailable(*args,**kwargs):raise RuntimeError('Registered Cast identity not found')
    monkeypatch.setattr(wf_device.discovery,'rediscover',unavailable)
    with pytest.raises(NeedsSetup,match='Registered Cast identity not found'):adapter.connect()


def test_address_hint_is_lan_scoped_and_readd_only(service):
    cfg,_,a,_=service
    store=Store(cfg['state']);device=store.devices()[0]
    device.update(transport='legacy-tcp',endpoint='192.168.4.46:5555')
    store.update_device('d1',device)
    jid=a.call('submit',{'workflow':'readd','device':'d1','address':'192.168.4.49'})['id']
    assert wait(a,jid)['request']['address']=='192.168.4.49'
    for address in ('127.0.0.1','8.8.8.8','192.168.9.49','192.168.4.49; id'):
        with pytest.raises(RuntimeError):a.call('submit',{'workflow':'readd','device':'d1','address':address})
    with pytest.raises(ValueError):validate_request({'workflow':'check','device':'d1','app':'aquarium','address':'192.168.4.49'},['jellyfish'])


def test_new_address_checks_hardware_serial_before_registry_update(monkeypatch):
    from wf_device.workflows import Adapter
    import wf_device.discovery
    adapter=Adapter.__new__(Adapter)
    adapter.req={'workflow':'readd','address':'192.168.4.49'}
    adapter.device={'transport':'legacy-tcp','endpoint':'192.168.4.46:5555','cast_udn':'old','serial':'expected-serial'}
    adapter.store=type('StoreStub',(),{'phase':lambda *_:None,'update_device':lambda *_:pytest.fail('Mismatched hardware registered')})()
    adapter.job={'id':'j'};adapter.identity_verified=False
    adapter.adb=lambda *args,**kwargs:'connected';adapter.shell=lambda *args,**kwargs:'other-device-serial'
    monkeypatch.setattr(wf_device.discovery,'rediscover',lambda *_args,**_kwargs:pytest.fail('Explicit hint unnecessarily required Cast discovery'))
    with pytest.raises(RuntimeError,match='Hardware serial mismatch'):adapter.connect()
    assert adapter.selector=='192.168.4.49:5555' and not adapter.identity_verified
    assert adapter.device['endpoint']=='192.168.4.46:5555'


def test_capture_accepts_no_apk_and_rejects_app_mutations(service):
    _,_,client,_=service
    jid=client.submit({'workflow':'capture','device':'d2'})['id']
    job=wait(client,jid)
    assert job['state']=='completed'
    assert job['request']=={'workflow':'capture','device':'d2'}
    for field,value in [('apk','anything.apk'),('app','aquarium'),('scene','jellyfish'),('validator','poke-resume')]:
        with pytest.raises(ValueError,match='Capture accepts only'):
            validate_request({'workflow':'capture','device':'d2',field:value},['jellyfish'])


def test_capture_preserves_foreground_and_never_installs(tmp_path):
    from wf_device.workflows import Adapter
    cfg=config(tmp_path);store=Store(cfg['state'],cfg['devices'])
    owner=store.register(os.getuid(),'capture-test')['session']
    job=store.submit(owner,{'workflow':'capture','device':'d2'})
    store.claim();job=store.job(job['id'])
    adapter=Adapter(store,job,cfg)
    adapter.connect=lambda: setattr(adapter,'identity_verified',True)
    commands=[]
    png=b'\x89PNG\r\n\x1a\n'+b'fixture-image-data'
    def adb(*args,**kwargs):
        commands.append(args)
        assert args==('exec-out','screencap','-p')
        assert kwargs=={'binary':True}
        return png
    adapter.adb=adb
    queries=[]
    def shell(*args,**kwargs):
        queries.append(args)
        assert args[0]=='dumpsys'
        return 'diagnostic fixture'
    adapter.shell=shell
    adapter.run();adapter.cleanup()
    assert commands==[('exec-out','screencap','-p')]
    assert (adapter.out/'screenshot.png').read_bytes()==png
    assert adapter.restoration=='unchanged: current display captured without input'
    assert queries==[('dumpsys','power'),('dumpsys','display'),('dumpsys','window'),
                     ('dumpsys','activity','activities'),('dumpsys','dreams'),('dumpsys','SurfaceFlinger')]
    assert (adapter.out/'power.txt').read_text()=='diagnostic fixture'
    assert all(v['result']=='saved' for v in json.loads((adapter.out/'display-diagnostics.json').read_text()).values())


def test_raw_capture_preserves_rgb_when_alpha_is_zero(tmp_path):
    import struct
    from PIL import Image
    from wf_device.capture import save_raw
    data=struct.pack('<4I',2,1,1,1)+bytes([123,45,67,0,1,2,3,255])
    summary=save_raw(data,tmp_path)
    assert summary['alpha_min']==0 and summary['nonzero_rgb_pixels']==2
    assert Image.open(tmp_path/'raw-preserved.png').getpixel((0,0))==(123,45,67,0)
    assert Image.open(tmp_path/'raw-opaque-preview.png').getpixel((0,0))==(123,45,67,255)
    assert (tmp_path/'raw-screencap.bin').read_bytes()==data
    with pytest.raises(RuntimeError,match='pixel length'):
        save_raw(data[:-1],tmp_path)


def test_capture_methods_reject_unreviewed_backends(service):
    _,_,client,_=service
    for method in ['png','raw','uiautomation','record','compare']:
        job=client.submit({'workflow':'capture','device':'d2','method':method})
        assert wait(client,job['id'])['state']=='completed'
    with pytest.raises(ValueError,match='reviewed capture'):
        validate_request({'workflow':'capture','device':'d2','method':'shell'},[])
    with pytest.raises(ValueError,match='reviewed capture'):
        validate_request({'workflow':'check','app':'aquarium','device':'d2','method':'record'},[])


def test_observational_record_only_controls_owned_recording(tmp_path):
    from wf_device.workflows import Adapter
    from wf_device.capture import capture_current
    cfg=config(tmp_path);store=Store(cfg['state'],cfg['devices'])
    owner=store.register(os.getuid(),'capture-test')['session']
    job=store.submit(owner,{'workflow':'capture','device':'d2','method':'record'})
    store.claim();adapter=Adapter(store,store.job(job['id']),cfg)
    adapter.identity_verified=True
    calls=[]
    def adb(*args,**kwargs):
        calls.append(args)
        if args[0]=='shell':
            assert args[1].startswith('screenrecord --time-limit 3 ')
            return '999'
        assert args[:2]==('exec-out','cat')
        return b'recording data'*100
    def shell(*args,**kwargs):
        calls.append(args)
        if args[:2]==('cat','/proc/999/cmdline'):return ''
        if args[0]=='rm':
            assert args[1]=='-f' and job['id'] in args[2]
            return ''
        assert args[0]=='cat'
        return 'recording log'
    adapter.adb=adb;adapter.shell=shell
    capture_current(adapter);adapter.cleanup()
    assert (adapter.out/'capture.mp4').is_file()
    assert adapter.record_pid is None
    assert not any('am' in call or 'input' in call or 'install' in call for call in calls)


def test_engine_log_tail_retains_recent_scene_without_reading_old_history(tmp_path):
    from wf_device.workflows import Adapter, ENGINE_LOG_TAIL_BYTES
    log = tmp_path/'wf.log'
    marker = 'level-menu: level 5 starts\n'
    log.write_bytes(b'x'*(ENGINE_LOG_TAIL_BYTES+1024)+marker.encode())
    adapter = object.__new__(Adapter)
    adapter.package = 'org.worldfoundry.wf_game.aquarium'
    def local_shell(*args, **kwargs):
        assert args[-1].endswith('/'+adapter.package+'/files/wf.log')
        return subprocess.check_output([*args[:-1],str(log)],text=True)
    adapter.shell = local_shell
    recent = adapter.engine_log_tail()
    assert len(recent.encode()) == ENGINE_LOG_TAIL_BYTES
    assert recent.endswith(marker)


def test_service_restart_during_drained_maintenance_keeps_queue_and_reservation(tmp_path):
    cfg=config(tmp_path)
    path=tmp_path/'config.json'
    path.write_text(json.dumps(cfg))
    process=subprocess.Popen([sys.executable,str(ROOT/'scripts/chromecast.py'),'serve','--config',str(path)],
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    deadline=time.monotonic()+5
    while not Path(cfg['socket']).exists() and time.monotonic()<deadline:
        time.sleep(.02)
    a=Client(cfg['socket'],tmp_path/'a.json')
    b=Client(cfg['socket'],tmp_path/'b.json')
    store = Store(cfg['state'])
    a.call('reserve', {'device': 'd2', 'reason': 'Watching TV'})
    active = submit(b, device='d1', duration=.3)
    deadline = time.monotonic()+3
    while b.call('status', {'job': active})['state'] == 'queued' and time.monotonic() < deadline:
        time.sleep(.02)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO maintenance VALUES(1,?,?)', ('Test deployment', time.time()))
    queued = b.call('submit', {'workflow': 'install', 'device': 'd2', 'app': 'bomberman'})['id']
    assert wait(b, active)['state'] == 'completed'
    assert b.call('status', {'job': queued})['state'] == 'queued'
    process.terminate()
    process.communicate(timeout=5)
    path = Path(cfg['state']).parent/'config.json'
    restarted = subprocess.Popen([sys.executable, str(ROOT/'scripts/chromecast.py'), 'serve', '--config', str(path)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic()+5
        while True:
            try:
                assert a.call('capabilities')['maintenance_drain']
                break
            except (RuntimeError, ConnectionRefusedError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.02)
        assert a.call('queue')['maintenance']['reason'] == 'Test deployment'
        assert b.call('status', {'job': queued})['state'] == 'queued'
        assert next(d for d in a.call('devices') if d['id']=='d2')['reservation']['owner'] == a.credentials['session']
        with store.db() as db:
            db.execute('DELETE FROM maintenance')
        deadline=time.monotonic()+5
        while b.call('status', {'job': queued})['phase']!='launcher-verification-pending' and time.monotonic()<deadline:
            time.sleep(.03)
        assert b.call('status', {'job': queued})['phase']=='launcher-verification-pending'
        assert next(d for d in a.call('devices') if d['id']=='d2')['reservation']['owner']==a.credentials['session']
        a.call('release', {'device':'d2'})
        assert wait(b, queued)['state'] == 'completed'
    finally:
        restarted.terminate()
        restarted.communicate(timeout=5)
