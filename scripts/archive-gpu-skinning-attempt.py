#!/usr/bin/env python3
"""Archive one failed skinning session so its cell can be rerun; never deletes evidence.

Moves <evidence>/<key>/ to <evidence>/failed-<key with / as ->-<job>/, removes
the key from jobs.json (so the runner submits a NEW job for the same frozen
recipe), and appends the attempt to failed-attempts.json and to
startup-exits.json's rerun list. Refuses if the cell would exceed --cap
attempts, if the folder or job does not match, or if the archive exists.

The exit facts come from the coordinator's process-exit-info.txt: the exit
record that follows the last launch of the session (reason, status, seconds
after launch). They support a classification, they do not make one:
--classification is the operator's, recorded verbatim.
"""
import argparse
import datetime
import json
from pathlib import Path
import re

LOCAL = datetime.timezone(datetime.timedelta(hours=7))  # coordinator and device clocks: Asia/Bangkok
EXIT = re.compile(r'timestamp=(\S+ \S+) pid=(\d+).*?\n\s*process=\S+ reason=(\d+) \(([^)]*)\) subreason=\S+ \S+ status=(\d+)')


def exit_after_last_launch(folder):
    commands = json.loads((folder / 'commands.json').read_text())
    launches = [c['start'] for c in commands if 'am start' in ' '.join(c['args'])]
    if not launches:
        return dict(launch=None)
    launch = launches[-1]
    facts = dict(last_launch_local=datetime.datetime.fromtimestamp(launch, LOCAL).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
    info = folder / 'process-exit-info.txt'
    if not info.exists():
        return dict(facts, exit='no process-exit-info.txt')
    facts['exit'] = 'no exit record after the last launch'
    for stamp, pid, reason, name, status in EXIT.findall(info.read_text(errors='replace')):
        when = datetime.datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=LOCAL).timestamp()
        if when >= launch:
            facts.update(exit='recorded', exit_pid=int(pid), exit_reason=f'{reason} ({name})', exit_status=int(status),
                         exit_seconds_after_launch=round(when - launch, 3))
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--key', required=True, help='Result key, e.g. close-idle/gpu/round-3')
    parser.add_argument('--job', required=True)
    parser.add_argument('--classification', required=True)
    parser.add_argument('--cap', type=int, default=10, help='Maximum attempts per cell, including this one')
    args = parser.parse_args()
    root = args.evidence
    jobs = json.loads((root / 'jobs.json').read_text())
    if jobs.get(args.key) != args.job:
        raise SystemExit(f'jobs.json maps {args.key} to {jobs.get(args.key)}, not {args.job}')
    folder = root / args.key
    receipt = json.loads((folder / 'receipt.json').read_text())
    if receipt['job'] != args.job:
        raise SystemExit(f'{folder} holds {receipt["job"]}, not {args.job}')
    failed_path = root / 'failed-attempts.json'
    failed = json.loads(failed_path.read_text()) if failed_path.exists() else []
    attempts = sum(1 for f in failed if f['result_key'] == args.key) + 2  # earlier failures, this one, the rerun
    if attempts > args.cap:
        raise SystemExit(f'{args.key}: a rerun would be attempt {attempts}, over the cap of {args.cap}')
    archive = root / ('failed-' + args.key.replace('/', '-') + '-' + args.job)
    if archive.exists():
        raise SystemExit(f'Archive exists: {archive}')
    facts = exit_after_last_launch(folder)
    installs = json.loads((folder / 'apk-installations.json').read_text())
    measured = [i['variant'] for i in installs if (folder / i['variant'] / 'run-1' / 'summary.json').exists()]
    lost = [i['variant'] for i in installs if i['variant'] not in measured]
    folder.rename(archive)
    del jobs[args.key]
    (root / 'jobs.json').write_text(json.dumps(jobs, indent=2) + '\n')
    entry = dict(result_key=args.key, job=args.job, status=receipt['status'], health=receipt['health'],
                 archived_evidence=archive.name, measured_cases=measured, lost_cases=lost,
                 classification=args.classification, exit=facts, action='archived; a new job reruns the same frozen recipe')
    failed.append(entry)
    failed_path.write_text(json.dumps(failed, indent=2) + '\n')
    exits_path = root / 'startup-exits.json'
    if exits_path.exists():
        exits = json.loads(exits_path.read_text())
        exits.setdefault('reruns', []).append({k: entry[k] for k in ('result_key', 'job', 'lost_cases', 'classification', 'exit')})
        exits_path.write_text(json.dumps(exits, indent=2) + '\n')
    submissions_path = root / 'submissions.json'
    if submissions_path.exists():
        submissions = json.loads(submissions_path.read_text())
        if submissions.get(args.key, {}).get('job') == args.job:
            submissions[args.key]['outcome'] = 'failed; archived in ' + archive.name
            submissions_path.write_text(json.dumps(submissions, indent=2) + '\n')
    print(json.dumps(entry, indent=2))


if __name__ == '__main__':
    main()
