#!/usr/bin/env python3
"""Resume frozen skinning recipes through the shared coordinator, one session at a time.

Stops on failure; never reboots, bypasses recovery, or retries a failed session.
Seed jobs.json with already submitted jobs to resume without duplicate submissions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {'completed', 'failed', 'cancelled', 'recovery-required', 'superseded'}


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def task(*args):
    result = subprocess.run(['task', *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def read_status(job):
    # A service refresh does not cancel its durable jobs. Retry only the
    # read; never repeat submission or retry a failed measurement session.
    for attempt in range(7):
        try:
            return json.loads(task('chromecast:status', 'JOB=' + job))
        except RuntimeError as error:
            if attempt == 6 or 'Coordinator connection failed' not in str(error):
                raise
            print('Coordinator unavailable; retrying status read', job, attempt + 1, flush=True)
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--device', choices=['chromecast-test-01', 'chromecast-test-02'], required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    campaign = json.loads(args.campaign.read_text())
    frozen_path = args.fixtures / 'variants.json'
    frozen = json.loads(frozen_path.read_text())
    for name, item in frozen['variants'].items():
        if hashlib.sha256((args.fixtures / (name + '.apk')).read_bytes()).hexdigest() != item['apk_sha256']:
            raise ValueError('Frozen APK changed: ' + name)
    for source, destination in [(args.campaign, args.evidence / 'campaign.json'),
                                (frozen_path, args.evidence / 'variants.json')]:
        if destination.exists() and source.read_bytes() != destination.read_bytes():
            raise ValueError('Conflicting campaign provenance: ' + str(destination))
        if not destination.exists():
            shutil.copyfile(source, destination)
    jobs_path = args.evidence / 'jobs.json'
    jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else {}
    progress = dict(device=args.device, completed=[], total=len(campaign['recipes']), state='running')
    progress_path = args.evidence / 'campaign-progress.json'
    save(progress_path, progress)
    try:
        for recipe in campaign['recipes']:
            match = re.search(r'-round-(\d+)$', recipe['name'])
            stage = 'profile' if recipe['frame_profile'] else 'round-' + match[1]
            key = f"{recipe['view']}/{recipe['mode']}/{stage}"
            if key not in jobs:
                output = task('chromecast:submit', 'DEVICE=' + args.device,
                              'RECIPE=' + recipe['path'], 'ASYNC=true')
                found = re.search(r'Accepted (J-[a-f0-9]{12}):', output)
                if not found:
                    raise ValueError('No accepted job ID: ' + output)
                jobs[key] = found[1]
                save(jobs_path, jobs)
                print('submitted', key, jobs[key], flush=True)
            job = jobs[key]
            progress.update(current=key, job=job)
            save(progress_path, progress)
            folder = args.evidence / key
            watch_path = args.evidence / (recipe['name'] + '-watch.log')
            with watch_path.open('a') as watch_log:
                watcher = subprocess.Popen(['task', 'chromecast:watch', 'JOB=' + job], cwd=ROOT,
                                           stdout=watch_log, stderr=subprocess.STDOUT)
                try:
                    previous = None
                    while True:
                        status = read_status(job)
                        state = (status['state'], status['phase'], (status.get('hold') or {}).get('code'))
                        if state != previous:
                            print(key, job, *state, flush=True)
                            previous = state
                        if status['state'] in TERMINAL:
                            break
                        time.sleep(15)
                finally:
                    if watcher.poll() is None:
                        watcher.terminate()
                        watcher.wait(timeout=10)
            task('chromecast:evidence', 'JOB=' + job, 'OUT=' + str(folder))
            receipt = json.loads((folder / 'receipt.json').read_text())
            if (status['state'] != 'completed' or receipt['status'] != 'succeeded'
                    or receipt['health'] != 'ready' or receipt['survivors']
                    or any(not j['restored'] for j in receipt['journal'])):
                raise ValueError(f'Incomplete session/cleanup: {key} {job}')
            installed = json.loads((folder / 'apk-installations.json').read_text())
            if len(installed) != len(recipe['order']) or {i['variant'] for i in installed} != set(recipe['order']):
                raise ValueError('Unexpected installed cases: ' + key)
            for item in installed:
                name = f"{recipe['view']}-{item['variant']}-{recipe['mode']}" + ('-profile' if recipe['frame_profile'] else '')
                if item['status'] != 'verified' or item['installed_sha256'] != frozen['variants'][name]['apk_sha256']:
                    raise ValueError('Installed APK mismatch: ' + name)
                run = folder / item['variant'] / 'run-1'
                summary = json.loads((run / 'summary.json').read_text())
                if summary.get('sampling_holes') or summary.get('latency_statistics_may_include_unobserved_bridges') or summary.get('observed_span_seconds', 0) < 59:
                    raise ValueError('Incomplete presentation coverage: ' + str(run))
                if recipe['mode'].startswith('gpu') and item['variant'] != 'none':
                    log = (run / 'wf.log').read_text(errors='replace')
                    marker = log.rfind('zforth: INDEXOF_CAMSHOT = 1921 (expect 1921)')
                    if marker < 0:
                        raise ValueError('No current scene marker: ' + str(run))
                    log = log[marker:]
                    if f"skinning: effective={recipe['mode']} vertices=" not in log or 'skinning: effective=cpu' in log:
                        raise ValueError('Missing GPU draw or CPU fallback: ' + str(run))
                print('sample', key, item['variant'], f"{summary['fps']:.3f} FPS", flush=True)
            restored = [j for j in receipt['journal'] if j['key'] == 'variant']
            if len(restored) != 1 or restored[0]['verification']['installed_sha256'] != campaign['restore_sha256']:
                raise ValueError('Restore APK mismatch: ' + key)
            progress['completed'].append(key)
            save(progress_path, progress)
        progress.update(state='complete')
        save(progress_path, progress)
        print('campaign complete', args.evidence, flush=True)
    except Exception as error:
        progress.update(state='stopped', error=str(error))
        save(progress_path, progress)
        raise


if __name__ == '__main__':
    main()
