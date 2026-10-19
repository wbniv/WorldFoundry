#!/usr/bin/env python3
"""Manage a complete browser playthrough with isolated server and saved evidence."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin',default=os.environ.get('WF_PD_ORIGIN') or None,help='Use an existing game server instead of starting an isolated one')
    parser.add_argument('--out',type=Path,default=Path(os.environ.get('WF_PD_OUT') or ROOT/'docs/diagnostics'/('patchwork-playthrough-'+datetime.now().strftime('%Y%m%d-%H%M%S'))))
    parser.add_argument('--headed',action='store_true',default=os.environ.get('WF_PD_HEADED')=='1')
    parser.add_argument('--slow-ms',type=int,default=int(os.environ['WF_PD_SLOW_MS']) if os.environ.get('WF_PD_SLOW_MS') else None)
    parser.add_argument('--browser',default=shutil.which('google-chrome') or shutil.which('chromium') or '/usr/bin/google-chrome')
    args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    print('Evidence: '+str(out),flush=True)
    server=None
    try:
        origin=args.origin
        with (out/'server.log').open('w') as server_log:
            if not origin:
                env=dict(os.environ,WF_GAME='patchwork',PORT='0')
                env.pop('WF_PUBLIC_ORIGIN',None);env.pop('WF_CAST_APP_ID',None)
                server=subprocess.Popen(['node',str(ROOT/'party-games/platform/server/index.js')],cwd=ROOT,env=env,stdout=server_log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    text=(out/'server.log').read_text()
                    ready=re.search(r'party-games platform ready on (http://localhost:\d+)',text)
                    if ready:origin=ready.group(1);break
                    if server.poll() is not None:raise RuntimeError('Game server failed to start:\n'+text)
                    time.sleep(.1)
                if not origin:raise RuntimeError('Game server startup timed out; see '+str(out/'server.log'))
            print('Game server: '+origin+(' (existing)' if args.origin else ' (isolated; stopped on exit)'),flush=True)
            command=[sys.executable,str(ROOT/'party-games/games/patchwork/test/browser-check.py'),'--origin',origin,'--out',str(out),'--browser',args.browser]
            if args.headed:command+=['--headed']
            command+=['--slow-ms',str(args.slow_ms if args.slow_ms is not None else 100 if args.headed else 0)]
            with (out/'playthrough.log').open('w') as log:
                result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            # Print the saved result ourselves; failures retain the full traceback.
            print((out/'playthrough.log').read_text(),end='',flush=True)
            return result.returncode
    except (OSError,RuntimeError) as error:
        print(str(error),file=sys.stderr);return 1
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':sys.exit(main())
