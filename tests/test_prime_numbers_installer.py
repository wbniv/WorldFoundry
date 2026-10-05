"""Connection failures recover through durable coordinator jobs, with bounded retries."""
import importlib.util
import io
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def installer(tmp_path, monkeypatch, states, initial=None):
    spec = importlib.util.spec_from_file_location('prime_installer', ROOT/'android/prime-numbers/install.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'OUT', tmp_path)
    receipt = {'apk':'/frozen/primes.apk', 'sha256':'abc'}
    if initial:
        (tmp_path/'jobs.json').write_text(json.dumps(dict(receipt, **initial)))
    calls, jobs = [], {}
    for jid, state in states:
        jobs[jid] = state
    admissions = iter(states)

    def run(command, log):
        calls.append(command)
        operation = command[1].split(':')[1]
        if operation in {'submit', 'readd'}:
            jid, _ = next(admissions)
            return 0, 'Accepted ' + jid + ': queued; ' + operation
        jid = next(arg[4:] for arg in command if arg.startswith('JOB='))
        if operation == 'status':
            status = {'state':jobs[jid]} if isinstance(jobs[jid], str) else jobs[jid]
            return 0, json.dumps({'id':jid, **status})
        if operation == 'watch':
            state = jobs[jid] if isinstance(jobs[jid], str) else jobs[jid]['state']
            return (0 if state == 'completed' else 1), ''
        if operation == 'evidence':
            return 0, ''
        pytest.fail('Unexpected operation: ' + operation)

    monkeypatch.setattr(module, 'run', run)
    module.test_delays = []
    monkeypatch.setattr(module.time, 'sleep', module.test_delays.append)
    return module, module.Installation(receipt, io.StringIO()), calls, jobs


def test_connection_failure_reconnects_then_replaces_install_before_check(tmp_path, monkeypatch):
    module, session, calls, _ = installer(tmp_path, monkeypatch, [
        ('J-failed','needs-local-setup'), ('J-reconnect','completed'),
        ('J-installed','completed'), ('J-checked','completed')])
    assert session.execute() == 0
    submissions = [c for c in calls if c[1] in {'chromecast:submit','chromecast:readd'}]
    assert [c[1] for c in submissions] == ['chromecast:submit','chromecast:readd','chromecast:submit','chromecast:submit']
    assert 'WORKFLOW=install' in submissions[0] and 'WORKFLOW=install' in submissions[2]
    assert 'VALIDATOR=prime-study' in submissions[3]
    assert all('DEVICE=chromecast-test-01' in c for c in submissions)
    assert all(c[-1] == 'APK=/frozen/primes.apk' for c in submissions if c[1]=='chromecast:submit' and 'WORKFLOW=install' in c)
    watched = [c[-1] for c in calls if c[1]=='chromecast:watch']
    assert watched == ['JOB=J-failed','JOB=J-reconnect','JOB=J-installed','JOB=J-checked']
    assert json.loads((tmp_path/'jobs.json').read_text())['jobs'] == {'install':'J-installed','check':'J-checked'}


def test_repeated_connection_failure_stops_without_reconnect_loop(tmp_path, monkeypatch):
    _, session, calls, _ = installer(tmp_path, monkeypatch, [
        ('J-failed','needs-local-setup'), ('J-reconnect','completed'), ('J-again','needs-local-setup')])
    assert session.execute() != 0
    assert sum(c[1]=='chromecast:readd' for c in calls) == 1
    assert not any('WORKFLOW=check' in c for c in calls)


def test_failed_reconnect_preserves_failed_install_and_stops(tmp_path, monkeypatch):
    _, session, calls, _ = installer(tmp_path, monkeypatch, [
        ('J-failed','needs-local-setup'), ('J-reconnect','needs-local-setup'),
        ('J-second','needs-local-setup'), ('J-third','needs-local-setup')])
    assert session.execute() != 0
    data = json.loads((tmp_path/'jobs.json').read_text())
    assert data['jobs']['install'] == 'J-failed'
    assert 'recovery' not in data
    assert sum(c[1]=='chromecast:submit' for c in calls) == 1
    assert sum(c[1]=='chromecast:readd' for c in calls) == 3


def test_delayed_wireless_discovery_recovers_on_second_attempt(tmp_path, monkeypatch):
    module, session, calls, _ = installer(tmp_path, monkeypatch, [
        ('J-failed','needs-local-setup'), ('J-first','needs-local-setup'),
        ('J-second','completed'), ('J-installed','completed'), ('J-checked','completed')])
    assert session.execute() == 0
    assert module.test_delays == [10]
    assert sum(c[1]=='chromecast:readd' for c in calls) == 2


def test_reconnect_service_failure_does_not_loop(tmp_path, monkeypatch):
    module, session, calls, _ = installer(tmp_path, monkeypatch, [
        ('J-failed','needs-local-setup'), ('J-reconnect','failed')])
    assert session.execute() != 0
    assert module.test_delays == []
    assert sum(c[1]=='chromecast:readd' for c in calls) == 1


def test_foreground_install_denial_uses_owned_check_without_background_retry(tmp_path, monkeypatch):
    _, session, calls, _ = installer(tmp_path, monkeypatch, [
        ('J-blocked', {'state':'failed', 'error':'Cannot update the foreground app without interrupting it'}),
        ('J-checked','completed')])
    assert session.execute() == 0
    admissions = [c for c in calls if c[1]=='chromecast:submit']
    assert len(admissions) == 2
    assert 'WORKFLOW=install' in admissions[0] and 'WORKFLOW=check' in admissions[1]
    assert not any(c[1]=='chromecast:readd' for c in calls)
    assert json.loads((tmp_path/'jobs.json').read_text())['install_in_check']
    before = len(admissions)
    assert session.execute() == 0
    assert len([c for c in calls if c[1]=='chromecast:submit']) == before


def test_interrupted_reconnect_reuses_journal_job_without_duplicate_admission(tmp_path, monkeypatch):
    _, session, calls, jobs = installer(tmp_path, monkeypatch,
        [('J-installed','completed'), ('J-checked','completed')],
        {'jobs':{'install':'J-failed'}, 'recovery':{'for_job':'J-failed','job':'J-existing'}})
    jobs.update({'J-failed':'needs-local-setup', 'J-existing':'completed'})
    assert session.execute() == 0
    assert not any(c[1]=='chromecast:readd' for c in calls)
    assert any(c[1]=='chromecast:watch' and c[-1]=='JOB=J-existing' for c in calls)


@pytest.mark.parametrize('replacement', ['completed','failed'])
def test_explicit_check_retry_submits_only_one_replacement(tmp_path, monkeypatch, replacement):
    _, session, calls, jobs = installer(tmp_path, monkeypatch, [('J-new',replacement)],
        {'jobs':{'install':'J-installed','check':'J-old'}})
    jobs.update({'J-installed':'completed', 'J-old':'failed'})
    session.retry_failed_check = True
    assert session.execute() == (0 if replacement == 'completed' else 1)
    submissions = [c for c in calls if c[1]=='chromecast:submit']
    assert len(submissions) == 1 and 'WORKFLOW=check' in submissions[0]
    assert not any(c[1]=='chromecast:readd' for c in calls)


@pytest.mark.parametrize('state', ['cancelled','failed','recovery-required'])
def test_nonconnection_failures_are_not_retried(tmp_path, monkeypatch, state):
    _, session, calls, _ = installer(tmp_path, monkeypatch, [('J-failed',state)])
    assert session.execute() != 0
    assert sum(c[1]=='chromecast:submit' for c in calls) == 1
    assert not any(c[1]=='chromecast:readd' for c in calls)
