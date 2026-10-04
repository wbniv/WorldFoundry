"""Deploy reviewed adapters as administrator, draining sessions without deleting queued work."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
DEST = Path('/opt/wf-device-coordinator/scripts/wf_device')
STATE = Path('/var/lib/wf-device-coordinator')
UNIT = 'wf-device-coordinator.service'


def maintenance(db, enabled):
    db.execute('CREATE TABLE IF NOT EXISTS maintenance(id INTEGER PRIMARY KEY CHECK(id=1), reason TEXT NOT NULL, started REAL NOT NULL)')
    if enabled:
        db.execute('INSERT OR IGNORE INTO maintenance VALUES(1,?,?)', ('Deploying reviewed coordinator adapters', time.time()))
    else:
        db.execute('DELETE FROM maintenance WHERE id=1')


def reviewed(review, deployed):
    for name, hashes in review.items():
        if Path(name).name != name or not name.endswith('.py'):
            raise RuntimeError('Unsafe reviewed filename')
        if hashlib.sha256((ROOT/'scripts/wf_device'/name).read_bytes()).hexdigest() != hashes['new']:
            raise RuntimeError('Source changed after review: '+name)
        if deployed and hashlib.sha256((DEST/name).read_bytes()).hexdigest() not in {hashes['old'], hashes['new']}:
            raise RuntimeError('Deployed adapter changed after review: '+name)


def wait_and_stop(timeout=3600):
    deadline = time.monotonic()+timeout
    last_notice = 0
    with sqlite3.connect(STATE/'coordinator.sqlite3', timeout=10) as db:
        db.execute('BEGIN IMMEDIATE')
        maintenance(db, True)
    while True:
        # This transaction also protects the bootstrap upgrade of older services
        # whose scheduler does not yet recognize the maintenance table.
        with sqlite3.connect(STATE/'coordinator.sqlite3', timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            jobs = db.execute("SELECT id,phase FROM jobs WHERE state='running'").fetchall()
            if not jobs:
                subprocess.run(['systemctl', 'stop', UNIT], check=True, timeout=30)
                return
        if time.monotonic() >= deadline:
            raise RuntimeError('Drain timed out; maintenance retained. Rerun this deployment to resume; no running job was cancelled.')
        if time.monotonic()-last_notice >= 20:
            print('Service upgrade waiting for active sessions and cleanup: '+', '.join(jid+' ('+phase+')' for jid, phase in jobs), flush=True)
            last_notice = time.monotonic()
        time.sleep(2)


def verify_service(timeout=30):
    # Authenticate as the configured client user, never print its credentials.
    code = "import sys;sys.path.insert(0,'/opt/wf-device-coordinator/scripts');from wf_device.client import Client;c=Client();r=c.call('capabilities');assert 'install' in r['workflows'] and r['maintenance_drain'];assert c.call('queue')['maintenance']"
    deadline = time.monotonic()+timeout
    while True:
        try:
            subprocess.run(['systemctl', 'is-active', '--quiet', UNIT], check=True, timeout=5)
            subprocess.run(['runuser', '-u', 'will', '--', sys.executable, '-c', code],
                           check=True, timeout=5, capture_output=True, text=True)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            if time.monotonic() >= deadline:
                if isinstance(error, subprocess.CalledProcessError) and error.stderr:
                    print(error.stderr, file=sys.stderr, flush=True)
                raise RuntimeError('Coordinator readiness verification timed out') from error
            time.sleep(.2)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Administrator deployment requires sudo; device tests use the coordinator.')
    review = json.loads((ROOT/'android/bomberman/deploy-review.json').read_text())
    with (STATE/'locks/deployment.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reviewed(review, deployed=True)
        wait_and_stop()
        backups = {}
        try:
            reviewed(review, deployed=True)
            for name in review:
                backup = DEST/(name+'.before-background-install')
                shutil.copy2(DEST/name, backup)
                backups[name] = backup
                temp = DEST/(name+'.deploying')
                shutil.copy2(ROOT/'scripts/wf_device'/name, temp)
                os.chown(temp, 0, 0)
                os.chmod(temp, 0o644)
                os.replace(temp, DEST/name)
            subprocess.run(['systemctl', 'start', UNIT], check=True, timeout=30)
            verify_service()
        except BaseException:
            # Stop before restoring so no broker reads partially restored code.
            subprocess.run(['systemctl', 'stop', UNIT], check=True, timeout=30)
            for name, backup in backups.items():
                shutil.copy2(backup, DEST/name)
            # An older restored scheduler may ignore maintenance; keep the unit
            # stopped until a verified upgrade can safely resume grants.
            print('Deployment failed; previous adapters restored and service kept stopped. Maintenance remains paused; inspect the log and rerun deployment.', file=sys.stderr, flush=True)
            raise
        with sqlite3.connect(STATE/'coordinator.sqlite3', timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            maintenance(db, False)
    print('Verified background-install capability; queue resumed; reservations retained.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
