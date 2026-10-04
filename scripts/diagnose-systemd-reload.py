#!/usr/bin/env python3
"""Read-only PID 1 diagnostics; no reload, signal, debugger attach or service changes."""
import collections
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def read(path):
    try:return Path(path).read_text()
    except OSError as error:return str(error)


def category(target):
    for prefix in ('anon_inode:', 'socket:', 'pipe:'):
        if target.startswith(prefix):
            return target.split('[',1)[0] if prefix!='anon_inode:' else target
    if target.startswith('/sys/fs/cgroup'):return 'cgroup files'
    if target.startswith('/memfd:') or target.startswith('memfd:'):return 'memfd (name omitted)'
    if target.startswith('/proc/'):return 'proc files'
    return 'other files (paths omitted)'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='JSON destination; default is a timestamped file in docs/diagnostics/')
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise SystemExit('Root is needed only to read /proc/1/fd, fdinfo, syscall and stack. Run sudo python3 scripts/diagnose-systemd-reload.py')
    report={'read_only':True,'captured_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'pid1_status':read('/proc/1/status'),'pid1_limits':read('/proc/1/limits')}
    entries=list(Path('/proc/1/fd').iterdir());report['fd_count']=len(entries)
    counts=collections.Counter();pidfds=[];bpf_entries=[];deadline=time.monotonic()+20;examined=0
    for entry in entries:
        if time.monotonic()>deadline:break
        try:target=os.readlink(entry)
        except OSError:continue
        counts[category(target)]+=1;examined+=1
        if 'bpf-prog' in target:bpf_entries.append(entry.name)
        if 'pidfd' in target and len(pidfds)<32:
            info=read('/proc/1/fdinfo/'+entry.name)
            pidfds.append('\n'.join(line for line in info.splitlines() if line.startswith(('Pid:','NSpid:'))))
    # Sample across the descriptor range instead of examining only the oldest.
    bpf_entries.sort(key=int)
    indexes=sorted({int(i*(len(bpf_entries)-1)/63) for i in range(64)}) if bpf_entries else []
    bpf_samples=[{'fd':bpf_entries[i],'info':read('/proc/1/fdinfo/'+bpf_entries[i])} for i in indexes]
    report.update(fd_types=dict(counts),fd_entries_examined=examined,pidfd_samples=pidfds,bpf_fdinfo_samples=bpf_samples)
    samples=[]
    for _ in range(5):
        stat=read('/proc/1/stat').split()
        samples.append({'cpu_ticks_user':stat[13],'cpu_ticks_kernel':stat[14],
                        'syscall':read('/proc/1/syscall'),'kernel_stack':read('/proc/1/stack')})
        time.sleep(1)
    report['samples']=samples
    command=['journalctl','-b','_PID=1','--grep=Reload','-n','12','--no-pager']
    try:report['reload_journal']=subprocess.run(command,capture_output=True,text=True,timeout=8).stdout
    except subprocess.TimeoutExpired:report['reload_journal']='journal query timed out'
    destination=args.output or Path(__file__).resolve().parents[1]/'docs/diagnostics'/('systemd-reload-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation avoids replacing existing evidence or following a link.
    with destination.open('x') as output:
        output.write(json.dumps(report,indent=2)+'\n')
    os.chmod(destination,0o644)
    print(f'Diagnostics saved to {destination}')

if __name__=='__main__':main()
