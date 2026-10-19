#!/usr/bin/env python3
"""Release failed Apport/DrKonqi instances and prevent their future retention.

Default is a read-only preview. --apply requires root. No service is stopped,
no BPF security restriction is removed, and journal/coredump files are kept.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
SYSTEMD_DIR=Path('/etc/systemd/system')
PID1_FDS=Path('/proc/1/fd')
TEMPLATES=('apport-coredump-hook','drkonqi-coredump-processor')
TARGET=re.compile(r'^(?:apport-coredump-hook|drkonqi-coredump-processor)@[A-Za-z0-9_.:-]+\.service$')
DROPIN='[Unit]\n# Keep crash evidence in the journal, without retaining every failed handler.\nCollectMode=inactive-or-failed\n'


def eligible(name):return TARGET.fullmatch(name) is not None


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    if args.apply and os.geteuid()!=0:ap.error('--apply requires sudo')
    output_dir=ROOT/'docs/diagnostics';output_dir.mkdir(parents=True,exist_ok=True)
    destination=output_dir/('systemd-crash-handler-repair-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
    # Create the evidence file before mutation and refuse to overwrite prior runs.
    with destination.open('x') as stream:stream.write('{}\n')
    os.chmod(destination,0o644)
    report={'apply':args.apply,'commands':[],'completed':False,'started':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    print(f'Repair report: {destination}',flush=True)
    def save():destination.write_text(json.dumps(report,indent=2)+'\n')
    def run(command,timeout=30):
        entry={'command':command,'started':time.time()};report['commands'].append(entry);save()
        try:
            result=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
            entry.update(returncode=result.returncode,elapsed_seconds=time.time()-entry['started'])
            if result.returncode:
                entry['stderr']=result.stderr[-12000:]
                raise RuntimeError('Command failed: '+' '.join(command[:3])+': '+result.stderr[-1000:])
            return result.stdout
        except subprocess.TimeoutExpired as error:
            entry['error']='Timed out; a manager operation may still be running'
            raise RuntimeError(entry['error']) from error
        finally:save()
    def metrics():
        out=run(['systemctl','show','--property=NNames,NFailedUnits,NJobs'])
        values=dict(line.split('=',1) for line in out.splitlines() if '=' in line)
        if os.geteuid()==0:
            counts=collections.Counter()
            for fd in PID1_FDS.iterdir():
                try:
                    name=os.readlink(fd)
                    counts['bpf-programs' if 'bpf-prog' in name else 'other']+=1
                except OSError:pass
            values['pid1_descriptor_types']=dict(counts)
        return values
    try:
        inventory=run(['systemctl','list-units','--state=failed','--no-legend','--plain','--no-pager'],timeout=60)
        names=[line.split()[0] for line in inventory.splitlines() if line.split()]
        targets=[name for name in names if eligible(name)]
        report.update(target_count=len(targets),target_counts=dict(collections.Counter(n.split('@')[0] for n in targets)),
                      targets=targets,untouched_failed_units=[n for n in names if not eligible(n)],before=metrics())
        save()
        if not args.apply:
            report['completed']=True;report['preview_only']=True
            print(f'Preview: {len(targets)} matching failed instances; run with --apply to repair.',flush=True)
            return 0
        paths=[SYSTEMD_DIR/(template+'@.service.d')/'90-wf-collect-failed-handlers.conf' for template in TEMPLATES]
        for path in paths:
            if path.exists() and path.read_text()!=DROPIN:
                raise RuntimeError(f'Conflicting local override at {path}; refusing to replace it')
        # Reset only previously failed matching instances. Other failed services,
        # running crash handlers and all crash evidence remain untouched.
        for start in range(0,len(targets),512):
            batch=targets[start:start+512]
            run(['systemctl','reset-failed',*batch],timeout=120)
            report['reset_count']=start+len(batch);save()
        report['after_reset']=metrics();save()
        # A reference can delay GC. Do not start another expensive reload if the
        # targeted retained-state population did not substantially decrease.
        if len(targets)>2000 and int(report['after_reset'].get('NFailedUnits',len(names)))>len(names)-len(targets)+1000:
            raise RuntimeError('Failed-instance cleanup did not settle; no reload requested. Inspect the saved report.')
        for path in paths:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(DROPIN);os.chmod(path,0o644)
        report['dropins']=[str(path) for path in paths];save()
        run(['systemctl','daemon-reload'],timeout=60)
        report['after_reload']=metrics()
        for template in TEMPLATES:
            configuration=run(['systemctl','cat','--no-pager',template+'@.service'])
            report.setdefault('template_configuration',{})[template]=configuration
            if 'CollectMode=inactive-or-failed' not in configuration:
                raise RuntimeError(f'{template} override verification failed')
        report['completed']=True
        print('Repair completed; measurements and commands are saved in the report.',flush=True)
        return 0
    except (OSError,RuntimeError) as error:
        report['error']=str(error)
        print(f'Repair incomplete; see {destination}',flush=True)
        return 1
    finally:
        report['finished']=time.strftime('%Y-%m-%dT%H:%M:%S%z');save()

if __name__=='__main__':raise SystemExit(main())
