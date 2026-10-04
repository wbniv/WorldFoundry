"""Deployment drain preserves active sessions, queues and personal reservations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from wf_device.store import Store
from wf_device.service import Coordinator
from wf_device.client import snapshot_text


def store_at(path):
    return Store(path, [{'id': 'd1', 'serial': 's1', 'health': 'ready', 'enrolled': True},
                        {'id': 'd2', 'serial': 's2', 'health': 'ready', 'enrolled': True}])


def deploy_module():
    spec = importlib.util.spec_from_file_location('deployment', ROOT/'android/bomberman/deploy-coordinator.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_on_other_reserved_device_during_profile(tmp_path):
    store = store_at(tmp_path/'state')
    owner = store.register(1000, 'test')['session']
    profile = store.submit(owner, {'workflow': 'profile', 'device': 'd1', 'app': 'aquarium'})
    assert store.claim() == [profile['id']]
    store.reserve(owner, 'd2', 'Watching TV')
    same = store.submit(owner, {'workflow': 'install', 'device': 'd1', 'app': 'bomberman'})
    other = store.submit(owner, {'workflow': 'install', 'device': 'd2', 'app': 'bomberman'})
    assert store.claim() == [other['id']]
    assert store.job(same['id'])['state'] == 'queued'
    assert store.devices()[1]['reservation']['owner'] == owner


def test_drain_is_durable_and_accepts_submissions(tmp_path):
    deployment = deploy_module()
    store = store_at(tmp_path/'state')
    owner = store.register(1000, 'test')['session']
    active = store.submit(owner, {'workflow': 'check', 'device': 'd1', 'app': 'aquarium'})
    assert store.claim() == [active['id']]
    store.reserve(owner, 'd2', 'Watching TV')
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        deployment.maintenance(db, True)
    queued = store.submit(owner, {'workflow': 'install', 'device': 'd2', 'app': 'bomberman'})
    assert store.claim() == []
    assert store.job(active['id'])['state'] == 'running'
    store.finish(active['id'], 'completed', None, 'ready')
    restarted = Store(store.root)
    assert restarted.claim() == []
    assert 'grants paused' in snapshot_text(restarted.snapshot())
    assert restarted.devices()[1]['reservation']['owner'] == owner
    with restarted.db() as db:
        deployment.maintenance(db, False)
    assert restarted.claim() == [queued['id']]


def test_maintenance_serializes_with_claim(tmp_path):
    deployment = deploy_module()
    store = store_at(tmp_path/'state')
    owner = store.register(1000, 'test')['session']
    queued = store.submit(owner, {'workflow': 'check', 'device': 'd1', 'app': 'aquarium'})
    started = threading.Event()
    grants = []
    def claim():
        started.set()
        grants.extend(store.claim())
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        deployment.maintenance(db, True)
        thread = threading.Thread(target=claim)
        thread.start()
        assert started.wait(2)
    thread.join(3)
    assert not thread.is_alive()
    assert grants == []
    assert store.job(queued['id'])['state'] == 'queued'


def test_capabilities_and_no_client_maintenance_control(tmp_path):
    coordinator = Coordinator({'state': str(tmp_path/'state'), 'devices': [], 'allowed_uids': [1000]})
    try:
        credentials = coordinator.dispatch(1000, {'method': 'register', 'args': {'label': 'test'}})
        call = {'method': 'capabilities', 'credentials': credentials}
        assert coordinator.dispatch(1000, call)['maintenance_drain']
        assert 'install' in coordinator.dispatch(1000, call)['workflows']
        with pytest.raises(ValueError, match='Unknown operation'):
            coordinator.dispatch(1000, {**call, 'method': 'maintenance'})
    finally:
        coordinator.lock.close()


def test_upgrade_waits_for_running_only_and_keeps_queue(tmp_path, monkeypatch):
    deployment = deploy_module()
    store = store_at(tmp_path/'state')
    monkeypatch.setattr(deployment, 'STATE', store.root)
    owner = store.register(1000, 'test')['session']
    active = store.submit(owner, {'workflow': 'check', 'device': 'd1', 'app': 'aquarium'})
    store.claim()
    queued = store.submit(owner, {'workflow': 'check', 'device': 'd1', 'app': 'aquarium'})
    calls = []
    def run(args, **kwargs):
        assert store.job(active['id'])['state'] == 'completed'
        calls.append(args)
    monkeypatch.setattr(deployment.subprocess, 'run', run)
    monkeypatch.setattr(deployment.time, 'sleep', lambda _: store.finish(active['id'], 'completed', None, 'ready'))
    deployment.wait_and_stop(timeout=2)
    assert calls == [['systemctl', 'stop', deployment.UNIT]]
    assert store.job(queued['id'])['state'] == 'queued'
    assert store.snapshot()['maintenance']


def test_deployment_failure_restores_files_and_retains_pause(tmp_path, monkeypatch):
    deployment = deploy_module()
    store = store_at(tmp_path/'state')
    dest = tmp_path/'dest'
    dest.mkdir()
    root = tmp_path/'source'
    (root/'scripts/wf_device').mkdir(parents=True)
    (root/'android/bomberman').mkdir(parents=True)
    (dest/'service.py').write_text('previous')
    (root/'scripts/wf_device/service.py').write_text('replacement')
    (root/'android/bomberman/deploy-review.json').write_text(json.dumps({'service.py': {}}))
    monkeypatch.setattr(deployment, 'ROOT', root)
    monkeypatch.setattr(deployment, 'DEST', dest)
    monkeypatch.setattr(deployment, 'STATE', store.root)
    monkeypatch.setattr(deployment.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(deployment.os, 'chown', lambda *args: None)
    monkeypatch.setattr(deployment, 'reviewed', lambda *args, **kwargs: None)
    calls = []
    monkeypatch.setattr(deployment.subprocess, 'run', lambda args, **kwargs: calls.append(args))
    def fail():
        assert (dest/'service.py').read_text() == 'replacement'
        assert store.claim() == []
        raise RuntimeError('capability check failed')
    monkeypatch.setattr(deployment, 'verify_service', fail)
    with pytest.raises(RuntimeError, match='capability check failed'):
        deployment.main()
    assert (dest/'service.py').read_text() == 'previous'
    assert store.snapshot()['maintenance']
    assert calls[-1] == ['systemctl', 'stop', deployment.UNIT]


def test_readiness_retries_until_socket_is_available(monkeypatch):
    deployment = deploy_module()
    attempts = []
    def run(args, **kwargs):
        if args[0] == 'runuser':
            attempts.append(args)
            if len(attempts) < 3:
                raise subprocess.CalledProcessError(1, args, stderr='socket does not exist yet')
    monkeypatch.setattr(deployment.subprocess, 'run', run)
    monkeypatch.setattr(deployment.time, 'sleep', lambda _: None)
    deployment.verify_service()
    assert len(attempts) == 3


def test_readiness_failure_is_bounded(monkeypatch):
    deployment = deploy_module()
    def run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(deployment.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='readiness verification timed out'):
        deployment.verify_service(timeout=0)


@pytest.mark.parametrize('cause', [FileNotFoundError('socket missing'), ConnectionRefusedError('stopped')])
def test_installer_resumes_deployment_when_service_is_stopped(tmp_path, monkeypatch, cause):
    spec = importlib.util.spec_from_file_location('installer', ROOT/'android/bomberman/install.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    monkeypatch.setattr(installer, 'OUT', tmp_path)
    def client():
        raise RuntimeError('Coordinator connection failed') from cause
    monkeypatch.setattr(installer, 'Client', client)
    calls = []
    class Process:
        stdout = ['deployment requested\n']
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def wait(self):
            return 7
    def popen(args, **kwargs):
        calls.append(args)
        return Process()
    monkeypatch.setattr(installer.subprocess, 'Popen', popen)
    assert installer.main() == 7
    assert calls[0][0] == 'sudo'
    assert calls[0][-1].endswith('deploy-coordinator.py')
    assert (tmp_path/'installation.log').read_text() == 'deployment requested\n'
