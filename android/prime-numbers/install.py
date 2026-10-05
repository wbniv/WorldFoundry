#!/usr/bin/env python3
"""Finish the reviewed registration and Chromecast 1 installation from a terminal."""
import hashlib
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT/'android/prime-numbers'
OUT = ROOT/'docs/diagnostics/prime-numbers-chromecast'


def run(command, log):
    print('+ ' + ' '.join(map(str, command)), flush=True)
    log.write('+ ' + ' '.join(map(str, command)) + '\n'); log.flush()
    lines = []
    with subprocess.Popen([str(arg) for arg in command], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True) as process:
        for line in process.stdout:
            print(line, end='', flush=True); log.write(line); log.flush(); lines.append(line)
        code = process.wait()
    return code, ''.join(lines)


class Installation:
    """Durable workflow with one bounded reconnect sequence per invocation."""
    def __init__(self, receipt, log, retry_failed_check=False):
        self.receipt, self.log = receipt, log
        self.journal = OUT/'jobs.json'
        previous = json.loads(self.journal.read_text()) if self.journal.exists() else {}
        self.data = previous if previous.get('sha256') == receipt['sha256'] else {
            'sha256':receipt['sha256'], 'apk':receipt['apk'], 'jobs':{}, 'history':[]}
        self.data.setdefault('history', [])
        self.reconnect_attempted = False
        self.retry_failed_check = retry_failed_check

    def save(self):
        temp = self.journal.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2) + '\n')
        temp.replace(self.journal)

    def submit(self, command):
        code, output = run(command, self.log)
        if code:
            return code, None
        match = re.search(r'Accepted (J-[a-zA-Z0-9]+):', output)
        if not match:
            raise RuntimeError('Submission returned no job ID; inspect the saved log before retrying')
        return 0, match[1]

    def follow(self, jid):
        code, _ = run(['task', 'chromecast:watch', 'JOB=' + jid], self.log)
        evidence_code, _ = run(['task', 'chromecast:evidence', 'JOB=' + jid, 'OUT=' + str(OUT/jid)], self.log)
        status_code, output = run(['task', 'chromecast:status', 'JOB=' + jid], self.log)
        if status_code:
            return status_code, None
        status, _ = json.JSONDecoder().raw_decode(output.lstrip())
        return code or evidence_code, status

    def reconnect(self, workflow, failed):
        if self.reconnect_attempted:
            print('Connection failed again after reconnect; stopping. Enable Wireless debugging on Chromecast 1, then rerun this installer.', flush=True)
            return 1
        self.reconnect_attempted = True
        recovery = self.data.get('recovery', {})
        attempt = recovery.get('attempt', 1) if recovery.get('for_job') == failed else 1
        while attempt <= 3:
            if recovery.get('for_job') != failed or recovery.get('attempt', 1) != attempt:
                if attempt > 1:
                    seconds = 10 * (attempt - 1)
                    message = 'Waiting ' + str(seconds) + ' seconds for wireless discovery before reconnect attempt ' + str(attempt) + '/3.'
                    print(message, flush=True); self.log.write(message + '\n'); self.log.flush()
                    time.sleep(seconds)
                code, jid = self.submit(['task', 'chromecast:readd', 'DEVICE=chromecast-test-01', 'ASYNC=true'])
                if code:
                    return code
                recovery = {'for_job':failed, 'job':jid, 'attempt':attempt}
                self.data['recovery'] = recovery
                self.save()  # Resume this reconnect if the watcher is interrupted.
            code, status = self.follow(recovery['job'])
            if status and status['state'] == 'completed' and code == 0:
                break
            if status and status['state'] in {'needs-local-setup', 'failed', 'recovery-required'}:
                self.data['history'].append({'workflow':'readd', 'job':recovery['job'], 'state':status['state'], 'attempt':attempt})
                self.data.pop('recovery', None); self.save()
            if not status or status['state'] != 'needs-local-setup' or attempt == 3:
                print('Coordinator reconnect did not complete. Enable Wireless debugging on Chromecast 1 and rerun; no direct device-control fallback.', flush=True)
                return code or 1
            attempt += 1
        self.data['history'].append({'workflow':workflow, 'job':failed, 'state':'needs-local-setup', 'reconnect':recovery['job']})
        self.data['jobs'].pop(workflow, None)
        self.save()
        print('Reconnect completed. Submitting a replacement ' + workflow + ' job.', flush=True)
        return 0

    def execute(self):
        for workflow in ('install', 'check'):
            if workflow == 'install' and self.data.get('install_in_check'):
                continue
            while True:
                jid = self.data['jobs'].get(workflow)
                if not jid:
                    command = ['task', 'chromecast:submit', 'DEVICE=chromecast-test-01', 'APP=primes',
                               'WORKFLOW=' + workflow, 'APK=' + self.receipt['apk']]
                    if workflow == 'check':
                        command.append('VALIDATOR=prime-study')
                    code, jid = self.submit(command)
                    if code:
                        return code
                    self.data['jobs'][workflow] = jid; self.save()
                print('Following ' + workflow + ' job ' + jid, flush=True)
                code, status = self.follow(jid)
                if status and status['state'] == 'completed' and code == 0:
                    break
                if (workflow == 'install' and status and status['state'] == 'failed'
                        and status.get('error') == 'Cannot update the foreground app without interrupting it'):
                    # The background workflow must preserve the foreground app.
                    # The separately authorized check installs within its own
                    # interactive lease, and waits behind any personal reservation.
                    self.data['history'].append({'workflow':workflow, 'job':jid, 'state':'failed', 'action':'install in owned check session'})
                    self.data['install_in_check'] = True; self.save()
                    print('App is foreground. Background install was preserved; the coordinated check session will install and verify the APK.', flush=True)
                    break
                if status and status['state'] == 'needs-local-setup':
                    recovery_code = self.reconnect(workflow, jid)
                    if recovery_code == 0:
                        continue
                    return recovery_code
                if workflow == 'check' and self.retry_failed_check and status and status['state'] == 'failed':
                    self.retry_failed_check = False
                    self.data['history'].append({'workflow':workflow, 'job':jid, 'state':'failed', 'action':'explicit check retry'})
                    self.data['jobs'].pop(workflow, None); self.save()
                    continue
                # Cancelled, uncertain-install, runtime and service errors must not
                # silently trigger another installation or a direct-control path.
                return code or 1
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry-check', action='store_true', help='Retry one failed hardware check, retaining its evidence')
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    report = OUT/'installation.log'
    print('Installation output: ' + str(report), flush=True)
    receipt = json.loads((APP/'build/build-receipt.json').read_text())
    if hashlib.sha256(Path(receipt['apk']).read_bytes()).hexdigest() != receipt['sha256']:
        raise RuntimeError('Frozen APK hash does not match the build receipt')
    review = json.loads((APP/'deploy-review.json').read_text())
    for name, hashes in review.items():
        if hashlib.sha256((ROOT/'scripts/wf_device'/name).read_bytes()).hexdigest() != hashes['new']:
            raise RuntimeError('Reviewed adapter source changed: ' + name)
    deployed = Path('/opt/wf-device-coordinator/scripts/wf_device')
    ready = all((deployed/name).exists() and hashlib.sha256((deployed/name).read_bytes()).hexdigest() == hashes['new']
                for name, hashes in review.items())
    with report.open('a') as log:
        if not ready:
            if not sys.stdin.isatty():
                raise RuntimeError('Registration needs administrator authentication. Run this installer in your terminal; never send a password in chat.')
            code, _ = run(['sudo', sys.executable, ROOT/'android/bomberman/deploy-coordinator.py',
                           '--review', APP/'deploy-review.json'], log)
            if code:
                return code
        for operation in ('devices', 'queue'):
            code, _ = run(['task', 'chromecast:' + operation], log)
            if code:
                return code
        code = Installation(receipt, log, retry_failed_check=args.retry_check).execute()
        if code:
            return code
    print('Chromecast 1 installation and remote verification completed. Evidence: ' + str(OUT), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
