"""Observe the known inactive-source membership defect in the real engine.

Successful exit means the defect and its source-reactivation control reproduced.
With --expect-fixed, instead require prompt updates without source activation.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time


def run(args, warm):
    from debug_bridge_client import BridgeClient
    out=args.out/('previously-loaded' if warm else 'never-loaded')
    out.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    command=['stdbuf','-oL','-eL',str(args.binary.resolve()),'-L'+str(args.level.resolve()),
             '--windowed','--debug-print-actors','--debug-port',str(port),'--debug-bind','127.0.0.1']
    records=[];client=None;failure=None
    with (out/'engine.log').open('w') as log:
        process=subprocess.Popen(command,cwd=args.level.parent,stdout=log,stderr=subprocess.STDOUT,
            env={**os.environ,'DISPLAY':os.environ.get('DISPLAY',':0'),'WF_REST_PORT':'0'})
        try:
            client=BridgeClient(port=port,timeout=10)
            for idx in (9,20,21):
                for mb in ({9:480,20:481,21:482}[idx],3009):client.watch(idx,mb)
            client.watch(9,471)
            def wait(predicate):
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    assert process.poll() is None,f'engine exited {process.returncode}'
                    if predicate():return
                    time.sleep(.01)
                raise AssertionError('timeout waiting for observation')
            def value(idx,mb=None):return client.mailbox_values.get((idx,mb if mb is not None else {9:480,20:481,21:482}[idx]),-999)
            def snapshot(label):
                record={'label':label,**{str(idx):{'heartbeat':value(idx),'x':value(idx,3009)} for idx in (9,20,21)}}
                records.append(record);print(json.dumps(record),flush=True)
                return record
            def frames(n):
                start=value(9);wait(lambda:value(9)>=start+n)
            def request(phase,x):
                client.set_mailbox(470,phase,idx=9)
                wait(lambda:value(9,471)==phase and abs(value(9,3009)-x)<.01)
                frames(5)
            def screenshot(label):
                path=str((out/(label+'.png')).resolve())
                client.send({'op':'screenshot','filename':path})
                assert client.wait_for(lambda m:m.get('op')=='screenshot_done' and m.get('filename')==path,5)
            wait(lambda:value(9)>5 and value(21)>5 and value(20,3009)==295)
            if warm:
                request(1,300);wait(lambda:value(20)>5)
                request(4,0)
            frames(10)
            before=snapshot('before-script-move')
            screenshot('before-move')
            if args.expect_fixed:
                client.send({'op':'pause'})
                assert client.wait_for(lambda m:m.get('op')=='paused',timeout=5)
                client.set_mailbox(470,7,idx=9)
                client.send({'op':'step','frames':1})
                wait(lambda:value(9,471)==7 and value(20,3009)==-5)
                snapshot('single-script-frame')
                screenshot('single-script-frame')
                # No second physics pass in the write frame; the target joins
                # normal actor iteration on the very next frame.
                assert value(20)==before['20']['heartbeat']
                client.send({'op':'step','frames':1})
                wait(lambda:value(20)==before['20']['heartbeat']+1)
                snapshot('next-single-frame')
                client.send({'op':'resume'})
            request(7,0)
            wait(lambda:value(20,3009)==-5)
            after=snapshot('pose-written-into-A')
            frames(120)
            stalled=snapshot('after-120-player-updates-in-A')
            screenshot('after-move-in-A')
            assert stalled['21']['heartbeat']-after['21']['heartbeat']>=100, 'active control did not update'
            if args.expect_fixed:
                assert after['20']['heartbeat']>before['20']['heartbeat'], 'target did not promptly start updating'
                assert stalled['20']['heartbeat']-after['20']['heartbeat']>=100, 'target remained stranded in inactive source'
                # Move back into inactive D: scripts must stop, despite its
                # permanent assets staying bound. Repeat return and batch writes.
                for phase in (7,9,7):
                    request(8,0);wait(lambda:value(20,3009)==295)
                    parked=value(20);frames(15)
                    assert value(20)==parked,'actor in inactive destination kept updating'
                    request(phase,0);wait(lambda:value(20,3009)==-5)
                    frames(10)
                    assert value(20)>parked+5,'actor failed repeated inactive-source return'
                snapshot('three-repeat-returns-without-visiting-D')
            else:
                assert stalled['20']['heartbeat']==before['20']['heartbeat'], 'target updated despite inactive source'
            request(1,300)
            frames(10)
            activated=snapshot('source-D-reactivated')
            request(4,0)
            frames(30)
            recovered=snapshot('returned-to-A')
            screenshot('recovered-in-A')
            assert recovered['20']['heartbeat']>activated['20']['heartbeat']+10,'source reactivation did not repair updates'
            assert not re.search(r'ASSERTION FAILED|runtime error:|zforth error|SIGSEGV|ValidPtr\( \(nil\) \) failed',
                                 (out/'engine.log').read_text(errors='replace')), 'engine diagnostics failed'
            print('PASS: inactive-source actor promptly rejoins updates, including repeated returns' if args.expect_fixed
                  else 'REPRODUCED: physical move succeeds, target stalls until source room reactivation',flush=True)
        except BaseException as exc:
            failure=repr(exc);raise
        finally:
            if client:client.close()
            exit_before_cleanup=process.poll()
            if exit_before_cleanup is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            (out/'receipt.json').write_text(json.dumps({'command':command,'warm_source':warm,
                'expect_fixed':args.expect_fixed,
                'binary_sha256':hashlib.sha256(args.binary.read_bytes()).hexdigest(),
                'fixture_sha256':hashlib.sha256(args.level.read_bytes()).hexdigest(),
                'observations':records,'failure':failure,'exit_before_cleanup':exit_before_cleanup,
                'cleanup_exit':process.returncode},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--level',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--expect-fixed',action='store_true',help='Require prompt membership repair rather than reproduce the old defect')
    args=parser.parse_args()
    for warm in (False,True):run(args,warm)
