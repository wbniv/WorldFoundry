"""Real loopback transport, bounds, fresh-state fences and instance reuse."""
import json
import socket
import subprocess
import time
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='session')
def executable(tmp_path_factory):
    binary=tmp_path_factory.mktemp('diagnostics')/'host'
    subprocess.run(['g++','-std=c++17','-O1','-fno-exceptions','-pthread',
                    '-DWF_RUNTIME_DIAGNOSTICS',str(ROOT/'tests/runtime_diagnostics_host.cc'),
                    str(ROOT/'engine/runtime_diagnostics.cpp'),'-o',str(binary)],check=True)
    return binary

@pytest.fixture
def host(executable):
    p=subprocess.Popen([str(executable)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
    p.port=int(p.stdout.readline().split()[1])
    def command(text):
        p.stdin.write(text+'\n');p.stdin.flush()
        assert p.stdout.readline().strip()=='OK '+text.split()[0]
    p.command=command
    yield p
    p.command('stop');p.wait(timeout=3)
    assert p.returncode==0

class Client:
    def __init__(self,host):
        self.socket=socket.create_connection(('127.0.0.1',host.port),timeout=2)
        self.file=self.socket.makefile('rb');self.id=0
    def send(self,**fields):
        self.id+=1
        self.socket.sendall((json.dumps({'v':1,'op':'snapshot','request':self.id,**fields})+'\n').encode())
    def read(self):
        return json.loads(self.file.readline())
    def snapshot(self,**fields):
        self.send(**fields);return self.read()
    def close(self):
        self.file.close();self.socket.close()

def test_correlated_snapshot_and_committed_vs_draft(host):
    c=Client(host)
    try:
        reply=c.snapshot(draft=True)
        assert reply['request']==1 and reply['v']==1 and reply['run']
        assert reply['monotonic_us']>0 and reply['frame']>=reply['simulation_step']>0
        assert reply['properties']['fields']==[{'id':'Fixture:1','field':1,'key':'seed','committed':'713','draft':'719'}]
        assert 'draft' not in c.snapshot()['properties']['fields'][0]
        fresh=c.snapshot(run=reply['run'],level_generation=reply['level_generation'],after_simulation_step=reply['simulation_step'])
        assert fresh['simulation_step']>reply['simulation_step']
    finally:c.close()

def test_received_routed_consumed_and_release(host):
    c=Client(host)
    try:
        host.command('receive hardware 8192')
        r=c.snapshot()['input'];assert r['received']==1 and r['consumed']==0 and r['held']==8192
        host.command('route');r=c.snapshot()['input'];assert r['routed']==1 and r['consumed']==0
        host.command('consume');r=c.snapshot(min_input=1)['input'];assert r['history'][0]['consumed']
        host.command('receive phone 8192');host.command('receive hardware 0');host.command('consume')
        r=c.snapshot(min_input=3)['input'];assert r['held']==8192 and r['last_release']==3
        assert r['sources']=={'hardware':0,'phone':8192}
        host.command('receive phone 0');host.command('consume')
        r=c.snapshot(since_input=3)['input'];assert r['held']==0 and r['history'][0]['released']==8192
    finally:c.close()

def test_paused_suspended_stale_level_and_actor(host):
    c=Client(host)
    try:
        r=c.snapshot();g=r['level_generation'];a=r['player']['generation']
        host.command('pause 1')
        assert c.snapshot(level_generation=g,after_simulation_step=r['simulation_step'])['error']=='simulation-paused'
        assert c.snapshot()['game']['paused']
        host.command('suspend 1')
        assert c.snapshot(min_input=99)['error']=='suspended'
        host.command('suspend 0');host.command('pause 0');host.command('level')
        assert c.snapshot(level_generation=g)['error']=='stale-level'
        g=c.snapshot()['level_generation']
        host.command('delete')
        assert c.snapshot(level_generation=g,actor=1,actor_generation=a)['error']=='actor-unavailable'
        host.command('create')
        assert c.snapshot(level_generation=g,actor=1,actor_generation=a)['error']=='stale-actor'
        assert c.snapshot(run='previous-process')['error']=='stale-run'
    finally:c.close()

@pytest.mark.parametrize('raw,error',[
    ('{"v":1,"request":1,"op":"pause"}','read-only-operation'),
    ('{"v":1,"request":1,"op":"inject_input"}','read-only-operation'),
    ('{"v":1,"request":1,"op":"snapshot","actor":1}','generation-required'),
    ('{"v":1,"request":1,"op":"snapshot","request":2}','malformed-request'),
    ('{"v":1,"request":1,"op":"snapshot","timeout_ms":false}','invalid-field'),
    ('{"v":2,"request":1,"op":"snapshot"}','unsupported-version'),
    ('{"v":1,"request":1,"op":"snapshot","script":"x"}','unknown-field'),
    ('{oops}','malformed-request'),
    ('{"v":1,"request":1,"op":"snapshot","actor":[[[[]]]]}','malformed-request'),
])
def test_strict_parser(host,raw,error):
    c=Client(host)
    try:
        c.socket.sendall((raw+'\n').encode());assert c.read()['error']==error
        assert c.snapshot(request=99)['op']=='snapshot'
    finally:c.close()

def test_queue_limits_timeout_and_cross_client_isolation(host):
    c=Client(host);other=Client(host)
    try:
        for _ in range(17):c.send(min_input=999,timeout_ms=120)
        r=c.read();assert r['request']==17 and r['error']=='queue-full'
        assert other.snapshot()['request']==1
        remaining=[c.read() for _ in range(16)]
        assert {r['request'] for r in remaining}==set(range(1,17))
        assert all(r['error']=='timeout' for r in remaining)
    finally:c.close();other.close()

def test_oversize_disconnect_and_stop_with_slow_client(host):
    c=Client(host)
    c.socket.sendall(b'x'*4097)
    assert c.file.readline()==b'';c.close()
    slow=Client(host);slow.socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024)
    for i in range(2000):
        try:slow.socket.sendall((f'{{"v":1,"request":{i+1},"op":"pause"}}\n').encode())
        except OSError:break
    # A saturated socket never delays another client or shutdown.
    other=Client(host);assert other.snapshot()['op']=='snapshot';other.close();slow.close()

def test_input_gap_is_explicit(host):
    c=Client(host)
    try:
        for _ in range(140):host.command('receive hardware 0')
        r=c.snapshot(since_input=1)['input']
        assert r['gap'] and len(r['history'])==128 and r['oldest_receipt']==13
        assert not c.snapshot(since_input=139)['input']['gap']
    finally:c.close()

def test_actual_actor_read_is_distinct_from_routing(host):
    c=Client(host)
    try:
        host.command('receive hardware 8192');host.command('route')
        before=c.snapshot();assert before['input']['consumed']==0
        host.command('actor-read')
        e=c.snapshot(min_input=1)['input']['history'][0]
        assert e['reason']=='actor-input-read' and e['consumed']
        assert e['consumers']==[{'actor':1,'generation':before['player']['generation'],'mailbox':1909}]
    finally:c.close()
