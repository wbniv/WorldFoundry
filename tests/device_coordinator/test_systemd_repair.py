"""Targeted repair behavior without administrative access or host mutations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture
def repair(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('wf_systemd_repair',ROOT/'scripts/repair-systemd-crash-handler-retention.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=tmp_path;module.SYSTEMD_DIR=tmp_path/'units';module.PID1_FDS=tmp_path/'fds';module.PID1_FDS.mkdir()
    monkeypatch.setattr(module.os,'geteuid',lambda:0)
    return module


def test_only_failed_crash_handler_instances_are_reset(repair,monkeypatch):
    monkeypatch.setattr(repair.os.sys,'argv',['repair','--apply'])
    commands=[];failed=3
    def run(command,**kwargs):
        nonlocal failed
        commands.append(command);out=''
        if command[1]=='list-units':out='apport-coredump-hook@123-abc.service loaded failed failed handler\ndrkonqi-coredump-processor@456.service loaded failed failed handler\navahi-daemon.service loaded failed failed other\n'
        elif command[1]=='show':out=f'NNames=10\nNFailedUnits={failed}\nNJobs=0\n'
        elif command[1]=='reset-failed':failed=1
        elif command[1]=='cat':out=repair.DROPIN
        return subprocess.CompletedProcess(command,0,stdout=out,stderr='')
    monkeypatch.setattr(repair.subprocess,'run',run)
    assert repair.main()==0
    reset=[c for c in commands if c[1]=='reset-failed']
    assert reset==[['systemctl','reset-failed','apport-coredump-hook@123-abc.service','drkonqi-coredump-processor@456.service']]
    report=json.loads(next((repair.ROOT/'docs/diagnostics').glob('*.json')).read_text())
    assert report['untouched_failed_units']==['avahi-daemon.service'] and report['completed']
    assert all(Path(p).read_text()==repair.DROPIN for p in report['dropins'])
    assert sum(c[1]=='daemon-reload' for c in commands)==1


def test_preview_never_mutates_manager_or_installs_overrides(repair,monkeypatch):
    monkeypatch.setattr(repair.os.sys,'argv',['repair'])
    def run(command,**kwargs):
        assert command[1] in ('list-units','show')
        return subprocess.CompletedProcess(command,0,stdout='',stderr='')
    monkeypatch.setattr(repair.subprocess,'run',run)
    assert repair.main()==0 and not repair.SYSTEMD_DIR.exists()


def test_selection_rejects_unrelated_units_and_option_injection(repair):
    assert repair.eligible('drkonqi-coredump-processor@123-456.service')
    for name in ['avahi-daemon.service','apport-coredump-hook.service','--all','drkonqi-coredump-processor@../bad.service']:
        assert not repair.eligible(name)
