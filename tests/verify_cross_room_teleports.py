"""Drive script-owned non-adjacent teleports in one real engine session.

Artifacts are retained in --out even when the engine crashes. No live device,
input automation, raw ADB or chapter dependency is used. Requires a GL display.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import shutil
import subprocess
import sys
import time


def run(args):
    sys.path.insert(0,str(args.repo/'tests'))
    from debug_bridge_client import BridgeClient
    args.out.mkdir(parents=True,exist_ok=True)
    log=args.out/'engine.log'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    command=[str(args.binary.resolve()),'-L'+str(args.level.resolve()),'--windowed',
             '--debug-print-actors','--debug-port',str(port),'--debug-bind','127.0.0.1']
    # ValidPtr uses printf. Keep its diagnostics visible before process cleanup,
    # instead of losing buffered stdout when the harness terminates the child.
    if shutil.which('stdbuf'):command=['stdbuf','-oL','-eL',*command]
    records=[];client=None
    with log.open('w') as output:
        process=subprocess.Popen(command,cwd=args.level.parent,stdout=output,stderr=subprocess.STDOUT,
            env={**os.environ,'DISPLAY':os.environ.get('DISPLAY',':0'),'WF_REST_PORT':'0'})
        try:
            client=BridgeClient(port=port,timeout=10)
            text=log.read_text(errors='replace')
            # Release omits constructor debug printing; both configurations
            # verify the actual Player by its script acknowledgement and pose.
            if '[Actor]' in text:
                assert re.search(r'\[Actor\] idx=9 class=22 ',text),'fixture Player index mismatch'
                assert re.search(r'\[Actor\] idx=8 class=16 ',text),'fixture camera index mismatch'
            for mb in (470,471,3009,3010,3011,1903):client.watch(9,mb)
            for mb in (3009,3010,3011):client.watch(6,mb)
            def wait(predicate,timeout=5):
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    assert process.poll() is None,f'engine exited: {process.returncode}'
                    if predicate():return
                    time.sleep(.01)
                raise AssertionError('timeout waiting for teleport evidence')
            wait(lambda:client.mailbox_values.get((9,1903),0)>0)
            # Destination D's mesh is initially unbound. This should cache the
            # requested scale without diagnosing a pointer failure.
            client.watch(18,3042)
            client.set_mailbox(3042,.25,idx=18)
            wait(lambda:client.mailbox_values.get((18,3042))==.25)
            print('PASS: unloaded room D actor caches scale 0.25',flush=True)
            for lap in range(args.laps):
                scale=.25 if lap%2==0 else .5
                # Every lap starts in A with D unloaded. Test fresh deferred
                # scale writes after an actual unload, as well as at startup.
                client.set_mailbox(3042,scale,idx=18)
                wait(lambda:client.mailbox_values.get((18,3042))==scale)
                # A→D: completely disjoint set, D→B: two rooms load,
                # B→C: retained A, C→D→A: all three A rooms load on return.
                for phase,x in [(2,100),(4,0),(1,300),(2,100),(5,200),(1,300),(4,0)]:
                    if args.mutation:
                        client.send({'op':'scene:set_transform','idx':9,'pos':[x,0,7]})
                    else:
                        client.set_mailbox(470,phase,idx=9)
                    wait(lambda:(args.mutation or client.mailbox_values.get((9,471))==phase)
                        and abs(client.mailbox_values.get((9,3009),-999)-x)<.01)
                    # Observe multiple completed frames after the script write.
                    time.sleep(.1)
                    assert process.poll() is None,f'engine exited after arrival: {process.returncode}'
                    assert client.mailbox_values.get((18,3042))==scale,'room reload lost scale'
                    records.append({'lap':lap+1,'command':phase,'x':client.mailbox_values[(9,3009)],
                        'camera_x':client.mailbox_values.get((6,3009)),
                        'fps':client.mailbox_values.get((9,1903))})
                    print(json.dumps(records[-1]),flush=True)
                    if args.require_camera:
                        wait(lambda:abs(client.mailbox_values.get((6,3009),-999)-x)<.01,timeout=2)
            if args.audit_boundary:
                client.send({'op':'pause'})
                assert client.wait_for(lambda m:m.get('op')=='paused',timeout=5)
                time.sleep(.1)
                if args.require_camera:
                    # Room-local script movement must retain camera smoothing.
                    client.set_mailbox(470,6,idx=9)
                    client.send({'op':'step','frames':1})
                    wait(lambda:client.mailbox_values.get((9,471))==6
                        and abs(client.mailbox_values.get((9,3009),-999)-5)<.01)
                    assert abs(client.mailbox_values.get((6,3009),-999)-5)>.1,'room-local move incorrectly snapped camera'
                def screenshot(label):
                    destination=args.out/(label+'.png')
                    client.send({'op':'screenshot','filename':str(destination.resolve())})
                    assert client.wait_for(lambda m:m.get('op')=='screenshot_done'
                        and m.get('filename')==str(destination.resolve()),timeout=5)
                screenshot('before-teleport')
                client.set_mailbox(470,1,idx=9)
                client.send({'op':'step','frames':1})
                wait(lambda:client.mailbox_values.get((9,471))==1)
                if args.require_camera:
                    # The engine remains paused: the camera must arrive in the
                    # same single script frame, with no smoothing frames.
                    wait(lambda:abs(client.mailbox_values.get((6,3009),-999)-300)<.01)
                screenshot('script-frame')
                client.send({'op':'step','frames':1})
                time.sleep(.1)
                screenshot('following-frame')
                client.send({'op':'step','frames':3})
                time.sleep(.1)
                screenshot('three-more-frames')
                client.send({'op':'resume'})
            text=log.read_text(errors='replace')
            assert not re.search(r'ASSERTION FAILED|runtime error:|zforth error|SIGSEGV|ValidPtr\( \(nil\) \) failed',text), 'engine diagnostics failed'
            entry='transform' if args.mutation else 'script'
            print(f'PASS: {len(records)} {entry} teleports in one engine session',flush=True)
        finally:
            if client:client.close()
            exit_before_cleanup=process.poll()
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            (args.out/'receipt.json').write_text(json.dumps({'command':command,'arrivals':records,
                'exit_before_cleanup':exit_before_cleanup,'cleanup_exit':process.returncode},indent=2)+'\n')
            print('Engine evidence: '+str(log),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--level',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--laps',type=int,default=5)
    parser.add_argument('--audit-boundary',action='store_true',help='Capture a paused one-frame teleport boundary for timing policy review')
    parser.add_argument('--require-camera',action='store_true',help='Assert immediate following-camera arrival at the destination')
    parser.add_argument('--mutation',action='store_true',help='Exercise wfmut::SetActorPos through the transform bridge')
    args=parser.parse_args();run(args)
