#!/usr/bin/env python3
"""Reviewable root provisioning; use --check for a read-only deployment inventory."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import time
import tomllib
import traceback

ROOT=Path(__file__).resolve().parents[1]
DEST=Path('/opt/wf-device-coordinator')
CONF=Path('/etc/wf-device-coordinator')
STATE=Path('/var/lib/wf-device-coordinator')


class DeploymentError(RuntimeError):
    """An administrative step failed; activation must not be reported as complete."""


def admin_step(command, *, timeout=30):
    try:
        return subprocess.run(command,check=True,timeout=timeout,capture_output=True,text=True)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:
        detail=error.stderr or error.stdout or ''
        if isinstance(detail,bytes):detail=detail.decode(errors='replace')
        reason=f'timed out after {timeout} seconds' if isinstance(error,subprocess.TimeoutExpired) else f'exited with status {error.returncode}'
        raise DeploymentError(f"{' '.join(command)} {reason}"+(f': {detail.strip()}' if detail.strip() else '')) from error


UNIT_NAMES=('wf-device-coordinator.service','wf-device-coordinator-network.service','wf-device-coordinator-network.timer')


def activate(*, resume=False, reload_timeout=900):
    if resume:
        # Do not enqueue another reload after an installer timed out waiting for
        # PID 1. Confirm that the completed reload loaded our current unit files.
        for unit in UNIT_NAMES:
            result=admin_step(['systemctl','show',unit,'--property=LoadState,NeedDaemonReload,FragmentPath'])
            properties=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
            if properties.get('LoadState')!='loaded' or properties.get('NeedDaemonReload')!='no' or properties.get('FragmentPath')!='/etc/systemd/system/'+unit:
                raise DeploymentError(f'{unit} has not loaded its installed revision; wait for the existing reload to finish or run a full install once the manager responds')
    else:
        print(f'Reloading systemd (installer limit {reload_timeout} seconds; systemctl may time out earlier). A client timeout does not cancel the manager reload.',flush=True)
        admin_step(['systemctl','daemon-reload'],timeout=reload_timeout)
    admin_step(['/usr/bin/python3',str(DEST/'config/refresh-network.py')])
    # enable otherwise implicitly requests another daemon-reload. These units
    # have already been loaded above; only their boot-target symlinks change.
    admin_step(['systemctl','enable','--no-reload','wf-device-coordinator.service','wf-device-coordinator-network.timer'])
    admin_step(['systemctl','start','wf-device-coordinator.service','wf-device-coordinator-network.timer'],timeout=60)
    admin_step(['systemctl','is-active','--quiet','wf-device-coordinator.service','wf-device-coordinator-network.timer'])
    socket=Path('/run/wf-device-coordinator/coordinator.sock')
    deadline=time.monotonic()+5
    while not socket.exists() and time.monotonic()<deadline:
        time.sleep(.1)
    if not socket.exists():
        raise DeploymentError('The service started but its API socket is not ready; inspect journalctl -u wf-device-coordinator.service')


def toml_dump(data):
    lines=[]
    def key(name):return json.dumps(name)
    def value(v):
        if isinstance(v,bool):return 'true' if v else 'false'
        if isinstance(v,(str,int,float)):return json.dumps(v,ensure_ascii=False)
        if isinstance(v,list):return '['+', '.join(value(x) for x in v)+']'
        raise ValueError('Unsupported existing policy TOML value; preserve and merge manually')
    def table(obj,path=(),array=False):
        if path:
            lines.append((' [[' if array else ' [').strip()+'.'.join(key(k) for k in path)+(']]' if array else ']'))
        for k,v in obj.items():
            if not isinstance(v,dict) and not (isinstance(v,list) and v and isinstance(v[0],dict)):
                lines.append(key(k)+' = '+value(v))
        for k,v in obj.items():
            if isinstance(v,dict):table(v,path+(k,))
            elif isinstance(v,list) and v and isinstance(v[0],dict):
                for entry in v:table(entry,path+(k,),True)
    table(data)
    text='\n'.join(lines)+'\n'
    if tomllib.loads(text)!=data:
        raise ValueError('Policy serialization changed existing settings; refusing update')
    return text


def merge_requirements(path,fragment):
    existing=tomllib.loads(path.read_text()) if path.exists() else {}
    existing.setdefault('features',{})['hooks']=True
    hooks=existing.setdefault('hooks',{})
    hooks.setdefault('managed_dir',fragment['hooks']['managed_dir'])
    for event,groups in fragment['hooks'].items():
        if event=='managed_dir':continue
        target=hooks.setdefault(event,[])
        for group in groups:
            if group not in target:target.append(group)
    return toml_dump(existing)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--client-user',default='will')
    ap.add_argument('--sdk',default='/home/will/android-sdk-local')
    ap.add_argument('--reuse-host-key',action='store_true',help='Copy current authorized host key into protected service state; otherwise use a fresh service identity and authorize it on each TV')
    ap.add_argument('--resume-activation',action='store_true',help='After a timed-out reload completes, verify loaded units and finish activation without copying files or reloading again')
    ap.add_argument('--reload-timeout',type=int,default=900,help='Bound systemd reload wait in seconds (default 900)')
    args=ap.parse_args()
    if args.reload_timeout<1:ap.error('--reload-timeout must be positive')
    if args.check:
        print(json.dumps({'code_installed':DEST.exists(),'config_installed':CONF.exists(),
                          'socket_present':Path('/run/wf-device-coordinator/coordinator.sock').exists(),
                          'requires_root':os.geteuid()!=0,'scope':'separate UID, protected code/state, address rules, managed hooks'},indent=2))
        return 0
    if os.geteuid()!=0:
        raise SystemExit('Run from your terminal: sudo python3 scripts/install-device-coordinator.py')
    # Check PID 1 before modifying protected files. A healthy D-Bus daemon alone
    # does not establish that the service manager will answer administrative calls.
    try:
        admin_step(['systemctl','show','--property=Version','--value'],timeout=15)
    except DeploymentError as error:
        print(f'Systemd preflight failed: {error}\nNo installation files were changed. '
              'An earlier reload may still be running. Inspect journalctl -b _PID=1 --grep=Reload -n 8. '
              'After it finishes, use --resume-activation for an already provisioned installation.',file=sys.stderr)
        return 1
    if args.resume_activation:
        if not (DEST/'config/refresh-network.py').is_file() or not (CONF/'devices.json').is_file():
            print('Protected provisioning is missing; run a full install first.',file=sys.stderr)
            return 1
        try:activate(resume=True)
        except DeploymentError as error:
            print(f'Activation remains incomplete: {error}',file=sys.stderr)
            return 1
        print('Activation completed. Run task chromecast:readd for each device; dashboard: http://127.0.0.1:8767. Enforcement verification remains pending.')
        return 0
    user=pwd.getpwnam(args.client_user)
    sdk=Path(args.sdk)
    aapts=sorted((sdk/'build-tools').glob('*/aapt'))
    if not aapts or not (sdk/'platform-tools/adb').is_file():
        raise SystemExit('SDK adb/aapt missing')
    policy=Path('/etc/codex/requirements.toml')
    fragment=tomllib.loads((ROOT/'config/device-coordinator/requirements.toml').read_text())
    policy_text=merge_requirements(policy,fragment) # Validate before any mutation.
    db=STATE/'coordinator.sqlite3'
    if db.exists():
        import sqlite3
        with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as connection:
            if connection.execute("SELECT 1 FROM jobs WHERE state='running' LIMIT 1").fetchone():
                raise SystemExit('Active device session: drain/cancel through coordinator before updating its protected code')
    # Stop the old process and its persistent ADB children before replacing
    # adapters. Starting an already active unit would otherwise retain old code.
    loaded=admin_step(['systemctl','show','wf-device-coordinator.service','--property=LoadState','--value']).stdout.strip()
    if loaded=='loaded':
        admin_step(['systemctl','stop','wf-device-coordinator.service'],timeout=60)
    try:account=pwd.getpwnam('wf-device-coordinator')
    except KeyError:
        subprocess.run(['useradd','--system','--home-dir',str(STATE),'--shell','/usr/sbin/nologin','wf-device-coordinator'],check=True)
        account=pwd.getpwnam('wf-device-coordinator')
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'scripts').mkdir(exist_ok=True)
    shutil.copytree(ROOT/'scripts/wf_device',DEST/'scripts/wf_device',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'scripts/chromecast.py',DEST/'scripts/chromecast.py')
    shutil.copytree(ROOT/'config/device-coordinator',DEST/'config',dirs_exist_ok=True)
    (DEST/'bin').mkdir(exist_ok=True)
    for source,name in [(sdk/'platform-tools/adb','adb'),(aapts[-1],'aapt'),(ROOT/'config/device-coordinator/chromecast','chromecast')]:
        shutil.copy2(source,DEST/'bin'/name);os.chmod(DEST/'bin'/name,0o755)
    # aapt resolves SDK libc++ relative to its executable; keep that dependency protected too.
    (DEST/'lib64').mkdir(exist_ok=True)
    shutil.copy2(aapts[-1].parent/'lib64/libc++.so',DEST/'lib64/libc++.so')
    (DEST/'hooks').mkdir(exist_ok=True)
    for path in DEST.rglob('*'):
        os.chown(path,0,0)
        os.chmod(path,0o755 if path.is_dir() or path.parent==DEST/'bin' else 0o644)
    CONF.mkdir(mode=0o755,exist_ok=True)
    config=json.loads((ROOT/'config/device-coordinator/devices.json').read_text())
    config['allowed_uids']=[user.pw_uid]
    config['adb_socket']='localfilesystem:'+str(STATE/'adb.sock')
    (CONF/'devices.json').write_text(json.dumps(config,indent=2)+'\n')
    STATE.mkdir(mode=0o700,exist_ok=True);os.chown(STATE,account.pw_uid,user.pw_gid);os.chmod(STATE,0o700)
    adbhome=STATE/'adb-home';adbhome.mkdir(mode=0o700,exist_ok=True);os.chown(adbhome,account.pw_uid,user.pw_gid)
    if args.reuse_host_key:
        for name in ('adbkey','adbkey.pub'):
            source=Path(user.pw_dir)/'.android'/name
            if not source.is_file():raise SystemExit('Existing host key missing; retry without --reuse-host-key')
            shutil.copy2(source,adbhome/name);os.chown(adbhome/name,account.pw_uid,user.pw_gid);os.chmod(adbhome/name,0o600)
    policy.parent.mkdir(parents=True,exist_ok=True)
    if policy.exists() and not policy.with_suffix('.before-wf.toml').exists():
        shutil.copy2(policy,policy.with_suffix('.before-wf.toml'))
    policy.write_text(policy_text)
    rules=Path('/etc/codex/rules');rules.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'config/device-coordinator/chromecast.rules',rules/'chromecast.rules')
    for name in UNIT_NAMES:
        text=(ROOT/'config/device-coordinator'/name).read_text().replace('Group=will','Group='+str(user.pw_gid))
        (Path('/etc/systemd/system')/name).write_text(text)
    try:
        activate(reload_timeout=args.reload_timeout)
    except DeploymentError as error:
        print(f'Provisioning completed, but activation failed: {error}\n'
              'The protected files remain installed; service access and enforcement are not verified.\n'
              'Inspect: systemctl status wf-device-coordinator.service wf-device-coordinator-network.timer --no-pager\n'
              'A reload timeout does not cancel PID 1: wait for Reloading finished in the journal.\n'
              'Then run this installer with --resume-activation to avoid a second reload; state and policy are preserved.',file=sys.stderr)
        return 1
    print('Installed. Authorize the fresh service host on each TV if prompted.')
    print('Run task chromecast:readd DEVICE=chromecast-test-01, then device 02.')
    print('Dashboard: http://127.0.0.1:8767')
    print('Enforcement is not certified: run bypass checks, including IPv6/DHCP and sandbox/escalated routes.')
    print('Restart participating Codex sessions to load managed hooks; cloud-orchestrated sessions may require managed remote hooks.')
    return 0

def run_with_report():
    if '--check' in sys.argv or '--help' in sys.argv or '-h' in sys.argv:
        return main()
    directory=ROOT/'docs/diagnostics';directory.mkdir(parents=True,exist_ok=True)
    destination=directory/('coordinator-install-'+time.strftime('%Y%m%d-%H%M%S')+'.log')
    class Transcript:
        def __init__(self,terminal,report):self.terminal=terminal;self.report=report
        def write(self,text):
            self.report.write(text);self.report.flush()
            return self.terminal.write(text)
        def flush(self):self.report.flush();self.terminal.flush()
    with destination.open('x') as report:
        os.chmod(destination,0o644)
        print(f'Installation log: {destination}',flush=True)
        with contextlib.redirect_stdout(Transcript(sys.stdout,report)),contextlib.redirect_stderr(Transcript(sys.stderr,report)):
            try:return main()
            except Exception:
                traceback.print_exc()
                return 1

if __name__=='__main__':raise SystemExit(run_with_report())
