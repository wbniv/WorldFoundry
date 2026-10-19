"""Accelerate the existing level-owned Parmenides tour; never write player pose."""
import hashlib,json,os,socket,subprocess,sys,time
from pathlib import Path
repo=Path(sys.argv[1]);fixture=Path(sys.argv[2]);out=Path(sys.argv[3])
sys.path.insert(0,str(repo/'tests'))
from debug_bridge_client import BridgeClient
out.mkdir(parents=True,exist_ok=True)
ids=json.loads((fixture/'actors.json').read_text())['ids'];player=ids['Player'];camera=ids['Camera']
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
binary=repo/'engine/wf_game';level=fixture/'parmenides_slice-standalone.iff'
command=['stdbuf','-oL','-eL',str(binary),'-L'+str(level),'--windowed','--debug-port',str(port),'--debug-bind','127.0.0.1',
    '--vram-width=5120','--vram-height=2048','--vram-slot-width=1024','--vram-slot-height=2048',
    '--vram-perm-width=2048','--vram-perm-height=2048']
records=[];bridge=None
with (out/'engine.log').open('w') as log:
    process=subprocess.Popen(command,cwd=fixture,env={**os.environ,'DISPLAY':':0','WF_REST_PORT':'0'},stdout=log,stderr=subprocess.STDOUT)
    try:
        bridge=BridgeClient(port=port,timeout=30)
        for mb in [102,470,471,475,3009,3010,3011,1903]:bridge.watch(player,mb)
        for mb in [3009,3010,3011]:bridge.watch(camera,mb)
        def wait(predicate):
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                assert process.poll() is None,f'engine exited {process.returncode}'
                if predicate():return
                time.sleep(.02)
            raise AssertionError('chapter tour arrival timed out')
        wait(lambda:bridge.mailbox_values.get((player,1903),0)>0)
        for lap in range(5):
            for scene,(realm,x) in enumerate([(3,294),(4,400),(5,500)]):
                bridge.set_mailbox(470,5.05+18*scene,idx=player)
                wait(lambda:bridge.mailbox_values.get((player,475))==scene+1
                    and bridge.mailbox_values.get((player,102))==realm
                    and abs(bridge.mailbox_values.get((player,3009),-999)-x)<1)
                time.sleep(.2)
                record=dict(lap=lap+1,realm=realm,player=[bridge.mailbox_values.get((player,m)) for m in [3009,3010,3011]],
                    camera=[bridge.mailbox_values.get((camera,m)) for m in [3009,3010,3011]])
                assert abs(record['camera'][0]-x)<10,'camera did not arrive in realm'
                records.append(record);print(json.dumps(record),flush=True)
        text=(out/'engine.log').read_text(errors='replace')
        assert not any(s in text for s in ['ASSERTION FAILED','runtime error:','zforth error','SIGSEGV','ValidPtr( (nil) ) failed'])
        print('PASS: 15 level-owned chapter teleports, including returns and slot reuse',flush=True)
    finally:
        if bridge:bridge.close()
        alive=process.poll() is None
        if alive:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        (out/'receipt.json').write_text(json.dumps(dict(command=command,fixture=str(fixture),
            level_sha256=hashlib.sha256(level.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            arrivals=records,alive_before_cleanup=alive,cleanup_exit=process.returncode),indent=2)+'\n')
